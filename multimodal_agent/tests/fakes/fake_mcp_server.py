"""
I7, I8, I9: agent-side video lifecycle endpoints (/process-video,
/task-status, /upload-video, DELETE /videos/{name}). These never touch the
LangGraph tool loop -- the app still boots the full graph at startup (see
patch_llms_noop), but no test in this file ever calls /chat.

Each upload-related test gets its own isolated shared_media directory
(via the autouse fixture below) so tests never collide with each other or
with a real repo checkout's shared_media/ contents. The task-status SQLite
file is intentionally NOT isolated per test -- it's harmless to share
(task_ids are UUIDs, and the schema is CREATE TABLE IF NOT EXISTS), and
isolating it would require patching a module-level Path computed once at
import time for no real benefit.
"""

import asyncio
import socket
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
import uvicorn
from fastmcp import FastMCP

from tests.helpers import patch_llms_noop


class MCPScript:
    def __init__(self):
        self.process_video_result = True
        self.calls: list[dict] = []

    def record(self, name: str, arguments: dict) -> None:
        self.calls.append({"name": name, **arguments})

    def calls_to(self, name: str) -> list[dict]:
        return [call for call in self.calls if call["name"] == name]


def _build_fake_mcp(script: MCPScript) -> FastMCP:
    mcp = FastMCP("FakeVideoProcessor")

    @mcp.tool(name="process_video")
    def process_video(video_path: str) -> bool:
        script.record("process_video", {"video_path": video_path})
        return script.process_video_result

    @mcp.tool(name="remove_video")
    def remove_video(video_path: str) -> bool:
        script.record("remove_video", {"video_path": video_path})
        return True

    @mcp.tool(name="get_video_clip_from_user_query")
    def get_video_clip_from_user_query(video_path: str, user_query: str) -> str:
        script.record("get_video_clip_from_user_query", {"video_path": video_path, "user_query": user_query})
        return ""

    @mcp.tool(name="get_video_clip_from_image")
    def get_video_clip_from_image(video_path: str, user_image: str) -> str:
        script.record("get_video_clip_from_image", {"video_path": video_path, "user_image": user_image})
        return ""

    @mcp.tool(name="ask_question_about_video")
    def ask_question_about_video(video_path: str, user_query: str) -> str:
        script.record("ask_question_about_video", {"video_path": video_path, "user_query": user_query})
        return ""

    @mcp.prompt(name="routing_system_prompt")
    def routing_system_prompt() -> str:
        return "Route the request."

    @mcp.prompt(name="tool_use_system_prompt")
    def tool_use_system_prompt() -> str:
        return "Use the available tools."

    @mcp.prompt(name="general_system_prompt")
    def general_system_prompt() -> str:
        return "Answer the user."

    return mcp


@asynccontextmanager
async def run_fake_mcp_server(script: MCPScript):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]

    server = uvicorn.Server(
        uvicorn.Config(
            _build_fake_mcp(script).http_app(transport="streamable-http"),
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
    )
    task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.01)
    try:
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        server.should_exit = True
        await task


@pytest.fixture(autouse=True)
def _isolated_shared_media(tmp_path, monkeypatch):
    import multimodal_agent.api as api_module

    media_dir = tmp_path / "shared_media"
    media_dir.mkdir()
    monkeypatch.setattr(api_module, "SHARED_MEDIA_DIR", media_dir)


async def _poll_until_settled(client, task_id: str, timeout_seconds: float = 5.0) -> str:
    elapsed = 0.0
    interval = 0.05
    while elapsed < timeout_seconds:
        resp = await client.get(f"/task-status/{task_id}")
        status = resp.json()["status"]
        if status in ("completed", "failed"):
            return status
        await asyncio.sleep(interval)
        elapsed += interval
    raise AssertionError(f"Task {task_id} did not settle within {timeout_seconds}s (still pending/in_progress)")


@pytest.mark.asyncio
async def test_process_video_failure_reports_failed(monkeypatch, make_client, mcp_script):
    """I7: regression test for the P0 bug -- a video whose MCP-side
    process_video call returns False (a clean failure, not an exception)
    must never be reported as `completed` by /task-status.
    """
    patch_llms_noop(monkeypatch)
    mcp_script.process_video_result = False

    async with make_client() as client:
        resp = await client.post("/process-video", json={"video_path": "shared_media/bad_video.mp4"})
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]

        status = await _poll_until_settled(client, task_id)

    assert status == "failed"


@pytest.mark.asyncio
async def test_reupload_same_filename_invalidates_index(monkeypatch, make_client, mcp_script):
    """I8: regression test for the P1 bug where re-uploading a filename
    that already existed silently kept the OLD file's bytes and left its
    (now stale) MCP index in place. Verifies both halves of the fix: the
    file is actually overwritten, AND remove_video is called exactly once,
    only on the second upload.
    """
    patch_llms_noop(monkeypatch)

    filename = "duplicate_name.mp4"

    async with make_client() as client:
        r1 = await client.post("/upload-video", files={"file": (filename, b"ORIGINAL BYTES", "video/mp4")})
        assert r1.status_code == 200
        video_path = r1.json()["video_path"]

        # First upload: nothing existed yet, remove_video must NOT be called.
        assert mcp_script.calls_to("remove_video") == []

        r2 = await client.post(
            "/upload-video", files={"file": (filename, b"REPLACED BYTES - LONGER CONTENT", "video/mp4")}
        )
        assert r2.status_code == 200
        assert r2.json()["video_path"] == video_path

    # The file on disk must be the new content, not the old.
    assert Path(video_path).read_bytes() == b"REPLACED BYTES - LONGER CONTENT"

    # remove_video called exactly once, for the second (overwriting) upload.
    remove_calls = mcp_script.calls_to("remove_video")
    assert len(remove_calls) == 1
    assert remove_calls[0]["video_path"] == video_path


@pytest.mark.asyncio
async def test_delete_video_cleans_file_and_index(monkeypatch, make_client, mcp_script):
    """I9: regression test for the P2 bug where removing a video from the
    UI only mutated local React state and never touched the backend -- the
    uploaded file and its MCP index lived on forever. Verifies
    DELETE /videos/{name} actually removes both.
    """
    patch_llms_noop(monkeypatch)

    filename = "to_be_deleted.mp4"

    async with make_client() as client:
        upload_resp = await client.post("/upload-video", files={"file": (filename, b"SOME VIDEO BYTES", "video/mp4")})
        video_path = upload_resp.json()["video_path"]
        assert Path(video_path).exists()

        delete_resp = await client.delete(f"/videos/{filename}")

    assert delete_resp.status_code == 200
    body = delete_resp.json()
    assert body["index_removed"] is True
    assert body["file_removed"] is True
    assert not Path(video_path).exists()

    remove_calls = mcp_script.calls_to("remove_video")
    assert len(remove_calls) == 1
    assert remove_calls[0]["video_path"] == video_path
