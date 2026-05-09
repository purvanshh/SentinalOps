COMPOSE ?= docker compose

.PHONY: up down logs test api-shell dev migrate replay-pending

up:
	$(COMPOSE) up --build

dev:
	$(COMPOSE) up --build api-server celery-worker celery-beat web-dashboard postgres redis qdrant prometheus grafana loki

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

test:
	cd apps/api-server && pytest

api-shell:
	$(COMPOSE) exec api-server /bin/bash

migrate:
	$(COMPOSE) run --rm migrations

replay-pending:
	$(COMPOSE) exec celery-worker celery -A workers.queues.celery_app call workers.tasks.replay_pending_incidents
