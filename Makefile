SHELL := /bin/bash

# Configuration
BACKEND_DIR = backend
FRONTEND_DIR = frontend
LOGS_DIR = logs
BACKEND_PORT = 8000
FRONTEND_PORT = 5173

.PHONY: help setup setup-backend setup-frontend start start-backend start-frontend stop stop-backend stop-frontend logs-dir up

up:
	docker compose up -d mongodb

down:
	docker compose down

help:
	@echo "Available commands:"
	@echo "  make setup          - Install dependencies for backend and frontend"
	@echo "  make start          - Start both backend and frontend"
	@echo "  make stop           - Stop both backend and frontend"
	@echo "  make setup-backend  - Install backend dependencies (using uv)"
	@echo "  make setup-frontend - Install frontend dependencies (using npm)"
	@echo "  make start-backend  - Start backend server"
	@echo "  make start-frontend - Start frontend server"
	@echo "  make stop-backend   - Stop backend server"
	@echo "  make stop-frontend  - Stop frontend server"
	@echo "  make up             - Start both backend and frontend"
	@echo "  make down           - Stop both backend and frontend"

logs-dir:
	@mkdir -p $(LOGS_DIR)

setup: setup-backend setup-frontend

setup-backend:
	@echo "Setting up backend..."
	cd $(BACKEND_DIR) && uv venv && source .venv/bin/activate && uv pip install -r requirements_prod.txt

setup-frontend:
	@echo "Setting up frontend..."
	cd $(FRONTEND_DIR) && npm install

start: logs-dir start-backend start-frontend

start-backend: logs-dir
	@echo "Starting backend..."
	@nohup bash -c "cd $(BACKEND_DIR) && source .venv/bin/activate && uvicorn app:app --host 0.0.0.0 --port $(BACKEND_PORT) --reload > ../$(LOGS_DIR)/backend.log 2>&1" & \
	echo "Backend starting on port $(BACKEND_PORT)... (logs in $(LOGS_DIR)/backend.log)"

start-frontend: logs-dir
	@echo "Starting frontend..."
	@nohup bash -c "cd $(FRONTEND_DIR) && npm run dev -- --port $(FRONTEND_PORT) > ../$(LOGS_DIR)/frontend.log 2>&1" & \
	echo "Frontend starting on port $(FRONTEND_PORT)... (logs in $(LOGS_DIR)/frontend.log)"

stop: stop-backend stop-frontend

stop-backend:
	@echo "Stopping backend on port $(BACKEND_PORT)..."
	@-lsof -ti:$(BACKEND_PORT) | xargs kill -9 2>/dev/null || echo "Backend not running"

stop-frontend:
	@echo "Stopping frontend on port $(FRONTEND_PORT)..."
	@-lsof -ti:$(FRONTEND_PORT) | xargs kill -9 2>/dev/null || echo "Frontend not running"
