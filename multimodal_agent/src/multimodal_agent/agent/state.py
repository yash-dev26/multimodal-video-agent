from typing import Annotated, Literal

from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # full chat turn history (checkpointed)
    video_path: str | None
    image_base64: str | None
    thread_id: str

    # routing
    needs_tool: bool | None

    # tool-loop bookkeeping
    tool_call_count: int
    last_tool_name: str | None

    # output shaping (mirrors your Pydantic response models)
    response_kind: Literal["general", "video_clip", None]
    clip_path: str | None
    error: str | None
