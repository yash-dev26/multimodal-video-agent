"""
I1: real video_mcp_server tool/prompt contract test.

This is the one test in the whole suite that boots the ACTUAL, unmodified
server.py registration code (add_mcp_tools / add_mcp_prompts /
add_mcp_resources) rather than a fake -- it's the only thing that can
catch a tool renamed, removed, or misregistered in server.py, since the
agent and this service are two separate processes that share NO
compile-time interface between them.

Uses FastMCP's in-memory client transport (`Client(mcp)` with the real
FastMCP object, not a URL) rather than a real HTTP socket/subprocess --
that's still the real, unmodified tool/prompt registry, just without the
extra cost of standing up a real network listener, which the actual
regression this guards against (a tool name drifting out of sync with
what the agent expects) doesn't require.

Doesn't need a real OPENAI_API_KEY/LANGSMITH_API_KEY at runtime -- Settings
only validates the fields are *present* at import time, and tool/prompt
registration never calls either service. A placeholder is enough.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-placeholder")
os.environ.setdefault("LANGSMITH_API_KEY", "test-placeholder")
os.environ.setdefault("LANGSMITH_TRACING", "false")

import pytest
from fastmcp.client import Client

EXPECTED_TOOLS = {
    "process_video": {"video_path"},
    "remove_video": {"video_path"},
    "get_video_clip_from_user_query": {"video_path", "user_query"},
    "get_video_clip_from_image": {"video_path", "user_image"},
    "ask_question_about_video": {"video_path", "user_query"},
}

EXPECTED_PROMPTS = {"routing_system_prompt", "tool_use_system_prompt", "general_system_prompt"}


@pytest.fixture(scope="module")
def real_mcp_app():
    """The actual FastMCP app object built by server.py, imported fresh --
    exercises the real registration code, just over an in-memory transport
    instead of a real socket.
    """
    from video_mcp_server.server import mcp

    return mcp


@pytest.mark.asyncio
async def test_all_expected_tools_are_registered(real_mcp_app):
    async with Client(real_mcp_app) as client:
        tools = await client.list_tools()

    tool_names = {t.name for t in tools}
    assert tool_names == set(EXPECTED_TOOLS), (
        f"Registered tools {tool_names} don't match what multimodal_agent "
        f"depends on ({set(EXPECTED_TOOLS)}) -- the agent has no compile-time "
        f"way to catch a tool being renamed or removed in server.py."
    )


@pytest.mark.asyncio
async def test_tool_schemas_contain_the_args_the_agent_relies_on(real_mcp_app):
    async with Client(real_mcp_app) as client:
        tools = await client.list_tools()

    tools_by_name = {t.name: t for t in tools}
    for name, expected_args in EXPECTED_TOOLS.items():
        schema_props = set(tools_by_name[name].inputSchema.get("properties", {}).keys())
        missing = expected_args - schema_props
        assert not missing, f"Tool '{name}' is missing expected arg(s) {missing} in its schema"


@pytest.mark.asyncio
async def test_all_expected_prompts_are_registered(real_mcp_app):
    async with Client(real_mcp_app) as client:
        prompts = await client.list_prompts()

    assert {p.name for p in prompts} == EXPECTED_PROMPTS
