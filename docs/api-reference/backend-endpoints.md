# API Endpoints Reference

This reference covers the primary REST and Server-Sent Events (SSE) endpoints exposed by the **AI Dashboard** backend.

---

## 1. Dashboard Generation Stream

### `POST /dashboard/generate/stream`
Executes the full 4-stage generation pipeline, streaming incremental status updates back to the client.

#### Authentication
Requires a valid Bearer JWT attached to request headers.

#### Request Body Schema (`DashboardGenerateRequest`)
```json
{
  "user_prompt": "Show daily revenue metrics breakdown across northern sales regions",
  "connection_name": "primary_analytics_db",
  "max_charts": 4,
  "theme": "slate"
}
```

#### Response Stream Format (`text/event-stream`)
Yields raw string chunks mapping lifecycle progress steps:

##### Progress Event Chunk
```sse
data: {"type": "progress", "stage": "strategy", "progress": 25, "message": "Planning chart objectives...", "details": {"charts_planned": 2}}

```

##### Completion Event Chunk
```sse
data: {"type": "complete", "result": {"session_id": "aff116c3-...", "dashboard_spec": {...}}}

```

---

## 2. Intent-Driven Refinement

### `POST /dashboard/refine`
Modifies an existing dashboard session context based on natural language feedback.

#### Authentication
Requires Bearer JWT authorization.

#### Request Payload (`DashboardRefineRequest`)
```json
{
  "session_id": "aff116c3-c9d0-4b9b-a095-dfd265d2b5f9",
  "new_feedback": "Update chart 1 to use a multi-series bar layout",
  "target_chart_id": "chart_1"
}
```

#### Response Payload (`DashboardResponse`)
```json
{
  "success": true,
  "session_id": "aff116c3-c9d0-4b9b-a095-dfd265d2b5f9",
  "dashboard": {
    "title": "Refined Workspace Metrics",
    "individual_specs": [...],
    "layout_config": {...}
  },
  "error": null
}
```

---

## 3. Fast Drill-Down Filtering

### `POST /dashboard/filter`
Applies sub-query injection wrappers to existing chart SQL logic to return filtered metrics instantly without invoking the LLM generation pipeline.

#### Authentication
Requires Bearer JWT authorization.

#### Request Payload (`DashboardFilterRequest`)
```json
{
  "session_id": "aff116c3-c9d0-4b9b-a095-dfd265d2b5f9",
  "filter_state": {
    "sales_region": "North",
    "fiscal_quarter": "Q4"
  }
}
```

#### Response Payload (`DashboardResponse`)
Returns updated chart data structures preserving pre-existing view specifications.
