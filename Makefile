.PHONY: help build up down logs clean dev dev-down test

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)TumorBoard Docker Commands$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

build: ## Build production images
	@echo "$(BLUE)Building production images...$(NC)"
	docker-compose build

up: ## Start production containers
	@echo "$(BLUE)Starting production containers...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Application started!$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost$(NC)"
	@echo "$(YELLOW)Backend API: http://localhost:5000$(NC)"

down: ## Stop production containers
	@echo "$(BLUE)Stopping containers...$(NC)"
	docker-compose down

logs: ## View logs
	docker-compose logs -f

logs-backend: ## View backend logs only
	docker-compose logs -f backend

logs-frontend: ## View frontend logs only
	docker-compose logs -f frontend

ps: ## Show running containers
	docker-compose ps

dev: ## Start development environment
	@echo "$(BLUE)Starting development environment...$(NC)"
	docker-compose -f docker-compose.dev.yml up
	@echo "$(GREEN)✓ Development servers started!$(NC)"
	@echo "$(YELLOW)Frontend: http://localhost:4200$(NC)"
	@echo "$(YELLOW)Backend: http://localhost:5000$(NC)"

dev-build: ## Build development images
	@echo "$(BLUE)Building development images...$(NC)"
	docker-compose -f docker-compose.dev.yml build

dev-up: ## Start development containers (detached)
	@echo "$(BLUE)Starting development containers...$(NC)"
	docker-compose -f docker-compose.dev.yml up -d
	@echo "$(GREEN)✓ Development environment started!$(NC)"

dev-down: ## Stop development containers
	@echo "$(BLUE)Stopping development containers...$(NC)"
	docker-compose -f docker-compose.dev.yml down

restart: ## Restart production containers
	@echo "$(BLUE)Restarting containers...$(NC)"
	docker-compose restart
	@echo "$(GREEN)✓ Containers restarted!$(NC)"

clean: ## Stop containers and remove volumes
	@echo "$(BLUE)Cleaning up...$(NC)"
	docker-compose down -v
	@echo "$(GREEN)✓ Cleanup complete!$(NC)"

clean-all: ## Remove all images, containers, and volumes
	@echo "$(YELLOW)WARNING: This will remove all TumorBoard Docker resources!$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		docker-compose down -v --rmi all; \
		echo "$(GREEN)✓ All resources removed!$(NC)"; \
	fi

health: ## Check container health
	@echo "$(BLUE)Checking container health...$(NC)"
	@docker-compose ps
	@echo ""
	@echo "$(BLUE)Backend health:$(NC)"
	@curl -s http://localhost:5000/api/health | jq '.' || echo "Backend not responding"
	@echo ""
	@echo "$(BLUE)Frontend health:$(NC)"
	@curl -s http://localhost/health || echo "Frontend not responding"

shell-backend: ## Open shell in backend container
	docker-compose exec backend /bin/bash

shell-frontend: ## Open shell in frontend container
	docker-compose exec frontend /bin/sh

test-api: ## Test API endpoints
	@echo "$(BLUE)Testing API endpoints...$(NC)"
	@curl -s http://localhost:5000/api/health | jq '.'
	@echo ""
	@echo "$(BLUE)Testing variant assessment...$(NC)"
	@curl -X POST http://localhost:5000/api/assess \
		-H "Content-Type: application/json" \
		-d '{"gene":"BRAF","variant":"V600E","tumor_type":"Melanoma"}' \
		| jq '.assessment'

stats: ## Show container resource usage
	docker stats --no-stream

rebuild: down build up ## Rebuild and restart all containers

deploy: ## Deploy to production
	@echo "$(YELLOW)Deploying to production...$(NC)"
	@echo "$(BLUE)1. Building images...$(NC)"
	docker-compose build --no-cache
	@echo "$(BLUE)2. Starting containers...$(NC)"
	docker-compose up -d
	@echo "$(BLUE)3. Checking health...$(NC)"
	@sleep 5
	@make health
	@echo "$(GREEN)✓ Deployment complete!$(NC)"
