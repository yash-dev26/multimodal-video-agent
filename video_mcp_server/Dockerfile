FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
COPY src/ ./src/

# Install CPU-only PyTorch
RUN pip install --no-cache-dir torch \
    --index-url https://download.pytorch.org/whl/cpu

# Install the application and remaining dependencies
RUN pip install --no-cache-dir .

# Start MCP server
CMD ["python", "src/video_mcp_server/server.py", "--port", "9090", "--host", "0.0.0.0", "--transport", "streamable-http"]
