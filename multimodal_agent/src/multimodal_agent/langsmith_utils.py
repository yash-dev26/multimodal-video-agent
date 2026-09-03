"""
Configures LangSmith tracing.
"""

import os

from loguru import logger

from multimodal_agent.config import get_settings

settings = get_settings()


def configure() -> None:
    """
    Configure LangSmith tracing.
    """
    if not settings.LANGSMITH_TRACING:
        logger.warning(
            "LANGSMITH_TRACING is disabled -- set LANGSMITH_TRACING=true and "
            "LANGSMITH_API_KEY to enable tracing."
        )
        return

    if not settings.LANGSMITH_API_KEY:
        logger.warning("LANGSMITH_TRACING=true but LANGSMITH_API_KEY is not set -- tracing will not start.")
        return

    # LANGCHAIN_* is what langchain-core's tracing callback manager actually
    # checks to decide whether to attach a tracer to every run.
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT

    # Newer langsmith SDK releases also read the LANGSMITH_* names directly.
    # Setting both isn't redundant guesswork -- it's forward-compatible
    # without depending on exactly one being "the" supported path.
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT

    logger.info(f"LangSmith tracing configured for project '{settings.LANGSMITH_PROJECT}'")
