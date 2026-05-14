# Background Tasks

The **AI Dashboard** application executes long-running data generation pipelines using asynchronous thread operations rather than offloading tasks to external queuing clusters (such as Celery or RQ).

---

## Architectural Context: Embedded Generator Loops

The pipeline generation process involves network calls to LLM APIs, dynamic schema synthesis, and database query executions. Combined, these stages can take 3 to 10 seconds to complete.

Rather than managing background worker nodes and polling endpoints, the application handles concurrency using **LangGraph** generator streams integrated directly into ASGI async handlers.

---

## Execution Mechanisms

### 1. Server-Sent Events Async Streaming
When a client hits `POST /dashboard/generate/stream`, the router spawns a background generator processing the input prompt asynchronously. 

As each agent stage finishes, the generator yields real-time progress events directly to the open network socket. This avoids blocking concurrent API requests while keeping the connection active.

### 2. Async Graph Orchestration
Within the generator thread, workflow stages execute using async invocations (`graph.ainvoke` / `graph.astream`). This allows the server runtime to switch execution contexts during database reads or API requests, maximizing CPU utilization.

---

## Error Catching & Recovery

Because operations run within active async scopes, runtime errors are caught and handled directly:
- **Graceful Termination**: Unhandled exceptions trigger the generation of explicit `type: error` SSE payloads before safely closing the connection socket.
- **Session Cleanup**: If a connection drops unexpectedly during processing, incomplete state snapshots are safely handled by the database session manager.
