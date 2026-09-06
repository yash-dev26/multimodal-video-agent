"""
Builds and compiles the agent's LangGraph.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from multimodal_agent.agent.state import AgentState
from multimodal_agent.agent.graph.nodes.router import make_router_node
from multimodal_agent.agent.graph.nodes.general_response import make_general_response_node
from multimodal_agent.agent.graph.nodes.tool_agent import make_tool_agent_node
from multimodal_agent.agent.graph.nodes.finalize import make_finalize_node
from multimodal_agent.agent.graph.nodes.persist_memory import persist_memory_node
from multimodal_agent.agent.mcp import setup_mcp
from multimodal_agent.agent.llm import (
    build_routing_llm,
    build_tool_use_llm,
    build_general_llm,
    build_finalize_llm,
)

# Tools available directly via POST /process-video (and now DELETE /videos)
# shouldn't also be reachable through the chat tool-loop -- these are
# internal lifecycle operations, not something the chat LLM should invoke
# on its own initiative.
DISABLED_CHAT_TOOLS = {"process_video", "remove_video"}


async def build_graph(checkpointer):
    """
    Discover MCP tools/prompts and compile the agent graph.

    `checkpointer` must already be open (see checkpointer.py's
    checkpointer_context(), entered via an AsyncExitStack in api.py's
    lifespan) -- this function does not manage its lifecycle.

    Must be awaited inside a running event loop (FastAPI lifespan), not at
    import time -- see api.py.
    """
    mcp_tools, mcp_prompts = await setup_mcp()
    mcp_tools = [t for t in mcp_tools if getattr(t, "name", None) not in DISABLED_CHAT_TOOLS]

    router_node = make_router_node(build_routing_llm(), mcp_prompts["routing_system_prompt"])
    general_response_node = make_general_response_node(build_general_llm(), mcp_prompts["general_system_prompt"])
    tool_agent_node = make_tool_agent_node(
        build_tool_use_llm().bind_tools(mcp_tools),
        mcp_prompts["tool_use_system_prompt"],
    )
    finalize_node = make_finalize_node(build_finalize_llm())

    builder = StateGraph(AgentState)
    builder.add_node("router", router_node)
    builder.add_node("general_response", general_response_node)
    builder.add_node("tool_agent", tool_agent_node)
    builder.add_node("mcp_tools", ToolNode(mcp_tools))
    builder.add_node("finalize", finalize_node)
    builder.add_node("persist_memory", persist_memory_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        lambda s: "tool_agent" if s["needs_tool"] else "general_response",
    )
    builder.add_conditional_edges(
        "tool_agent",
        tools_condition,
        {
            "tools": "mcp_tools",
            END: "finalize",
        },
    )
    builder.add_edge("mcp_tools", "tool_agent")
    builder.add_edge("general_response", "persist_memory")
    builder.add_edge("finalize", "persist_memory")
    builder.add_edge("persist_memory", END)

    graph = builder.compile(checkpointer=checkpointer)
    return graph, mcp_prompts
