import os

from loguru import logger

from video_mcp_server.config import get_settings

settings = get_settings()


def configure() -> None:
    if settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY and settings.LANGSMITH_PROJECT:
        os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT
        os.environ["LANGSMITH_TRACING"] = "true"

        logger.info(
            f"LangSmith configured successfully for project "
            f"'{settings.LANGSMITH_PROJECT}'"
        )
    else:
        logger.warning(
            "LANGSMITH_API_KEY and LANGSMITH_PROJECT are not set. "
            "Set them to enable LangSmith tracing."
        )