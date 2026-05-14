# Debugging Strategies

Techniques for monitoring server telemetry streams, pipeline execution graphs, and interface component trees.

---

## 1. Inspecting Server-Sent Events (SSE) Streams

Because streaming generation tasks (`POST /dashboard/generate/stream`) transmit over keep-alive socket channels, standard browser network tab payload inspection can be limited.

### Recommended Toolchains
- **cURL Direct Extraction**: Run terminal requests directly against gateway endpoints to observe emitted data blocks in real time:
  ```bash
  curl -N -X POST http://localhost:8000/dashboard/generate/stream \
    -H "Authorization: Bearer <token>" \
    -H "Content-Type: application/json" \
    -d '{"user_prompt": "test query", "connection_name": "db"}'
  ```
- **Browser Event Listeners**: Monitor emitted messages directly within client developer console views:
  ```javascript
  const es = new EventSource("http://localhost:8000/dashboard/generate/stream");
  es.onmessage = (event) => console.log(JSON.parse(event.data));
  ```

---

## 2. Tracing LangGraph State Execution

To track complex state mutations across multi-stage agent pipelines:
- **Enable Verbose Logging**: Set the backend log level to `DEBUG` in `.env` to capture execution inputs and outputs across all pipeline stages.
- **Inspect Session Snapshots**: Query the MongoDB `sessions` collection to examine captured stage output structures (`chart_goals`, `sql_queries`, `individual_specs`) after pipeline execution completes.

---

## 3. Isolating Client Rendering Errors

If generated chart specifications contain malformed syntax parameters:
- **Examine Component Error Boundaries**: The `<ChartRenderer>` component isolates rendering issues using localized React Error Boundaries. This prevents errors from breaking the wider dashboard layout container.
- **Validate against Specification Schemas**: Check generated Vega-Lite JSON specs against official schema definitions using online validators to identify invalid mark configurations.
