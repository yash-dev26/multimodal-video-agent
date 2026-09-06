"""
Tool-use node: the ReAct-style loop that calls MCP tools (get a clip from a
query/image, ask a question about the video) and produces a follow-up
answer once the LLM stops requesting tools.

Design note: the LLM is never told the real `video_path` / `image_base64` —
those come from app state (the user's own upload), not something the model
should be trusted to supply an argument for — so this node injects them
into the tool call's args itself, after the LLM decides which tool to call
but before ToolNode executes it. 
"""

from typing import Any

from loguru import logger
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage

from multimodal_agent.agent.state import AgentState

# Tools whose return value is a clip file path, not a plain text answer
# (see video_mcp_server/tools.py — ask_question_about_video returns text).
CLIP_PRODUCING_TOOLS = {"get_video_clip_from_user_query", "get_video_clip_from_image"}

# Every video tool requires an actively selected/processed video_path.
# FIX (P1 - image query with no active/processed video enters a failure
# path): the router decides `needs_tool` purely from the message text and
# never checks whether a video is actually available, so without this
# guard a tool call for one of these would be dispatched with
# video_path=None and fail deep inside the MCP server's registry lookup
# (previously a raw TypeError; see registry.get_table's fix) instead of
# producing a clean, friendly response.
VIDEO_REQUIRED_TOOLS = CLIP_PRODUCING_TOOLS | {"ask_question_about_video"}


def _inject_context_args(tool_calls: list[dict], video_path: str | None, image_base64: str | None) -> list[dict]:
    """
    Fill in the args the LLM can't/shouldn't supply itself.

    All four MCP video tools take `video_path`; `get_video_clip_from_image`
    additionally takes `user_image`. Both come from the current turn's
    AgentState, not from anything the model generated.
    """
    updated = []
    for call in tool_calls:
        args = dict(call.get("args", {}))
        args["video_path"] = video_path
        if call.get("name") == "get_video_clip_from_image":
            args["user_image"] = image_base64
        updated.append({**call, "args": args})
    return updated


def _extract_tool_text(content: Any) -> str:
    """
    Normalize a ToolMessage's content down to a plain string.

    langchain_mcp_adapters can return either a plain string or a list of
    MCP content blocks (e.g. [{"type": "text", "text": "..."}]) depending
    on the MCP server's response shape. The video_mcp_server tools here all
    return plain `str`, but this stays defensive rather than assuming that
    never changes.
    """
    if isinstance(content, str):
        return content.strip().strip('"')
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return str(block.get("text", "")).strip().strip('"')
        return str(content)
    return str(content)


def _find_new_clip_path(messages: list) -> str | None:
    """
    Look at the most recent contiguous run of ToolMessages -- the ones
    ToolNode just appended before looping back to this node -- for a
    clip-producing tool's result.
    """
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            break  # walked past this round's tool results
        if message.name in CLIP_PRODUCING_TOOLS and getattr(message, "status", "success") != "error":
            return _extract_tool_text(message.content)
    return None


def make_tool_agent_node(llm_with_tools, tool_use_system_prompt: str):
    def tool_agent_node(state: AgentState) -> dict:
        updates: dict = {}

        new_clip_path = _find_new_clip_path(state["messages"])
        if new_clip_path:
            logger.info(f"Tool loop produced clip: {new_clip_path}")
            updates["clip_path"] = new_clip_path

        system_prompt = tool_use_system_prompt.format(is_image_provided=bool(state.get("image_base64")))
        history = [SystemMessage(content=system_prompt), *state["messages"]]

        response: AIMessage = llm_with_tools.invoke(history)

        if response.tool_calls:
            video_path = state.get("video_path")

            # A video-scoped tool call with no active video can never
            # succeed. Fail fast here with a friendly, on-persona message
            # instead of dispatching to ToolNode and hitting an error deep
            # inside the MCP server.
            missing_video_calls = [
                c["name"] for c in response.tool_calls if c["name"] in VIDEO_REQUIRED_TOOLS and not video_path
            ]
            if missing_video_calls:
                logger.info(
                    f"Skipping tool call(s) {missing_video_calls}: no active video selected."
                )
                updates["messages"] = [
                    AIMessage(
                        content="I don't have a video to search yet, Grace — please upload or select one first! Amaze!"
                    )
                ]
                return updates

            logger.info(f"Tool calls requested: {[c['name'] for c in response.tool_calls]}")
            response = response.model_copy(
                update={
                    "tool_calls": _inject_context_args(
                        response.tool_calls,
                        video_path=video_path,
                        image_base64=state.get("image_base64"),
                    )
                }
            )

        updates["messages"] = [response]
        return updates

    return tool_agent_node
