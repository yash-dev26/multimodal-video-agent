from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]     # full chat turn history (checkpointed)
    video_path: Optional[str]
    image_base64: Optional[str]
    thread_id: str

    # routing
    needs_tool: Optional[bool]

    # tool-loop bookkeeping
    tool_call_count: int
    last_tool_name: Optional[str]

    # output shaping (mirrors your Pydantic response models)
    response_kind: Literal["general", "video_clip", None]
    clip_path: Optional[str]
    error: Optional[str]