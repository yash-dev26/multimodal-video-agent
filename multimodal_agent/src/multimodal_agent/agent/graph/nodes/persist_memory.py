"""
Bounds the checkpointed message history to AGENT_MEMORY_SIZE.

The checkpointer (agent/checkpointer.py) already persists `state["messages"]`
automatically after every node runs, because `graph.py` compiles with
`checkpointer=...`. This node's only job is to keep that persisted history
from growing without bound on a long-running thread.

`state["messages"]` uses the `add_messages` reducer (see state.py), which
merges/appends by message id rather than replacing the list outright — so
trimming requires emitting `RemoveMessage` objects rather than just
returning a shorter list. See:
https://langchain-ai.github.io/langgraph/how-tos/memory/delete-messages/
"""

from langchain_core.messages import RemoveMessage

from multimodal_agent.agent.state import AgentState
from multimodal_agent.config import get_settings

settings = get_settings()


def persist_memory_node(state: AgentState) -> dict:
    messages = state.get("messages", [])
    max_size = settings.AGENT_MEMORY_SIZE

    if len(messages) <= max_size:
        return {}

    overflow = messages[: len(messages) - max_size]
    removable = [RemoveMessage(id=m.id) for m in overflow if getattr(m, "id", None) is not None]

    return {"messages": removable} if removable else {}
