from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEFAULT_SHARED_MEDIA_DIR = Path(__file__).resolve().parents[3] / "shared_media"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")

    # GROQ Configuration
    GROQ_API_KEY: str
    GROQ_ROUTING_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_TOOL_USE_MODEL: str = "meta-llama/llama-4-maverick-17b-128e-instruct"
    GROQ_IMAGE_MODEL: str = "meta-llama/llama-4-maverick-17b-128e-instruct"
    GROQ_GENERAL_MODEL: str = "meta-llama/llama-4-maverick-17b-128e-instruct"

    # Langsmith Configuration
    LANGSMITH_API_KEY: str
    LANGSMITH_TRACING: bool
    LANGSMITH_PROJECT: str = "multimodal-video-agent"

    # Memory Configuration
    AGENT_MEMORY_SIZE: int = 20

    # MCP Configuration
    MCP_SERVER: str = "http://video-mcp-server:9090/mcp"

    # Checkpointer Configuration
    CHECKPOINTER_DB_URL: str

    # Shared video files used by the agent and video MCP server.
    SHARED_MEDIA_DIR: Path = _DEFAULT_SHARED_MEDIA_DIR

    # Disable Nest Asyncio
    DISABLE_NEST_ASYNCIO: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Get the application settings.

    Returns:
        Settings: The application settings.
    """
    return Settings()
