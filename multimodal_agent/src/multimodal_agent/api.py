import shutil
import sqlite3
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from enum import Enum
from pathlib import Path
from uuid import uuid4

import click
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastmcp.client import Client
from loguru import logger

from multimodal_agent.agent.checkpointer import checkpointer_context
from multimodal_agent.agent.graph.graph import build_graph
from multimodal_agent.config import get_settings
from multimodal_agent.models import (
    AssistantMessageResponse,
    ProcessVideoRequest,
    ProcessVideoResponse,
    ResetMemoryRequest,
    ResetMemoryResponse,
    UserMessageRequest,
    VideoUploadResponse,
)

settings = get_settings()

# The agent and MCP server default to the same repository-level directory,
# while Docker can override this with the mounted /app/shared_media path.
SHARED_MEDIA_DIR = settings.SHARED_MEDIA_DIR
SHARED_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

# ── Background task status store ────────────────────────────────────────────
# FIX (P1 - background task state only in memory): a plain in-process dict
# doesn't survive a restart/redeploy and isn't shared across workers, so a
# client polling /task-status/{task_id} can get a false NOT_FOUND for a task
# that really did complete. SQLite gives us a durable, file-backed store with
# no extra infra dependency; swap for Redis/Postgres if you run multiple
# hosts without a shared filesystem.
TASK_DB_PATH = SHARED_MEDIA_DIR / ".task_status.db"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_FOUND = "not_found"


def _init_task_db() -> None:
    with sqlite3.connect(TASK_DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS task_status ("
            "task_id TEXT PRIMARY KEY, status TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        conn.commit()


@contextmanager
def _task_db():
    conn = sqlite3.connect(TASK_DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def set_task_status(task_id: str, status: TaskStatus) -> None:
    with _task_db() as conn:
        conn.execute(
            "INSERT INTO task_status (task_id, status, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(task_id) DO UPDATE SET status = excluded.status, updated_at = excluded.updated_at",
            (task_id, status.value),
        )
        conn.commit()


def get_task_status_value(task_id: str) -> str:
    with _task_db() as conn:
        row = conn.execute(
            "SELECT status FROM task_status WHERE task_id = ?", (task_id,)
        ).fetchone()
    return row[0] if row else TaskStatus.NOT_FOUND.value


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    lifespan context manager for FastAPI app. Sets up the checkpointer and builds the graph.
    """
    _init_task_db()
    async with AsyncExitStack() as stack:
        checkpointer = await stack.enter_async_context(checkpointer_context())
        app.state.graph, app.state.mcp_prompts = await build_graph(checkpointer)
        yield


app = FastAPI(
    title="Rocky API",
    description="An AI-powered sports assistant API using OpenAI",
    docs_url="/docs",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for media serving
app.mount("/media", StaticFiles(directory=str(SHARED_MEDIA_DIR)), name="media")


@app.get("/")
async def root():
    """
    Root endpoint that redirects to API documentation
    """
    return {"message": "Welcome to Rocky API. Visit /docs for documentation"}


@app.get("/health")
async def health(fastapi_request: Request):
    """
    Liveness/readiness check.

    Reports "ok" once lifespan has finished building the graph (i.e. MCP
    tool/prompt discovery succeeded and the checkpointer is open) --
    cheap and synchronous, no network round-trip on every call.
    """
    is_ready = getattr(fastapi_request.app.state, "graph", None) is not None
    return {"status": "ok" if is_ready else "not_ready"}


@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    return {"task_id": task_id, "status": get_task_status_value(task_id)}


@app.post("/process-video")
async def process_video(request: ProcessVideoRequest, bg_tasks: BackgroundTasks):
    """
    Process a video and return the results
    """
    task_id = str(uuid4())

    async def background_process_video(video_path: str, task_id: str):
        """
        Background task to process the video
        """
        set_task_status(task_id, TaskStatus.IN_PROGRESS)

        if not Path(video_path).exists():
            logger.error(f"Video file not found: {video_path}")
            set_task_status(task_id, TaskStatus.FAILED)
            return

        try:
            mcp_client = Client(settings.MCP_SERVER)
            async with mcp_client:
                result = await mcp_client.call_tool("process_video", {"video_path": video_path})
        except Exception as e:
            logger.error(f"Error processing video {video_path}: {e}")
            set_task_status(task_id, TaskStatus.FAILED)
            return

        # FIX (P0 - API marks failed processing as completed): `process_video`
        # returns bool -- True only if the video is actually indexed and
        # ready. The absence of an exception here is NOT the same as
        # success: both a tool-level error (`result.is_error`) and a clean
        # `False` return value (`result.data`) must be checked explicitly,
        # otherwise a failed re-encode/indexing pass gets reported to the
        # frontend as COMPLETED.
        succeeded = (not result.is_error) and bool(result.data)
        if not succeeded:
            logger.error(f"process_video reported failure for {video_path}: {result.content}")
            set_task_status(task_id, TaskStatus.FAILED)
            return

        set_task_status(task_id, TaskStatus.COMPLETED)

    set_task_status(task_id, TaskStatus.PENDING)
    bg_tasks.add_task(background_process_video, request.video_path, task_id)
    return ProcessVideoResponse(message="Task enqueued for processing", task_id=task_id)


@app.post("/chat", response_model=AssistantMessageResponse)
async def chat(request: UserMessageRequest, fastapi_request: Request):
    graph = getattr(fastapi_request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Agent is still initializing. Please retry in a moment.",
        )

    thread_id = request.thread_id or str(uuid4())

    # Normalize path separators so the same video_path works on Windows
    # development (backslashes) and Linux/Docker (forward slashes).
    video_path = request.video_path
    if video_path:
        video_path = video_path.replace("\\", "/")

    try:
        result = await graph.ainvoke(
            {
                "messages": [{"role": "user", "content": request.message}],
                "video_path": video_path,
                "image_base64": request.image_base64,
            },
            config={"configurable": {"thread_id": thread_id}},
        )
    except Exception as exc:
        logger.error(f"Graph invocation failed for thread {thread_id}: {exc}")
        raise HTTPException(
            status_code=500,
            detail=f"Agent encountered an error: {exc}",
        )

    last_message = result["messages"][-1]
    return AssistantMessageResponse(
        message=last_message.content,
        clip_path=result.get("clip_path"),
        thread_id=thread_id,
    )


@app.post("/reset-memory")
async def reset_memory(
    fastapi_request: Request,
    body: ResetMemoryRequest | None = None,
    thread_id: str | None = None,
):
    """
    Reset the memory of the agent for a given thread.
    Accepts ``thread_id`` from either a JSON body (``{"thread_id": "..."}```)
    or as a plain query parameter so both invocation styles work.
    """
    graph = getattr(fastapi_request.app.state, "graph", None)
    if graph is None:
        raise HTTPException(
            status_code=503,
            detail="Agent is still initializing. Please retry in a moment.",
        )

    # Resolve thread_id from body first, then fall back to query param.
    resolved_thread_id = (body.thread_id if body else None) or thread_id
    if not resolved_thread_id:
        raise HTTPException(status_code=400, detail="thread_id is required.")

    checkpointer = graph.checkpointer
    delete = getattr(checkpointer, "adelete_thread", None) or getattr(
        checkpointer, "delete_thread", None
    )
    if delete is None:
        # Not all checkpointer implementations support deletion.
        # Return a graceful no-op instead of HTTP 501 so the UI doesn't break.
        logger.warning(
            f"{type(checkpointer).__name__} does not support thread deletion — "
            "memory reset skipped."
        )
        return ResetMemoryResponse(
            message="Memory reset is not supported by the current checkpointer."
        )

    try:
        result = delete(resolved_thread_id)
        if hasattr(result, "__await__"):
            await result
    except Exception as exc:
        logger.error(f"Failed to reset memory for thread {resolved_thread_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Failed to reset memory: {exc}")

    return ResetMemoryResponse(message="Memory reset successfully")


@app.post("/upload-video", response_model=VideoUploadResponse)
async def upload_video(file: UploadFile = File(...)):
    """
    Upload a video, replacing any existing file with the same name and
    invalidating its stale index (if one existed) so it gets re-processed.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    video_path = SHARED_MEDIA_DIR / file.filename
    # FIX (P1 - same filename doesn't replace existing video): the previous
    # implementation skipped writing entirely if a file with this name
    # already existed, so a re-upload under the same name kept serving the
    # old bytes while still reporting "success".
    replacing_existing = video_path.exists()

    try:
        with open(video_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        if replacing_existing:
            # The old file's Pixeltable index (if any) now points at stale
            # content. Drop it so the next /process-video call re-indexes
            # from scratch instead of short-circuiting on
            # VideoProcessor._check_if_exists(), which only reasons about
            # the path string and would otherwise happily reuse the old
            # embeddings for the new file.
            try:
                mcp_client = Client(settings.MCP_SERVER)
                async with mcp_client:
                    await mcp_client.call_tool("remove_video", {"video_path": str(video_path)})
            except Exception as e:
                logger.warning(f"Could not invalidate stale index for {video_path}: {e}")

        return VideoUploadResponse(
            message="Video uploaded successfully", video_path=str(video_path)
        )
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/videos/{video_name}")
async def delete_video(video_name: str):
    """
    Remove a video's index and its uploaded file from shared_media.

    FIX (P2 - removing a video from the UI doesn't remove backend/index
    data): the frontend used to only drop the video from its own React
    state, leaving the uploaded file and its Pixeltable index behind
    forever. This endpoint gives the UI a real deletion primitive to call.
    """
    # Path(...).name strips any directory components to prevent path traversal.
    video_path = SHARED_MEDIA_DIR / Path(video_name).name

    index_removed = False
    try:
        mcp_client = Client(settings.MCP_SERVER)
        async with mcp_client:
            result = await mcp_client.call_tool("remove_video", {"video_path": str(video_path)})
        index_removed = (not result.is_error) and bool(result.data)
    except Exception as e:
        logger.error(f"Error removing video index for {video_path}: {e}")

    file_removed = False
    if video_path.exists():
        video_path.unlink()
        file_removed = True

    return {"index_removed": index_removed, "file_removed": file_removed}


@app.get("/media/{file_path:path}")
async def serve_media(file_path: str):
    """
    Serve media files from the shared_media directory
    """
    try:
        clean_path = Path(file_path).name
        media_file = SHARED_MEDIA_DIR / clean_path

        if not media_file.exists():
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(str(media_file))
    except Exception as e:
        logger.error(f"Error serving media file {file_path}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@click.command()
@click.option("--port", default=8080, help="FastAPI server port")
@click.option("--host", default="0.0.0.0", help="FastAPI server host")
def run_api(port, host):
    import uvicorn

    uvicorn.run("multimodal_agent.api:app", host=host, port=port, loop="asyncio")


if __name__ == "__main__":
    run_api()
