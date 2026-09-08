from pydantic import BaseModel, Field


class ProcessVideoRequest(BaseModel):
    video_path: str


class ProcessVideoResponse(BaseModel):
    message: str
    task_id: str


class UserMessageRequest(BaseModel):
    message: str
    video_path: str | None = None
    image_base64: str | None = None
    # NEW (Phase 2): the client's conversation/session id. Omit it on the
    # first message of a conversation -- the server generates one and
    # returns it on AssistantMessageResponse.thread_id; send that same
    # value back on every subsequent turn to keep using the same
    # LangGraph checkpointer thread (memory). This replaces the old
    # `app.state.thread_id`, which was a single process-wide value shared
    # by every user.
    thread_id: str | None = None


class AssistantMessageResponse(BaseModel):
    message: str
    clip_path: str | None = None
    # NEW (Phase 2): echoes the thread_id used for this turn (the one the
    # caller sent, or a freshly generated one if they didn't send one) so
    # the client can persist it and continue the same conversation.
    thread_id: str


class ResetMemoryResponse(BaseModel):
    message: str


class ResetMemoryRequest(BaseModel):
    thread_id: str


class VideoUploadResponse(BaseModel):
    message: str
    video_path: str | None = None
    task_id: str | None = None


# -- LLM Structured Outputs Models --


class RoutingResponseModel(BaseModel):
    tool_use: bool = Field(description="Whether the user's question requires a tool call.")


class GeneralResponseModel(BaseModel):
    message: str = Field(
        description="Your response to the user's question, that needs to follow Rocky's style and personality"
    )


class VideoClipResponseModel(BaseModel):
    message: str = Field(
        description="A fun and engaging message to the user, asking them to watch the video clip, that needs to follow Rocky's style and personality"
    )
    clip_path: str = Field(description="The path to the generated clip.")
