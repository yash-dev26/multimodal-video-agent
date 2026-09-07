.PHONY: build-project start-project stop-project dev-project restart-project logs-project ps-project clean-project

build-project:
	docker-compose build

start-project:
	docker-compose up -d

stop-project:
	docker-compose down

# Foreground stack with live interleaved logs — the everyday inner-loop
# command while iterating on any service.
dev-project:
	docker-compose up --build

restart-project: stop-project start-project

# Stream logs from every running service (Ctrl+C to detach; does not stop anything).
logs-project:
	docker-compose logs -f

# Show container status for the stack.
ps-project:
	docker-compose ps

# Full teardown: stop the stack AND drop volumes. This wipes Postgres data
# (chat memory) and shared_media (clips), and forces every video to be
# re-indexed from scratch on the next `make start-project`.
clean-project:
	docker-compose down -v