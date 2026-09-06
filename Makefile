.PHONY: build-project start-project stop-project

build-project:
	docker-compose build

start-project:
	docker-compose up -d

stop-project:
	docker-compose down