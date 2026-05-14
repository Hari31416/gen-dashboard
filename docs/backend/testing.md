# Testing Patterns

The backend uses **pytest** to validate internal execution boundaries, route handlers, and data transformation logic.

---

## 1. Test Directory Layout

```txt
backend/tests/
├── conftest.py                 # Shared execution fixtures and mocked services
├── test_auth.py                # Asserts password verification and JWT logic
├── test_dashboard_routes.py    # Validates REST payload mapping and SSE stream structure
└── test_security_scrubbing.py  # Tests pre-execution SQL regex sanitization
```

---

## 2. Core Testing Strategies

### A. Isolated Unit Execution
Unit tests run isolated from external network dependencies. Tests replace downstream network calls to MongoDB and LLM API providers with mock objects (`unittest.mock`) to verify localized logic:
- **Pydantic Validation**: Asserts that malformed edge request payloads raise validation errors before hitting route logic.
- **SQL Sanitization**: Tests the regex scrubbing module against arrays of malicious query injection strings to ensure destructive commands are caught.

### B. Route Integration via TestClient
To test route execution and dependency injection, tests use `fastapi.testclient.TestClient`. This allows simulating full HTTP request cycles directly against the initialized application instance:

```python
from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_unauthenticated_access_rejection():
    """Asserts that unauthenticated requests to protected endpoints return 401."""
    response = client.post("/dashboard/generate", json={"user_prompt": "test", "connection_name": "db"})
    assert response.status_code == 401
```
