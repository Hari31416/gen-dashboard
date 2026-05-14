# API Routing Layers

The **AI Dashboard** application maps endpoints under distinct routing definitions. Every incoming HTTP request undergoes structural Pydantic validation before routing to its respective target execution handler.

---

## 1. Dashboard Operations (`routes/dashboard.py`)

Governs full pipeline generation, smart updates, drill-down sub-filtering, and historical query cache access.

| Method | Route | Description | Auth Required | Core Output |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/dashboard/generate` | Synchronous straight-line generation using the 4-stage pipeline. | Yes | `DashboardResponse` |
| `POST` | `/dashboard/generate/stream` | Asynchronous generator streaming progress percentages via **SSE**. | Yes | SSE Text Stream |
| `POST` | `/dashboard/refine` | Intent-driven modifications applying localized edits. | Yes | `DashboardResponse` |
| `POST` | `/dashboard/filter` | Injects sub-query filtering wrappers for instantaneous drill-downs. | Yes | `DashboardResponse` |
| `GET` | `/dashboard/{session_id}/chart/{chart_id}/data` | URL endpoint serving live row records to clients. | Yes | JSON Array |
| `DELETE` | `/dashboard/{session_id}/chart/{chart_id}` | Immediately strips designated chart definitions without calling the LLM. | Yes | `DashboardResponse` |

---

## 2. Authentication Management (`routes/auth.py`)

Handles Bearer token validation, user creation, and access status checks.

| Method | Route | Description | Auth Required | Core Output |
| :--- | :--- | :--- | :--- | :--- |
| `POST` | `/auth/token` | OAuth2 compatible password grant yielding access tokens. | No | `Token` Payload |
| `GET` | `/auth/users/me` | Validates session headers and outputs internal user claims. | Yes | `User` Document |

---

## 3. Database Catalogs (`routes/database.py`)

Exposes target schema metadata to inform LLM generation context.

| Method | Route | Description | Auth Required | Core Output |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/database/connections` | Lists configured relational database connections. | Yes | Connection List |
| `GET` | `/database/schema/{connection_name}` | Retrieves table architectures, column properties, and relational constraints. | Yes | `DatabaseSchema` |

---

## 4. Internationalization Context (`routes/language.py`)

Exposes localized strings.

| Method | Route | Description | Auth Required | Core Output |
| :--- | :--- | :--- | :--- | :--- |
| `GET` | `/language/translations` | Serves localized user string parameters. | Optional | Translation JSON |
