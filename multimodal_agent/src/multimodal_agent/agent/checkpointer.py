"""
Provides the LangGraph checkpointer as an async context manager, so its
connection pool's lifecycle is tied to the FastAPI app's own lifespan
instead of leaking or being torn down too early.

Usage (see api.py's lifespan):

    async with AsyncExitStack() as stack:
        checkpointer = await stack.enter_async_context(checkpointer_context())
        ...

On first startup this also runs the checkpointer's own `.setup()`, which
creates its tables if they don't exist yet -- idempotent, safe to run on
every startup.
"""

from contextlib import asynccontextmanager

from multimodal_agent.config import get_settings

settings = get_settings()


@asynccontextmanager
async def checkpointer_context():
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    if not settings.CHECKPOINTER_DB_URL:
        raise ValueError(
            "CHECKPOINTER_DB_URL must be set, e.g. "
            "postgresql://user:password@host:5432/dbname"
        )

    async with AsyncPostgresSaver.from_conn_string(settings.CHECKPOINTER_DB_URL) as saver:
        await saver.setup()
        yield saver