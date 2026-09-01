.PHONY: build run stop inspect

build:
	docker build -t video-mcp-server .

run: stop
	docker run -it \
		-p 9090:9090 \
		--env-file .env \
		--name video-mcp-server \
		-v ./data:/app/videos \
		-v ./.pixeltable:/root/.pixeltable \
		-v ./.records:/app/.records \
		-v ~/.cache/huggingface:/root/.cache/huggingface \
		video-mcp-server

stop:
	docker stop video-mcp-server 2>/dev/null || true
	docker rm video-mcp-server 2>/dev/null || true
	rm -rf .pixeltable .records

inspect:
	npx @modelcontextprotocol/inspector@latest