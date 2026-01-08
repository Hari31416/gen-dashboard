# Dockerfile
FROM python:3.11-slim

# Prevent Python from writing .pyc files & enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency definitions
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN uv sync --frozen --no-cache

# Clean up uv cache to reduce image size
RUN rm -rf /root/.cache/uv

# Add venv to path
ENV PATH="/app/.venv/bin:$PATH"

# Copy app code
COPY . .

# Make startup scripts executable
EXPOSE 8016

# Use uv run to start the app
CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8016", "--loop", "asyncio"]
