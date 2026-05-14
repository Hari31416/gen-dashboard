# Request & Response Examples

Concrete JSON structures for primary operations across the platform.

---

## 1. Authentication Handshake Payload (`POST /auth/token`)

### Request Parameters (Form-Data)
```txt
username=admin&password=secure_password_string
```

### JSON Response
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc4MDAwMDAwMH0....",
  "token_type": "bearer"
}
```

---

## 2. Complete Dashboard Payload Example

Below is an example of the finalized `ComposedDashboardSpec` returned upon completing a streaming or synchronous generation task:

```json
{
  "title": "Corporate Metrics Summary",
  "description": "Synthesized executive analytics.",
  "layout_type": "grid",
  "chart_count": 1,
  
  "vega_lite_spec": {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "background": "transparent"
  },
  
  "individual_specs": [
    {
      "chart_id": "chart_total_sales",
      "title": "Aggregate Sales Performance",
      "chart_type": "bar",
      "spec": {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "mark": { "type": "bar", "tooltip": true },
        "encoding": {
          "x": { "field": "department", "type": "nominal", "axis": { "labelAngle": 0 } },
          "y": { "field": "total_revenue", "type": "quantitative" }
        }
      },
      "data": {
        "values": [
          { "department": "Hardware", "total_revenue": 450000 },
          { "department": "Software", "total_revenue": 850000 },
          { "department": "Services", "total_revenue": 210000 }
        ]
      }
    }
  ],
  
  "layout_config": {
    "cols": 12,
    "row_height": 100,
    "layout": [
      { "i": "chart_total_sales", "x": 0, "y": 0, "w": 12, "h": 4 }
    ]
  },
  
  "sql_queries": [
    {
      "chart_id": "chart_total_sales",
      "sql_query": "SELECT department, SUM(revenue) as total_revenue FROM corporate_sales GROUP BY department"
    }
  ]
}
```
