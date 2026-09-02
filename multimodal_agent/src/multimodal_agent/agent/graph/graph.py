from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition

from multimodal_agent.agent.state import AgentState
from multimodal_agent.agent.graph.nodes.router import _should_use_tool as router_node
from multimodal_agent.agent.graph.nodes.general_response import _respond_general as general_response_node
from multimodal_agent.agent.graph.nodes.tool_agent import tool_agent_node
from multimodal_agent.agent.graph.nodes.finalize import finalize_node
from multimodal_agent.agent.graph.nodes.persist_memory import persist_memory_node
from multimodal_agent.agent.mcp import setup_mcp

mcp_tools = setup_mcp()

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
builder.add_conditional_edges("tool_agent", tools_condition, {
    "tools": "mcp_tools",
    END: "finalize",
})
builder.add_edge("mcp_tools", "tool_agent")   # loop back — the real upgrade
builder.add_edge("general_response", "persist_memory")
builder.add_edge("finalize", "persist_memory")
builder.add_edge("persist_memory", END)

graph = builder.compile(checkpointer=checkpointer)