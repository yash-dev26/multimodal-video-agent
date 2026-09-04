# multimodal_agent

FastAPI service that hosts "Rocky," the LangGraph-based conversational
agent. Routes user messages, decides whether a video tool is needed, calls
`video_mcp_server` over MCP when it is, and persists per-thread chat memory
in Postgres via a LangGraph checkpointer.

## Purpose & Responsibilities

- Expose the chat/video-processing HTTP API consumed by `frontend`.
- Build and run the LangGraph agent graph on startup (`lifespan`), which:
  - **routes** each turn (needs a tool, or a plain conversational reply?)
  - **calls MCP tools** on `video_mcp_server` to fetch clips or answer
    questions grounded in video content, injecting `video_path` /
    `image_base64` from server-side state rather than trusting the LLM
    with them
  - **finalizes** the response shape (plain text vs. text + clip path)
  - **trims** checkpointed message history to `AGENT_MEMORY_SIZE`
- Serve uploaded/generated video files from a shared media directory.
- Own the Postgres-backed conversation memory (one thread per
  conversation; supports reset).

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

## Local Run / Test / Build

```bash
pip install -r requirements.txt

# requires a reachable Postgres (see CHECKPOINTER_DB_URL) and
# video_mcp_server running (see MCP_SERVER, defaults to :9090 locally
# when not in Docker)
python run.py                 # cross-platform entrypoint (handles the
                               # Windows event-loop quirk); serves on :8080

# equivalent alternatives:
uvicorn multimodal_agent.api:app --host 0.0.0.0 --port 8080 --reload
python -m multimodal_agent.api --port 8080 --host 0.0.0.0   # via the click CLI
```

**Docker:**

```bash
docker build -t multimodal-agent .
docker run -p 8080:8080 --env-file .env multimodal-agent
```

No test suite is currently defined.

## API Endpoints

Interactive docs at `/docs` once running.

| Method & Path | Description |
|---|---|
| `GET /` | Welcome message |
| `GET /health` | Liveness/readiness — `ok` once the graph has finished building |
| `POST /chat` | Main chat turn. Body: `{message, video_path?, image_base64?, thread_id?}` → `{message, clip_path?, thread_id}`. Generates a `thread_id` if omitted; send it back on subsequent turns to keep memory. |
| `POST /upload-video` | Multipart file upload → `{message, video_path}`. Saves into the shared media directory. |
| `POST /process-video` | Body: `{video_path}`. Enqueues background indexing via the MCP `process_video` tool → `{message, task_id}`. |
| `GET /task-status/{task_id}` | `{task_id, status}` — one of `pending`, `in_progress`, `completed`, `failed`, `not_found`. |
| `POST /reset-memory` | Body `{thread_id}` or `?thread_id=` query param → deletes the checkpointed thread. No-op with a message if the checkpointer backend doesn't support deletion. |
| `GET /media/{file_path}` | Serves a file from the shared media directory by basename. |
| `GET /media/*` (mounted `StaticFiles`) | Direct static mount over the same directory. |

## Agent Graph (internal)

`router → {tool_agent → mcp_tools → tool_agent (loop) → finalize} | general_response → persist_memory`

Tools are discovered from `video_mcp_server` at startup via MCP
(`agent/mcp.py`); `process_video` is excluded from the chat tool-loop since
it's only reachable via `POST /process-video` directly.