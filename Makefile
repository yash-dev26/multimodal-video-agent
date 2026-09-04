.PHONY: build-multimodal-frontend build-multimodal-mcp build-multimodal-agent build-all

build-multimodal-frontend:
	docker build -t multimodal-frontend ./frontend

build-multimodal-mcp:
	docker build -t video-mcp-server ./video_mcp_server

build-multimodal-agent:
	docker build -t multimodal-agent ./multimodal_agent

build-all: build-multimodal-frontend build-multimodal-mcp build-multimodal-agent
