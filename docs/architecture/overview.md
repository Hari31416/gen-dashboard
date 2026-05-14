# Architecture Blueprint

The **AI Dashboard** platform implements a decoupled, event-driven architecture designed to transform natural language data queries into fully responsive interactive dashboards.

---

## High-Level System Architecture

```mermaid
graph TD
    %% User and Edge Gateway Layer
    Client[React 19 Web App] -- "HTTP POST / SSE Stream" --> API[FastAPI Gateway]
    
    %% Storage Backing Layer
    subgraph "Persistence Layer"
        Mongo[(MongoDB Session Store)]
        RelationalDB[(Target SQL Data Sources)]
    end
    
    %% Core Orchestration Layer
    subgraph "Core Orchestration Backend"
        API --> GraphEngine[LangGraph Stateful Graph Engine]
        
        GraphEngine --> Strat[1. Strategy Stage]
        Strat --> DataStage[2. Data Stage]
        DataStage --> VizStage[3. Viz Spec Stage]
        VizStage --> LayoutStage[4. Layout Stage]
    end
    
    %% Interactions
    API <--> Mongo
    DataStage -- "Async SQLAlchemy Connection" --> RelationalDB
    LayoutStage -- "ComposedDashboardSpec JSON" --> API
    API -- "Live Event Stream" --> Client
```

---

## Subsystem Responsibilities

### 1. Presentation Layer (React 19 + Vite)
- Serves as the consumer of composed **Vega-Lite** configuration schemas.
- Maintains responsive viewports, isolated client-side filter contexts, and user input validation via **Shadcn UI** components.
- Handles custom loading skeletons responding to multi-stage real-time Server-Sent Events emitted during complex generation.

### 2. API Gateway Layer (FastAPI)
- Governs connection lifecycle, JSON Payload serialization, request validation via strict **Pydantic** models, and Bearer token authentication.
- Bypasses reverse-proxy buffering (`X-Accel-Buffering: no`) to stream real-time pipeline checkpoints via generator endpoints directly to the browser.

### 3. Orchestration Layer (LangGraph)
- Orchestrates multi-actor generation processes using an explicit state diagram (`DashboardGraphState`).
- Decouples monolithic reasoning into sequential specialized micro-agents, bounding potential failure cascades and enabling localized re-tries.

### 4. Database Access Layer (SQLAlchemy Async)
- Establishes read-only engine pools to execute LLM-formulated query strings contextually against specified data catalogs.
- Applies pre-execution regex safety scrubbing to guarantee queries contain zero schema mutation/deletion commands.

### 5. Session State Layer (MongoDB)
- Persists raw conversational user inputs, schema snapshots, intermediate stage outputs, and historical execution SQL blocks.
- Enables contextual conversation restoration to drive localized natural language refinement (`POST /dashboard/refine`).
