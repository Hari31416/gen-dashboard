# AI Dashboard

A powerful, agentic AI-powered dashboard generator that converts natural language requests into fully functional, interactive, and aesthetically pleasing data dashboards.

## Overview

The **AI Dashboard** leverages a sophisticated **multi-agent pipeline** to automate the end-to-end process of data visualization. It translates user queries (e.g., "Show me sales trends for Q3 compared to last year") into SQL queries, executes them securely, generates Vega-Lite visualization specifications, and intelligently composes them into a responsive layout.

### Key Features

- **Natural Language to Dashboard**: Just ask for what you want to see.
- **Multi-Agent Architecture**: A 4-stage pipeline (Strategy, Data, Viz Spec, Layout) ensures high-quality, reasoned outputs.
- **Interactive Visualizations**: Powered by **Vega-Lite** for rich, interactive charts.
- **Drill-Down & Refinement**: Click on charts to filter data or ask follow-up questions to refine the dashboard.
- **Secure SQL Execution**: Built-in sanitization and validation to prevent unsafe database operations.
- **Modern UI**: A responsive, "dark mode" aesthetic built with React and Tailwind CSS.

## Architecture

The system is built on a robust modern stack:

### Backend

- **FastAPI**: High-performance async API framework.
- **LangGraph / LangChain**: Orchestrates the sequential agent workflow.
- **LLMs**: Powered by OpenAI (GPT-4o) or Google Gemini.
- **SQLAlchemy**: Database ORM for secure data access.
- **Pydantic**: Enforcing strict schema validation for all agent outputs.

### Frontend

- **React**: Component-based UI library.
- **Vite**: Fast build tool and dev server.
- **Tailwind CSS**: Utility-first styling framework.
- **Vega-Embed**: Embedding Vega-Lite visualizations.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13+**
- **Node.js 18+** & **pnpm**
- **Docker** (for running the database container, i.e., MongoDB)
- **uv** (Required for backend dependency management)

## Getting Started

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-dashboard
```

### 2. Environment Setup

Create a `.env` file in the root directory (or ensure the existing one is configured correctly) with your API keys and database credentials.

```env
OPENAI_API_KEY=sk-...
# or
GEMINI_API_KEY=...
DATABASE_URL=...
```

### 3. Install Dependencies

Use the provided `Makefile` to set up both backend and frontend environments effortlessly.

```bash
make setup
```

This command will:

- Create a Python virtual environment and install backend requirements using `uv sync`.
- Install frontend Node.js packages.

### 4. Start the Application

Start both the backend and frontend servers with a single command:

```bash
make start
```

- **Frontend**: <http://localhost:5173>
- **Backend API**: <http://localhost:8000>

## 🎮 Usage

1. **Open the App**: Navigate to `<http://localhost:5173>`.
2. **Enter a Prompt**: In the input box, type a request like "Analyze the sales performance by region for the last 12 months."
3. **View Dashboard**: The system will plan, fetch data, and generate a dashboard.
4. **Refine**:
   - **Click** on a bar or point to filter the rest of the dashboard.
   - **Chat** to refine: "Switch the trend chart to a line chart."

## Project Structure

```txt
ai-dashboard/
├── backend/            # FastAPI application & Agent logic
├── frontend/           # React + Vite application
├── logs/               # Application logs
├── Makefile            # Convenience commands
├── docker-compose.yml  # Docker services (e.g., MongoDB)
└── REAMDE.md           # Project documentation
```

## Useful Commands

| Command      | Description                                   |
| :----------- | :-------------------------------------------- |
| `make setup` | Install all dependencies (Backend + Frontend) |
| `make start` | Start both servers                            |
| `make stop`  | Stop both servers                             |
| `make up`    | Start Docker containers (DB)                  |

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request for any enhancements or bug fixes.

### Code Quality

We enforce strict coding standards using `pre-commit`:

```bash
# Install git hooks
pre-commit install

# Run all checks manually
pre-commit run --all-files
```
