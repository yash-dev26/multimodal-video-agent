"""
General-response node: answers directly, without any tool call.

Now a factory returning a proper `(state) -> dict` node.
"""

from langchain_core.messages import AIMessage, SystemMessage

from multimodal_agent.agent.state import AgentState
from multimodal_agent.models import GeneralResponseModel


def make_general_response_node(llm, general_system_prompt: str):
    structured_llm = llm.with_structured_output(GeneralResponseModel)

    def general_response_node(state: AgentState) -> dict:
        history = [SystemMessage(content=general_system_prompt), *state["messages"]]
        response = structured_llm.invoke(history)
        return {"messages": [AIMessage(content=response.message)]}

    return general_response_node
