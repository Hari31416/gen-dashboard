# Logging Architecture

To ensure operational visibility during development and production monitoring, the backend standardizes logging operations across all modules.

---

## 1. Centralized Logger Instantiation

Modules instantiate tracking resources using a shared initialization pattern provided by `utilities/utils.py`. This ensures log messages are formatted consistently across the application:

```python
from utilities import create_simple_logger

# Initializes logging instances mapped to local execution modules
logger = create_simple_logger(__name__)
```

---

## 2. Structured Log Output Formatting

The simple logger wrapper configures standard Python logging handlers to output structured entries containing timestamps, execution levels, source files, and line numbers:

```txt
2026-05-14 04:52:00,123 - routes.dashboard - INFO - Dashboard generation request from admin: Show me revenue trends...
2026-05-14 04:52:01,456 - langchain_agents.dashboard.graph - DEBUG - Stream event from node: strategy
2026-05-14 04:52:03,789 - services.database.db_connection_service - WARNING - Query execution took longer than expected (2100ms)
```

---

## 3. Operational Logging Levels

Logging statements use standard severity levels to support log aggregation and alerting:
- **`DEBUG`**: Detailed execution tracking, such as raw agent payloads and SSE event loops. Enabled during local development.
- **`INFO`**: High-level application events, including server startup tasks, incoming API requests, session saves, and pipeline stage completions.
- **`WARNING`**: Non-fatal operational issues, such as missing configuration keys with fallbacks or long-running database queries.
- **`ERROR`**: Actionable runtime failures, including unhandled exceptions, malformed generation schemas, and connection timeouts.
