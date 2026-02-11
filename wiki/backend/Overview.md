# Backend Overview

The backend is a high-performance **FastAPI** application designed for agentic orchestration and secure data handling.

## Directory Structure
```txt
backend/
├── app.py                  # Entry point, route inclusion, and startup logic
├── langchain_agents/       # Agentic core
│   ├── dashboard/          # Dashboard-specific logic
│   │   ├── agents/         # Stage implementations (Strategy, Data, Viz, Layout)
│   │   ├── graph.py        # LangGraph StateGraph definition
│   │   └── state.py        # TypedDict state schemas
│   └── models.py           # Shared Pydantic models (ChartGoal, etc.)
├── routes/                 # FastAPI routers (auth, dashboard, database)
├── services/               # Core business services
│   ├── database/           # SQL and NoSQL (MongoDB) logic
│   └── llm.py              # LLM client configuration (LiteLLM)
├── utilities/              # Logging, SSE, and helper functions
└── env.py                  # Environment variable management
```

## Core Technology Stack
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) for asynchronous REST and SSE.
- **Orchestration**: [LangGraph](https://langchain-ai.github.io/langgraph/) for the cyclic/sequential agent pipeline.
- **LLM Interface**: [LiteLLM](https://docs.litellm.ai/) for model-agnostic provider support.
- **ORM/Execution**: [SQLAlchemy](https://www.sqlalchemy.org/) for SQL dialect abstraction and execution.
- **Data Schemas**: [Pydantic v2](https://docs.pydantic.dev/) for strict type validation.

## Authentication & Security
- **JWT (OAuth2 Password Flow)**: Standard secure token-based authentication.
- **Dependency Injection**: Routes use `get_current_active_user` to ensure only authorized users access their connections and sessions.
- **User Scoping**: All database operations and dashboard sessions are scoped to the `username` to prevent data leakage between users.

## Startup Sequence
1.  **FastAPI Initialization**: Routers for `auth`, `dashboard`, and `database` are mounted.
2.  **State Loading**: Environment variables are validated via `env.py`.
3.  **Graph Compilation**: The LangGraph `StateGraph` is compiled into a singleton on first request.
4.  **Database Connection Pooling**: Global connection engines are initialized for efficient session management.
