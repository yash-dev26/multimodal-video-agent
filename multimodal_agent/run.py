# Windows does not support uvicorn's default event loop, so we need to use a different one.

import asyncio
import selectors
import sys

import uvicorn

if sys.platform == "win32":
    loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
    loop.run_until_complete(
        uvicorn.Server(
            uvicorn.Config(
                "multimodal_agent.api:app",
                host="0.0.0.0",
                port=8080,
            )
        ).serve()
    )
else:
    uvicorn.run(
        "multimodal_agent.api:app",
        host="0.0.0.0",
        port=8080,
    )
