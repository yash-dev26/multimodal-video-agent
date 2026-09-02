from langchain_mcp_adapters.client import MultiServerMCPClient
from multimodal_agent.config import get_settings

settings = get_settings()

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
        name: await mcp_client.get_prompt("video_mcp_server", name)
        for name in (
            "routing_system_prompt",
            "tool_use_system_prompt",
            "general_system_prompt",
        )
    }

    return mcp_tools, mcp_prompts