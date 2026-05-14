# Business Logic Services

The decoupled business logic layer handles data operations, script sandboxing, and telemetry processing.

---

## Service Layer Mapping

```txt
services/
├── database/
│   ├── db_connection_service.py     # Connection string parsing & caching
│   └── db_config_models.py          # Secure config database abstractions
├── sse_utils.py                     # Standardized SSE JSON payloads
├── local_python_interpreter.py      # Secure script execution container
└── geojson_service.py               # Spatial mapping data translators
```

---

## 1. Database Connection Engine (`db_connection_service.py`)

Handles safe database interaction across asynchronous threads:
- **Connection Formatting**: Constructs standard SQLAlchemy database URIs dynamically based on config records.
- **Data Execution**: Wraps database driver calls to run SQL read commands, outputting formatted Pandas DataFrames ready for serialization.

---

## 2. Server-Sent Events Formatter (`sse_utils.py`)

Decouples payload construction from application routing, standardizing emitted event string payloads:

```python
def format_progress_event(stage: str, progress: int, message: str, details: dict = None) -> str:
    """Computes string event contracts compatible with SSE boundaries."""
    payload = {
        "type": "progress",
        "stage": stage,
        "progress": progress,
        "message": message,
        "details": details
    }
    return f"data: {json.dumps(payload)}\n\n"
```

---

## 3. Secure Execution Runtime (`local_python_interpreter.py`)

When generating dynamic analytics logic requiring localized transformations, the service layer isolates operations inside monitored environments. This prevents external command execution or unauthorized file access.
