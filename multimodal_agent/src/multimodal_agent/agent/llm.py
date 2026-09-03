"""
Factory functions for the LangChain chat models the agent nodes use.

Centralizing these keeps model construction (auth, model name, temperature)
in one place, and lets `build_graph()` (graph.py) construct them once per
app lifetime instead of each node reaching for a client on every call.
"""

from langchain_groq import ChatGroq

from multimodal_agent.config import get_settings

settings = get_settings()


def build_routing_llm() -> ChatGroq:
    # temperature=0: this is a binary classification call (needs_tool),
    # not something that benefits from sampling variety.
    return ChatGroq(model=settings.GROQ_ROUTING_MODEL, api_key=settings.GROQ_API_KEY, temperature=0)


def build_tool_use_llm() -> ChatGroq:
    return ChatGroq(model=settings.GROQ_TOOL_USE_MODEL, api_key=settings.GROQ_API_KEY, temperature=0)


def build_general_llm() -> ChatGroq:
    return ChatGroq(model=settings.GROQ_GENERAL_MODEL, api_key=settings.GROQ_API_KEY)


def build_finalize_llm() -> ChatGroq:
    return ChatGroq(model=settings.GROQ_TOOL_USE_MODEL, api_key=settings.GROQ_API_KEY)
