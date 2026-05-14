# Data Models

The **AI Dashboard** internal representation relies on document models persisted inside **MongoDB** collections.

---

## 1. Document Collections

```txt
MongoDB Data Catalogs
├── users/                      # System authentication accounts
├── sessions/                   # Executed dashboard state snapshots
└── db_configs/                 # Encrypted database connections
```

---

## 2. Session Schema Architecture

The `sessions` collection persists all context necessary to rehydrate user states:

```json
{
  "_id": "ObjectId('...')",
  "session_id": "aff116c3-c9d0-4b9b-a095-dfd265d2b5f9",
  "username": "admin",
  "connection_name": "production_metrics",
  "user_prompt": "Show daily sales metrics breakdown",
  "created_at": "2026-05-14T04:52:00Z",
  "generation_time_ms": 4820,
  
  "dashboard_spec": {
    "title": "Daily Sales Overview",
    "description": "Auto-generated analytics breakdown.",
    "layout_type": "grid",
    "chart_count": 2,
    "individual_specs": [
      {
        "chart_id": "chart_1",
        "title": "Revenue Over Time",
        "chart_type": "line",
        "spec": { "$schema": "https://vega.github.io/schema/vega-lite/v5.json", "..." : "..." }
      }
    ],
    "layout_config": {
      "cols": 12,
      "row_height": 100,
      "layout": [
        { "i": "chart_1", "x": 0, "y": 0, "w": 6, "h": 4 }
      ]
    }
  },
  
  "chart_goals": [
    {
      "chart_id": "chart_1",
      "question": "What is the revenue progression?",
      "chart_type": "line",
      "variables": ["order_date", "total_amount"]
    }
  ],
  
  "sql_queries": [
    {
      "chart_id": "chart_1",
      "sql_query": "SELECT order_date, SUM(total_amount) as total_amount FROM orders GROUP BY order_date"
    }
  ]
}
```

---

## 3. Database Configurations (`db_configs`)

Persists structural metadata enabling connections to relational sources:

```json
{
  "username": "admin",
  "connection_name": "production_metrics",
  "db_type": "postgresql",
  "host": "localhost",
  "port": 5432,
  "database": "analytics_db",
  "user": "db_user",
  "password": "encrypted_secret_string"
}
```
