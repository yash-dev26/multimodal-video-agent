"""
Shared fixtures for multimodal_agent's integration test suite.

Every fixture here exists to make ONE thing possible: booting the real
FastAPI app (real lifespan, real LangGraph compilation, real Postgres
checkpointer, real MCP protocol calls) with zero real LLM API calls and
zero real video processing. See tests/fakes/ for how each of those two
axes is faked, and tests/helpers.py for how tests script the LLM side.

Requires a reachable Postgres (see TEST_CHECKPOINTER_DB_URL below) -- in
CI this is a native `services: postgres:` container; locally, point it at
whatever Postgres you have running (e.g. the one docker-compose.yml
already starts for the full stack).
"""

from __future__ import annotations

import os

# Settings (multimodal_agent.config.Settings) is validated at construction
# and cached via @lru_cache -- these must be set before ANYTHING under
# multimodal_agent is imported, by any test file, fixture, or plugin.
os.environ.setdefault("GROQ_API_KEY", "test-placeholder")
os.environ.setdefault("LANGSMITH_API_KEY", "test-placeholder")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGSMITH_PROJECT", "multimodal-agent-tests")
os.environ.setdefault("AGENT_MEMORY_SIZE", "20")
os.environ.setdefault(
    "CHECKPOINTER_DB_URL",
    os.environ.get(
        "TEST_CHECKPOINTER_DB_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres",
    ),
)
# Real value is set per-test by the `fake_mcp` fixture below; this default
# just needs to exist so Settings() doesn't fail before that happens.
os.environ.setdefault("MCP_SERVER", "http://127.0.0.1:1/mcp")

from contextlib import asynccontextmanager  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from asgi_lifespan import LifespanManager  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from tests.fakes.fake_mcp_server import MCPScript, run_fake_mcp_server  # noqa: E402


@pytest.fixture
def mcp_script() -> MCPScript:
    """The canned behavior/call-log for the fake MCP server. Mutate its
    fields before making a request to script a specific scenario (e.g.
    `mcp_script.process_video_result = False` for a failure test); read
    `.calls` / `.calls_to(...)` afterward to assert on what was invoked.
    """
    return MCPScript()


@pytest_asyncio.fixture
async def fake_mcp(mcp_script: MCPScript):
    """Runs the fake MCP server for the test and points the app's shared
    Settings singleton at it. Every module under multimodal_agent that
    reads MCP_SERVER does `settings = get_settings()` at import time, and
    get_settings() is @lru_cache'd -- so mutating the attribute on the
    SAME cached instance (rather than the environment, which nothing
    re-reads after import) reliably reaches api.py, agent/mcp.py, etc.
    regardless of import order.
    """
    from multimodal_agent.config import get_settings

    async with run_fake_mcp_server(mcp_script) as url:
        settings = get_settings()
        original = settings.MCP_SERVER
        settings.MCP_SERVER = url
        try:
            yield url
        finally:
            settings.MCP_SERVER = original


@pytest.fixture
def make_client(fake_mcp):
    """Returns an async context manager factory for a fresh, fully-booted
    FastAPI test client (real lifespan -> real build_graph() -> real
    Postgres checkpointer -> real MCP handshake with the fake server).

    Call this from INSIDE the test body, AFTER patching LLM factories via
    `patch_llms()` / `patch_llms_noop()` (see helpers.py) -- fixtures
    resolve before the test body runs, but build_graph() (and therefore
    the LLM factory calls) only happens once this context manager's
    lifespan actually starts.
    """

    @asynccontextmanager
    async def _make_client():
        from multimodal_agent.api import app

        async with LifespanManager(app) as manager:
            transport = ASGITransport(app=manager.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client

    return _make_client
