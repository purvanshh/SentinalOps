COMPOSE ?= docker compose

.PHONY: up down logs test api-shell

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

test:
	cd apps/api-server && pytest

api-shell:
	$(COMPOSE) exec api-server /bin/bash
