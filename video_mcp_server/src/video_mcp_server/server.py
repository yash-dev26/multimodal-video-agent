import click
from fastmcp import FastMCP
from fastmcp.prompts import Prompt
from fastmcp.resources import FunctionResource
from fastmcp.tools import Tool

from video_mcp_server.langsmith_utils import configure as configure_langsmith
from video_mcp_server.prompts import (
    general_system_prompt,
    routing_system_prompt,
    tool_use_system_prompt,
)
from video_mcp_server.resources import list_tables
from video_mcp_server.tools import (
    ask_question_about_video,
    get_video_clip_from_image,
    get_video_clip_from_user_query,
    process_video,
    remove_video,
)


def add_mcp_tools(mcp: FastMCP) -> None:
    mcp.add_tool(
        Tool.from_function(
            fn=process_video,
            name="process_video",
            description="Process a video file and prepare it for searching.",
            tags={"video", "process"},
        )
    )
    mcp.add_tool(
        Tool.from_function(
            fn=remove_video,
            name="remove_video",
            description="Drop a video's cached index so it will be fully re-processed next time.",
            tags={"video", "remove"},
        )
    )
    mcp.add_tool(
        Tool.from_function(
            fn=get_video_clip_from_user_query,
            name="get_video_clip_from_user_query",
            description="Use this tool to get a video clip from a video file based on a user query or question.",
            tags={"video", "clip", "query", "question"},
        )
    )
    mcp.add_tool(
        Tool.from_function(
            fn=get_video_clip_from_image,
            name="get_video_clip_from_image",
            description="Use this tool to get a video clip from a video file based on a user image.",
            tags={"video", "clip", "image"},
        )
    )
    mcp.add_tool(
        Tool.from_function(
            fn=ask_question_about_video,
            name="ask_question_about_video",
            description="Use this tool to get an answer to a question about the video.",
            tags={"ask", "question", "information"},
        )
    )


def add_mcp_resources(mcp: FastMCP) -> None:
    mcp.add_resource(
        FunctionResource.from_function(
            fn=list_tables,
            uri="file:///app/.records/records.json",
            name="list_tables",
            description="List all video indexes currently available.",
            tags={"resource", "all"},
        )
    )


def add_mcp_prompts(mcp: FastMCP) -> None:
    mcp.add_prompt(
        Prompt.from_function(
            fn=routing_system_prompt,
            name="routing_system_prompt",
            description="Latest version of the routing prompt from LangSmith.",
            tags={"prompt", "routing"},
        )
    )
    mcp.add_prompt(
        Prompt.from_function(
            fn=tool_use_system_prompt,
            name="tool_use_system_prompt",
            description="Latest version of the tool use prompt from LangSmith.",
            tags={"prompt", "tool_use"},
        )
    )
    mcp.add_prompt(
        Prompt.from_function(
            fn=general_system_prompt,
            name="general_system_prompt",
            description="Latest version of the general prompt from LangSmith.",
            tags={"prompt", "general"},
        )
    )


configure_langsmith()

mcp = FastMCP("VideoProcessor")

add_mcp_prompts(mcp)
add_mcp_tools(mcp)
add_mcp_resources(mcp)


@click.command()
@click.option("--port", default=9090, help="FastMCP server port")
@click.option("--host", default="0.0.0.0", help="FastMCP server host")
@click.option("--transport", default="streamable-http", help="MCP Transport protocol type")
def run_mcp(port, host, transport):
    """Run the FastMCP server with the specified port, host, and transport protocol."""
    mcp.run(host=host, port=port, transport=transport)


if __name__ == "__main__":
    run_mcp()
