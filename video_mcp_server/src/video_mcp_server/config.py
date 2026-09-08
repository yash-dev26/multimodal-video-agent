from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# src/video_mcp_server/config.py -> video_mcp_server/.env
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore", env_file_encoding="utf-8")

    SHARED_MEDIA_DIR: Path = Path(__file__).resolve().parents[3] / "shared_media"

    # LANGSMITH Configuration
    LANGSMITH_API_KEY: str
    LANGSMITH_TRACING: bool
    LANGSMITH_PROJECT: str = "multimodal-video-mcp"

    # OPENAI Configuration
    OPENAI_API_KEY: str
    AUDIO_TRANSCRIPT_MODEL: str = "gpt-transcribe"
    IMAGE_CAPTION_MODEL: str = "gpt-4o-mini"

    # Video Ingestion Configuration
    SPLIT_FRAMES_COUNT: int = 45  # keeps the cost low and the number of frames manageable for processing when videos are shorter.
    AUDIO_CHUNK_LENGTH: int = 10
    AUDIO_OVERLAP_SECONDS: int = 1
    AUDIO_MIN_CHUNK_DURATION_SECONDS: int = 1  # If an audio chunk is left and the audio chunk is shorter than this duration, it will be skipped to avoid processing very short audio segments.

    # Transcription Similarity Search Configuration
    TRANSCRIPT_SIMILARITY_EMBD_MODEL: str = "text-embedding-3-small"

    # Image Similarity Search Configuration
    IMAGE_SIMILARITY_EMBD_MODEL: str = "openai/clip-vit-base-patch32"

    # Image Captioning Configuration : for cost savings because VLMs use patches to process images which are encoded and sent to the model, so resizing the image to a smaller size can reduce the number of patches and thus reduce the cost of processing the image.
    IMAGE_RESIZE_WIDTH: int = 1024
    IMAGE_RESIZE_HEIGHT: int = 768
    CAPTION_SIMILARITY_EMBD_MODEL: str = "text-embedding-3-small"

    # Caption Similarity Search Configuration
    CAPTION_MODEL_PROMPT: str = "Describe what is happening in the image"

    # The time interval in seconds to extend before and after the frame's timestamp when searching for video clips based on image similarity.
    # This allows for a broader context around the matched frame, capturing relevant video segments that may not be exactly at the frame's timestamp but are still contextually related.
    DELTA_SECONDS_FRAME_INTERVAL: float = 5.0

    # Video Search Engine Configuration
    VIDEO_CLIP_SPEECH_SEARCH_TOP_K: int = 1
    VIDEO_CLIP_CAPTION_SEARCH_TOP_K: int = 1
    VIDEO_CLIP_IMAGE_SEARCH_TOP_K: int = 1
    QUESTION_ANSWER_TOP_K: int = 3


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the application settings.

    Returns:
        Settings: The application settings.
    """
    return Settings()
