"""
Runs after the tool-use loop ends (the `tools_condition -> END` branch in
graph.py), before `persist_memory`.

This means a tool-based turn now costs two LLM calls minimum (one in
the tool loop to decide/execute tools, one here to produce the polished
final message)
"""

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from multimodal_agent.agent.state import AgentState
from multimodal_agent.models import GeneralResponseModel, VideoClipResponseModel

_GENERAL_REWRITE_PROMPT = (
    "Rewrite the following into your final answer to the user. Keep the "
    "same meaning and any facts -- just make sure it reads as a complete, "
    "well-formed reply."
)
_CLIP_REWRITE_PROMPT = (
    "A video clip was generated for the user based on the conversation "
    "below. Write a short, fun, engaging message inviting them to watch it."
)


def make_finalize_node(llm):
    general_structured = llm.with_structured_output(GeneralResponseModel)
    clip_structured = llm.with_structured_output(VideoClipResponseModel)

    def finalize_node(state: AgentState) -> dict:
        clip_path = state.get("clip_path")

        last_ai = next(
            (m for m in reversed(state["messages"]) if isinstance(m, AIMessage)),
            None,
        )
        raw_text = (last_ai.content if last_ai and last_ai.content else "").strip()

        if clip_path:
            structured: VideoClipResponseModel = clip_structured.invoke(
                [
                    SystemMessage(content=_CLIP_REWRITE_PROMPT),
                    HumanMessage(content=raw_text or f"A clip was generated at {clip_path}."),
                ]
            )
            # Force-set, never trust the model's own guess at the path --
            # same guarantee as kubrick-api's validate_video_clip_response.
            structured.clip_path = clip_path
            final_message = structured.message
        else:
            structured: GeneralResponseModel = general_structured.invoke(
                [
                    SystemMessage(content=_GENERAL_REWRITE_PROMPT),
                    HumanMessage(content=raw_text),
                ]
            )
            final_message = structured.message

        return {
            "response_kind": "video_clip" if clip_path else "general",
            "messages": [AIMessage(content=final_message)],
        }

    return finalize_node
