"""
Discovers tools and prompts from the video_mcp_server over MCP.
"""

from langchain_mcp_adapters.client import MultiServerMCPClient

from multimodal_agent.config import get_settings

settings = get_settings()


def _as_prompt_text(prompt_messages) -> str:
    if isinstance(prompt_messages, str):
        return prompt_messages
    if isinstance(prompt_messages, list) and prompt_messages:
        first = prompt_messages[0]
        return getattr(first, "content", str(first))
    return str(prompt_messages)


async def setup_mcp():
    mcp_client = MultiServerMCPClient({
        "video_mcp_server": {
            "transport": "http",
            "url": settings.MCP_SERVER,
        },
        # room to add more MCP servers later without touching agent code:
        # "transcription": {"transport": "http", "url": "..."},
    })

    mcp_tools = await mcp_client.get_tools()

    mcp_prompts = {
        name: _as_prompt_text(await mcp_client.get_prompt("video_mcp_server", name))
        for name in (
            "routing_system_prompt",
            "tool_use_system_prompt",
            "general_system_prompt",
        )
    }

    return mcp_tools, mcp_prompts
