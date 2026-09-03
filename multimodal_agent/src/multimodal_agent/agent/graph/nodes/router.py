"""
Router node: decides whether the user's message needs a tool call.

This is now a factory: `make_router_node(llm, routing_system_prompt)`
returns a real `(state) -> dict` node, closing over an LLM client and the
prompt text fetched from the MCP server at startup (see build_graph() in
graph.py) instead of reading them off `self`.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from multimodal_agent.agent.state import AgentState
from multimodal_agent.models import RoutingResponseModel


def make_router_node(llm, routing_system_prompt: str):
    structured_llm = llm.with_structured_output(RoutingResponseModel)

    def router_node(state: AgentState) -> dict:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None,
        )
        message_text = last_human.content if last_human is not None else ""

        response = structured_llm.invoke(
            [
                SystemMessage(content=routing_system_prompt),
                HumanMessage(content=message_text),
            ]
        )
        return {"needs_tool": response.tool_use}

    return router_node
