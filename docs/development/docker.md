# Docker Infrastructure

The **AI Dashboard** relies on Docker containers to provide consistent runtime environments across local development and production deployments.

---

## 1. Local Session Storage Container (`docker-compose.yml`)

To support stateful operations like dashboard refinement and refresh caching without requiring a host-installed database, the root folder provides a containerized MongoDB setup:

```yaml
services:
  mongodb:
    image: mongo:latest
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_DATABASE: ai_dashboard

volumes:
  mongodb_data:
```

### Usage
- `make up`: Boots the storage instance in the background.
- `make down`: Terminates the container instance while preserving volume state.

---

## 2. Backend Containerization (`backend/Dockerfile`)

For production hosting, the backend service compiles into an optimized container format:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Copy application configuration locks
COPY pyproject.toml uv.lock ./

# Install application dependencies via `uv`
RUN pip install uv && uv sync --frozen

# Copy source assets into target layer
COPY . .

# Expose gateway port
EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```
