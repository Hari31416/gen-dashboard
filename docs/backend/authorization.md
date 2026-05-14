# Authorization Architecture

The **AI Dashboard** application enforces role-based access control (RBAC) and resource ownership validation to protect user dashboard sessions and database configs from unauthorized access.

---

## 1. Access Status Verification

Once an incoming JWT token is successfully decoded, access control dependencies evaluate internal user record properties:

```python
async def get_current_active_user(current_user: User = Depends(get_current_user)):
    """Verifies operational status properties before granting endpoint access."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user account")
    return current_user
```

### Protection Boundaries
Chaining the active account validation check prevents disabled user records from invoking computational pipeline resources or viewing historical queries.

---

## 2. Session Ownership Isolation

Dashboard generation payloads, raw data records, and stored database configurations are isolated by user context.

### Data Access Guardrails
When a user requests operations on an active session (`POST /dashboard/refine`, `GET /dashboard/{session_id}/chart/{chart_id}/data`), resource services query MongoDB using composite keys matching both the target parameter and the authenticated user identity:

```python
def get_dashboard_session(username: str, session_id: str) -> Optional[dict]:
    """Retrieves session records filtered by authenticated owner boundaries."""
    # Queries collections using composite match structures:
    # {"session_id": session_id, "username": username}
    ...
```

### Security Benefits
By requiring both parameters, unauthorized attempts to enumerate or access sessions belonging to other accounts return standard `404 Not Found` errors. This prevents cross-account data leakage.
