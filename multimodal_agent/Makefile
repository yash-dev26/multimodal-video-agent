.PHONY: build run stop

build:
	docker build -t multimodal-agent .

run: stop
	docker run -it \
		-p 8080:8080 \
		--env-file .env \
		--name multimodal-agent \
		-v ./shared_media:/app/shared_media \
		multimodal-agent

stop:
	docker stop multimodal-agent 2>/dev/null || true
	docker rm multimodal-agent 2>/dev/null || true
