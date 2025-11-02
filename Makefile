.DEFAULT_GOAL := help

COMPOSE_FILE := docker-compose.yml

help:
	@echo "Available targets:"
	@echo "  docker-build    Build all container images"
	@echo "  docker-up       Start all services in the background"
	@echo "  docker-down     Stop services and remove containers"
	@echo "  docker-backend  Start only the backend service"
	@echo "  docker-frontend Start only the frontend service"
	@echo "  docker-logs     Tail logs for all services"
	@echo "  docker-config   Validate docker-compose configuration"

.PHONY: docker-build

docker-build:
	docker compose -f $(COMPOSE_FILE) build

.PHONY: docker-up

docker-up:
	docker compose -f $(COMPOSE_FILE) up -d

.PHONY: docker-down

docker-down:
	docker compose -f $(COMPOSE_FILE) down --remove-orphans

.PHONY: docker-backend

docker-backend:
	docker compose -f $(COMPOSE_FILE) up backend -d

.PHONY: docker-frontend

docker-frontend:
	docker compose -f $(COMPOSE_FILE) up frontend -d

.PHONY: docker-logs

docker-logs:
	docker compose -f $(COMPOSE_FILE) logs -f

.PHONY: docker-config

docker-config:
	docker compose -f $(COMPOSE_FILE) config 