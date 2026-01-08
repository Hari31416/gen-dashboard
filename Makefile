SHELL := /bin/bash

# Configuration
BACKEND_DIR = backend
FRONTEND_DIR = frontend
LOGS_DIR = logs
BACKEND_PORT = 8000
FRONTEND_PORT = 5173

.PHONY: help setup backend-setup frontend-setup start backend-start frontend-start stop backend-stop frontend-stop logs-dir up

up:
	docker compose up -d mongodb

down:
	docker compose down

help:
	@echo "Available commands:"
	@echo "  make setup          - Install dependencies for backend and frontend"
	@echo "  make start          - Start both backend and frontend"
	@echo "  make stop           - Stop both backend and frontend"
	@echo "  make backend-setup  - Install backend dependencies (using uv)"
	@echo "  make frontend-setup - Install frontend dependencies (using pnpm)"
	@echo "  make backend-start  - Start backend server"
	@echo "  make frontend-start - Start frontend server"
	@echo "  make backend-stop   - Stop backend server"
	@echo "  make frontend-stop  - Stop frontend server"
	@echo "  make up             - Start both backend and frontend"
	@echo "  make down           - Stop both backend and frontend"

logs-dir:
	@mkdir -p $(LOGS_DIR)

setup: backend-setup frontend-setup

backend-setup:
	@echo "Setting up backend..."
	cd $(BACKEND_DIR) && uv sync

frontend-setup:
	@echo "Setting up frontend..."
	cd $(FRONTEND_DIR) && pnpm install

start: logs-dir backend-start frontend-start

backend-start: logs-dir
	@echo "Starting backend..."
	@nohup bash -c "cd $(BACKEND_DIR) && uv run uvicorn app:app --host 0.0.0.0 --port $(BACKEND_PORT) --reload > ../$(LOGS_DIR)/backend.log 2>&1" & \
	echo "Backend starting on port $(BACKEND_PORT)... (logs in $(LOGS_DIR)/backend.log)"

frontend-start: logs-dir
	@echo "Starting frontend..."
	@nohup bash -c "cd $(FRONTEND_DIR) && pnpm run dev -- --port $(FRONTEND_PORT) > ../$(LOGS_DIR)/frontend.log 2>&1" & \
	echo "Frontend starting on port $(FRONTEND_PORT)... (logs in $(LOGS_DIR)/frontend.log)"

stop: backend-stop frontend-stop
backend-stop:
	@echo "Stopping backend on port $(BACKEND_PORT)..."
	@-lsof -ti:$(BACKEND_PORT) | xargs kill -9 2>/dev/null || echo "Backend not running"

frontend-stop:
	@echo "Stopping frontend on port $(FRONTEND_PORT)..."
	@-lsof -ti:$(FRONTEND_PORT) | xargs kill -9 2>/dev/null || echo "Frontend not running"
