# E2E tests run against the real, full docker-compose stack (real Groq/
# OpenAI/embedding calls) -- see .github/workflows/e2e.yml, triggered
# manually only. Kept deliberately separate from either service's own
# requirements-test.txt since this suite talks to the stack over HTTP,
# not to either service's Python package directly.
pytest
httpx
