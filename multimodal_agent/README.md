# multimodal_agent

FastAPI service that hosts **Rocky**, the LangGraph-based conversational
agent. Routes user messages, decides whether a video tool is needed, calls
`video_mcp_server` over MCP when it is, and persists per-thread chat memory
in Postgres via a LangGraph checkpointer.

This service owns *conversation*, not *video processing* — it has no
Pixeltable, ffmpeg, or embedding-model dependency of its own. Every
video-aware capability is a tool discovered from `video_mcp_server` at
startup.

---

## Responsibilities

- Expose the chat/video-lifecycle HTTP API consumed by `frontend`.
- Build and run the LangGraph agent graph on startup (`lifespan`).
- Inject server-side state (`video_path`, `image_base64`) into tool calls
  itself, rather than trusting the LLM to supply them as arguments.
- Serve uploaded/generated video files from a shared media directory.
- Own Postgres-backed, per-thread conversation memory (supports reset).
- Track background video-processing jobs (`/process-video` →
  `/task-status/{id}`) in a durable store, independent of any single
  worker process.

---

## Agent execution graph

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1f2937','primaryTextColor':'#f3f4f6','primaryBorderColor':'#6b7280','lineColor':'#9ca3af','tertiaryColor':'#374151'}}}%%
flowchart TB
    START(["START<br/>/chat request"]) --> ROUTER

    ROUTER["**router**<br/>structured LLM call →<br/>RoutingResponseModel.tool_use"]

    ROUTER -- "needs_tool = false" --> GENERAL["**general_response**<br/>direct structured reply,<br/>Rocky persona system prompt"]

    ROUTER -- "needs_tool = true" --> TOOLAGENT

    subgraph loop["ReAct tool-use loop"]
        direction TB
        TOOLAGENT["**tool_agent**<br/>1. inject video_path / image_base64<br/>2. bind_tools LLM decides which tool(s)<br/>3. guards: no video → friendly bail-out"]
        MCPTOOLS["**mcp_tools** (ToolNode)<br/>get_video_clip_from_user_query<br/>get_video_clip_from_image<br/>ask_question_about_video<br/>— via video_mcp_server over MCP"]
        TOOLAGENT -- "tool_calls present" --> MCPTOOLS
        MCPTOOLS -- "ToolMessage(s)" --> TOOLAGENT
    end

    TOOLAGENT -- "no more tool_calls" --> FINALIZE["**finalize**<br/>rewrite raw tool output into a<br/>polished GeneralResponseModel or<br/>VideoClipResponseModel"]

    GENERAL --> PERSIST
    FINALIZE --> PERSIST

    PERSIST["**persist_memory**<br/>trim checkpointed history to<br/>AGENT_MEMORY_SIZE via RemoveMessage"]
    PERSIST --> FINISH(["END<br/>AssistantMessageResponse"])

    classDef node fill:#1f2937,stroke:#6b7280,color:#f3f4f6;
    classDef term fill:#0f172a,stroke:#334155,color:#94a3b8;
    class ROUTER,GENERAL,TOOLAGENT,MCPTOOLS,FINALIZE,PERSIST node;
    class START,FINISH term;
```

`process_video` and `remove_video` are deliberately **excluded** from this
tool-loop (`DISABLED_CHAT_TOOLS` in `graph.py`) — they're internal
lifecycle operations reachable only via `POST /process-video` and
`DELETE /videos/{name}` directly, never something the chat LLM should
invoke on its own initiative.

Every LangGraph node is a **factory function** (`make_router_node(llm,
prompt)`, etc.) closing over an LLM client and a prompt string fetched
from MCP at startup, rather than a class reading from `self` — so
`build_graph()` constructs each dependency exactly once per app lifetime.

---

## Request lifecycle

```mermaid
%%{init: {'theme':'base', 'themeVariables': {'primaryColor':'#1f2937','primaryTextColor':'#f3f4f6','primaryBorderColor':'#6b7280','lineColor':'#9ca3af'}}}%%
sequenceDiagram
    participant FE as frontend
    participant API as multimodal_agent API
    participant G as LangGraph
    participant MCP as video_mcp_server
    participant PG as Postgres (checkpointer)

    FE->>API: POST /upload-video (multipart)
    API-->>FE: {video_path}
    FE->>API: POST /process-video {video_path}
    API-->>FE: {task_id}
    API->>MCP: call_tool("process_video", {video_path})
    Note over API,MCP: background task — polled via /task-status/{task_id}
    MCP-->>API: bool (success/failure)

    FE->>API: POST /chat {message, video_path, thread_id?}
    API->>G: graph.ainvoke(state, thread_id)
    G->>PG: load checkpoint (prior messages)
    G->>G: router → tool_agent ⇄ mcp_tools → finalize
    G->>MCP: call_tool("get_video_clip_from_user_query", ...)
    MCP-->>G: clip path (written to shared_media)
    G->>PG: persist trimmed checkpoint
    G-->>API: {message, clip_path?, thread_id}
    API-->>FE: AssistantMessageResponse
    FE->>API: GET /media/{clip_filename}
```

---

## Dependencies & Environment Variables

Key dependencies (`requirements.txt`): `fastapi`, `uvicorn`, `langgraph`,
`langgraph-checkpoint-postgres`, `langchain-groq`, `langchain-mcp-adapters`,
`fastmcp`, `psycopg[binary,pool]`, `pydantic-settings`, `loguru`.

Environment variables (`.env`, see `.env.example`):

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GROQ_API_KEY` | yes | — | Auth for all ChatGroq LLM calls |
| `GROQ_ROUTING_MODEL` | no | `meta-llama/llama-4-scout-17b-16e-instruct` | Router node model |
| `GROQ_TOOL_USE_MODEL` | no | `meta-llama/llama-4-maverick-17b-128e-instruct` | Tool-use / finalize node model |
| `GROQ_IMAGE_MODEL` | no | `meta-llama/llama-4-maverick-17b-128e-instruct` | Reserved for image-capable calls |
| `GROQ_GENERAL_MODEL` | no | `meta-llama/llama-4-maverick-17b-128e-instruct` | General-response node model |
| `LANGSMITH_API_KEY` | yes | — | LangSmith tracing auth |
| `LANGSMITH_TRACING` | yes | — | `true`/`false` toggle for tracing |
| `LANGSMITH_PROJECT` | no | `multimodal-video-agent` | LangSmith project name |
| `AGENT_MEMORY_SIZE` | no | `20` | Max messages kept per checkpointed thread |
| `MCP_SERVER` | no | `http://video-mcp-server:9090/mcp` | `video_mcp_server` MCP endpoint |
| `CHECKPOINTER_DB_URL` | yes | — | Postgres connection string for chat memory |
| `DISABLE_NEST_ASYNCIO` | no | `true` | — |

---

## State schema (`agent/state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # checkpointed chat turn history
    video_path: Optional[str]
    image_base64: Optional[str]
    thread_id: str

    needs_tool: Optional[bool]  # set by router

    tool_call_count: int  # tool-loop bookkeeping
    last_tool_name: Optional[str]

    response_kind: Literal["general", "video_clip", None]
    clip_path: Optional[str]
    error: Optional[str]
```

`video_path` and `image_base64` come from the request body / server-side
context, never from the LLM — `tool_agent.py` injects them into a tool
call's `args` after the model decides *which* tool to call but before
`ToolNode` executes it, and short-circuits with a friendly message rather
than dispatching a video-scoped tool call when no video is active.

---

## API Endpoints

Interactive docs at `/docs` once running.

| Method & Path | Description |
|---|---|
| `GET /` | Welcome message |
| `GET /health` | Liveness/readiness — `ok` once the graph has finished building |
| `POST /chat` | Main chat turn. Body: `{message, video_path?, image_base64?, thread_id?}` → `{message, clip_path?, thread_id}`. Generates a `thread_id` if omitted; send it back on subsequent turns to keep memory. |
| `POST /upload-video` | Multipart file upload → `{message, video_path}`. Saves into the shared media directory, overwriting any existing file of the same name and invalidating its stale index if one existed. |
| `POST /process-video` | Body: `{video_path}`. Enqueues background indexing via the MCP `process_video` tool → `{message, task_id}`. |
| `GET /task-status/{task_id}` | `{task_id, status}` — one of `pending`, `in_progress`, `completed`, `failed`, `not_found`. Backed by a durable on-disk store, not process memory. |
| `DELETE /videos/{video_name}` | Removes a video's Pixeltable index (via the MCP `remove_video` tool) and its file from shared media. → `{index_removed, file_removed}`. |
| `POST /reset-memory` | Body `{thread_id}` or `?thread_id=` query param → deletes the checkpointed thread. No-op with a message if the checkpointer backend doesn't support deletion. |
| `GET /media/{file_path}` | Serves a file from the shared media directory by basename. |
| `GET /media/*` (mounted `StaticFiles`) | Direct static mount over the same directory. |

---

## Local Run / Test / Build

```bash
pip install -r requirements.txt

# install test dependencies when working from this service directory
pip install -e ".[test]"

# fast unit tests; no Postgres or running MCP server required
pytest tests/unit -q

# integration tests; requires a reachable Postgres checkpointer
docker compose up -d postgres
# PowerShell: $env:TEST_CHECKPOINTER_DB_URL = "postgresql://multimodal_agent:multimodal_agent@localhost:5432/multimodal_agent"
# macOS/Linux: export TEST_CHECKPOINTER_DB_URL="postgresql://multimodal_agent:multimodal_agent@localhost:5432/multimodal_agent"
pytest tests/integration -q

# run the complete service suite
pytest -q

# requires a reachable Postgres (see CHECKPOINTER_DB_URL) and
# video_mcp_server running (see MCP_SERVER, defaults to :9090 locally
# when not in Docker)
python run.py                 # cross-platform entrypoint (handles the
                               # Windows event-loop quirk); serves on :8080

# equivalent alternatives:
uvicorn multimodal_agent.api:app --host 0.0.0.0 --port 8080 --reload
python -m multimodal_agent.api --port 8080 --host 0.0.0.0   # via the click CLI
```

**Via Makefile (standalone Docker workflow):**

```bash
make build      # docker build -t multimodal-agent .
make run        # runs the container on :8080, mounts ./shared_media,
                 # stops+removes any existing container first
make stop       # stops/removes the container
```

The integration tests use a fake MCP server, but still boot the real FastAPI
lifespan, LangGraph graph, and Postgres checkpointer. They do not require real
Groq or video-processing calls; test credentials are supplied by
`tests/conftest.py`. Set `TEST_CHECKPOINTER_DB_URL` when your local Postgres
uses a different connection string.

> For the full stack (Postgres + `video_mcp_server` + this service +
> `frontend` together), use the root [`Makefile`](../README.md#-quickstart)
> instead (`make start-project` / `make dev-project` from the repo root).