# API Reference

The backend exposes a REST API for session management and a streaming SSE endpoint for dashboard generation.

## Dashboard Endpoints

### `POST /api/dashboard/generate/stream`
The primary entry point for creating a new dashboard.
- **Request Body**: `DashboardGenerateRequest` (prompt, connection_name, max_charts).
- **Response**: A Server-Sent Events (SSE) stream.

#### SSE Event Structure
The stream yields JSON chunks representing the progress:
```json
{
  "type": "progress",
  "stage": "data",
  "progress": 50,
  "message": "Generating and executing SQL queries...",
  "details": { "queries_executed": 3, "successful_queries": 3 }
}
```
Upon completion, it sends:
```json
{ "type": "complete", "result": { "dashboard_spec": {...}, "session_id": "..." } }
```

### `POST /api/dashboard/refine`
Updates an existing dashboard based on feedback or filters.
- **Automatic Classification**: Detects if the change is a filtering action or a structural modification.
- **Efficiency**: Only re-runs the specific agents required for the change.

### `GET /api/dashboard/{session_id}/chart/{chart_id}/data`
Used by Vega-Lite on the frontend to fetch data for specific charts.
- **Authenticantion**: Requires the Same JWT as the main dashboard.
- **Data Handling**: Streamlines JSON delivery and handles large datasets via optimized result set mapping.

## Database Management

### `POST /api/database/connect`
Tests and saves a database connection.
- **Supported Dialects**: MySQL, PostgreSQL, SQLite.
- **Schema Caching**: Upon successful connection, the backend introspects the schema and caches it for agent prompts.

### `GET /api/database/connections`
Returns all saved connections for the current user.
