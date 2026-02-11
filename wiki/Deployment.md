# Deployment

Guide for setting up and running the AI Dashboard locally or in production.

## Prerequisites
- **Python 3.13+** (managed via `uv`)
- **Node.js 18+** (managed via `pnpm`)
- **Docker** (for MongoDB session storage)

## Quick Start (Development)

1.  **Setup Environment**:
    ```bash
    cp backend/.env.example backend/.env
    # Edit backend/.env with your LLM API keys (OpenAI/Gemini)
    ```

2.  **Automated Setup**:
    ```bash
    make setup
    ```

3.  **Spin up Services**:
    ```bash
    make up    # Starts MongoDB
    make start # Starts FastAPI (8000) and Vite (5173)
    ```

## Makefile Commands Reference

| Command | Description |
| :--- | :--- |
| `make setup` | Installs all dependencies for both layers |
| `make up` | Starts Docker services (MongoDB) |
| `make start` | Starts dev servers for backend and frontend |
| `make logs` | Tails logs from both services |
| `make nuke` | Stops all services and clears volumes |
| `make wiki-setup` | Installs MkDocs using `uv` |
| `make wiki-serve` | Serves the documentation locally |
| `make wiki-build` | Builds the static documentation site |

## Production Notes
- Use `uvicorn` with multiple workers or a process manager like PM2.
- Ensure CORS settings in `backend/app.py` are restricted to your production domain.
- Use a persistent MongoDB instance instead of the short-lived Docker volume for session stability.
