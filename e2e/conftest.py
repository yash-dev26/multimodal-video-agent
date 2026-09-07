"""
Shared fixtures for the E2E suite. Unlike the integration tests, these run
against the REAL, full docker-compose stack (see .github/workflows/e2e.yml)
-- real Groq/OpenAI calls, real Pixeltable ingestion, real ffmpeg. No fakes
anywhere in this directory.
"""

from __future__ import annotations

import os

import httpx
import pytest


@pytest.fixture(scope="session")
def agent_base_url() -> str:
    return os.environ.get("AGENT_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def client(agent_base_url: str) -> httpx.Client:
    with httpx.Client(base_url=agent_base_url, timeout=30.0) as c:
        yield c
