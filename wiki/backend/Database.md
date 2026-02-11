# Database Documentation

The AI Dashboard manages two types of data: **Target SQL Data** (for visualizations) and **Application State** (for sessions and metadata).

## Target SQL Databases
The system uses **SQLAlchemy** to connect to various database engines.

### Supported Dialects
- **PostgreSQL**: `postgresql+psycopg2://...`
- **MySQL**: `mysql+pymysql://...`
- **SQLite**: `sqlite:///...`

### Connection Management
Connections are built dynamically in `services/database/db_connection_service.py`. The backend introspects the database to retrieve:
- **Table Names**: For agent context.
- **Column Names & Types**: To help agents generate valid SQL.
- **Foreign Key Relationships**: To enable cross-table joins.

## SQL Security & Sanitization
To prevent SQL injection while allowing LLM-generated queries, the system employs several safety layers:

### 1. Read-Only Enforcement
Agents are explicitly prompted to only generate `SELECT` queries.

### 2. Lexical Analysis (Blacklist)
Before execution, every query is scanned using the `check_for_sql_safety` utility. It uses regex to block:
- **Destructive Commands**: `DROP`, `DELETE`, `TRUNCATE`.
- **Modifications**: `UPDATE`, `INSERT`, `ALTER`, `REPLACE`.
- **Administrative Access**: `GRANT`, `REVOKE`, `CREATE`.

### 3. Iterative Correction
If a query contains an error, the **Data Agent ReAct loop** catches the exception and asks the LLM to provide a fixed version, rather than exposing the raw error to the frontend.

## Session Persistence (MongoDB)
All dashboard sessions are persisted in a MongoDB collection. This allows users to revisit dashboards, share links, and maintain customizations.

### Document Structure (Simplified)
```json
{
  "session_id": "...",
  "username": "hari",
  "prompt": "Revenue trends",
  "dashboard_spec": {
    "layout": [...],
    "charts": [...]
  },
  "customizations": {
    "chart_1": { "theme": "quartz", "title": "Manual Override" }
  },
  "created_at": "ISODate(...)"
}
```
When a dashboard is "refined" by the AI, the backend merges the new AI-generated specs with the manually saved `customizations` to ensure user tweaks aren't lost.
