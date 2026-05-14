# Backend Internals

The **AI Dashboard** backend is structured to separate orchestration logic from edge API handling and underlying persistent access layers.

---

## Subsystem Layout

```txt
backend/
├── app.py                      # Global entrypoint & Lifespan configuration
├── langchain_agents/          # Core multi-agent reasoning graphs
│   ├── dashboard/             # Specialized dashboard pipeline modules
│   │   ├── agents/            # Strategy, Data, Viz Spec, and Layout agents
│   │   ├── refinement/        # Intent validation and structural update handling
│   │   └── graph.py           # Master LangGraph state engine definition
├── routes/                    # API endpoints
│   ├── auth.py                # Bearer token verification & user metadata
│   ├── dashboard.py           # Generation streams, refinement, and filtering
│   └── database.py            # Catalogs target relational schema bindings
├── services/                  # Decoupled domain business capabilities
│   ├── database/              # Shared connection string & schema caching logic
│   ├── sse_utils.py           # Encapsulates Server-Sent Events structure formatting
│   └── local_python_interpreter.py # Secure runtime script context wrappers
└── utilities/                 # Cross-cutting logging, validation & encryption
```

---

## Design Philosophy

1. **Uncompromising Type Safety**: Every data handoff relies on strict **Pydantic** models to catch parsing anomalies at runtime boundaries.
2. **Predictable Orchestration**: By relying on explicit graph state models (`DashboardGraphState`), operational context stays traceable through localized retries.
3. **Decoupled Telemetry**: Server-Sent Events generation leverages generator loops yielding isolated dictionaries, decoupled from rigid UI frameworks.
