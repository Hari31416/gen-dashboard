# Application Initialization

The FastAPI backend uses an explicit **Lifespan** context manager inside `backend/app.py` to ensure critical bootstrapping dependencies are satisfied before accepting web traffic.

---

## Startup Sequence

```mermaid
sequenceDiagram
    autonumber
    actor System
    participant App as FastAPI Runtime
    participant Dep as `check_dependencies.py`
    participant Adm as `setup_admin_user.py`
    participant Log as Simple Logger

    System->>App: Launch Uvicorn Server
    App->>App: Trigger `lifespan` startup hook
    
    %% Check 1
    App->>Log: Info ("Running dependency checks...")
    App->>Dep: Execute `main()` verification checks
    Dep-->>App: Exit status code (0 = success)
    
    %% Check 2
    App->>Log: Info ("Setting up admin user...")
    App->>Adm: Ensure default admin authentication records exist
    Adm-->>App: Exit status code (0 = success)
    
    App->>Log: Info ("Startup tasks completed successfully.")
    App-->>System: Server ready to receive incoming traffic
```

### Pre-Flight Failure Handling
If either dependency evaluation or user provisioning exits with a non-zero exit code, the lifespan hook executes `sys.exit(1)`. This fail-fast approach prevents deploying a compromised service to production.

---

## Global Middleware and Routing Registration

Following standard initialization procedures, global routing contexts are attached to the API instance:

```python
app = FastAPI(title="Dashboard Generation API", version="0.1.0", lifespan=lifespan)

# Attached Global Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Core Router Inclusions (Order Independent but Logically Segregated)
app.include_router(auth)
app.include_router(database_router)
app.include_router(dashboard_router)
```

### Baseline Health Check Endpoints
The base API instance attaches direct root verifiers to validate load-balancer connections:
- `GET /`: Outputs global application identifier payloads.
- `GET /health`: Yields basic status indicators (`{"status": "healthy"}`).
