FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app/src

# Matches the shared_media/ convention video_mcp_server's tools.py already
# writes clips to (relative "./shared_media/{uuid}.mp4"). docker-compose.yml
# mounts a shared volume at this same path in both containers so a clip
# video_mcp_server produces is immediately servable by this app's /media
# route without copying anything between containers.
RUN mkdir -p shared_media

EXPOSE 8080

CMD ["uvicorn", "multimodal_agent.api:app", "--host", "0.0.0.0", "--port", "8080"]