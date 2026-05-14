# Error Handling Strategy

The **AI Dashboard** application uses explicit exception catching to handle errors gracefully. This prevents leaking stack traces to clients while returning structured error responses.

---

## 1. Global REST Exception Interceptors

Standard API endpoints catch operational failures and validation issues using centralized handlers. Errors map to standard HTTP status codes:

| Scenario | Handled Exception | Output Status Code | Detail Contract Payload |
| :--- | :--- | :--- | :--- |
| **Missing Account Records** | Authentication lookup fails | `401 Unauthorized` | `{"detail": "Incorrect username or password"}` |
| **Expired Tokens** | JWT Verification validation fails | `401 Unauthorized` | `{"detail": "Could not validate credentials"}` |
| **Inactive Profiles** | Account disabled validation check | `400 Bad Request` | `{"detail": "Inactive user account"}` |
| **Missing Resource IDs** | Session/Chart ownership lookups fail | `404 Not Found` | `{"detail": "Session ... not found"}` |
| **Malformed JSON Requests** | Schema parsing validation fails | `422 Unprocessable Entity` | Pydantic validation error array |
| **Destructive SQL Commands** | Query contains drop/write operations | `400 Bad Request` | `{"detail": "Query validation failed..."}` |

---

## 2. Server-Sent Events Streaming Error Contracts

Because Server-Sent Events stream over a persistent HTTP connection with a `200 OK` status, standard REST error mapping cannot be used once streaming begins.

To communicate failures occurring during long-running tasks, streaming generators yield standardized JSON error payloads before closing the connection:

```python
def format_error_event(error: str, stage: str = None) -> str:
    """Computes error payload strings formatted for active SSE streams."""
    payload = {
        "type": "error",
        "error": error,
        "stage": stage or "unknown"
    }
    return f"data: {json.dumps(payload)}\n\n"
```

### Client Handling
When the React frontend receives an event with `type: error`, it parses the string payload to update the workspace UI. This replaces loading skeletons with clear error messages without breaking the layout container.
