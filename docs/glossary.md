# Technical Glossary

This glossary defines standard terminology, third-party libraries, and internal abstractions used across the **AI Dashboard** codebase.

---

### Agentic Pipeline
A multi-step reasoning and data processing workflow where autonomous or semi-autonomous software entities (agents) execute distinct responsibilities sequentially or conditionally.

### Composed Dashboard Spec
The finalized JSON contract produced by the **Layout Agent**. It encapsulates dashboard metadata, unified styling configs, individual chart specs, pre-fetched raw data arrays, and SQL tracing queries. Validated via Pydantic on the backend and mapped to strict TypeScript interfaces on the frontend.

### Data Agent
The second stage of the generation pipeline. It receives `ChartGoal` structures, formulates database-specific SQL queries based on active schemas, runs proactive security sanitization checks, executes read-only operations via SQLAlchemy, and packages raw row records.

### Intent Classification
A routing mechanism invoked during dashboard refinement (`POST /dashboard/refine`). It analyzes the user's conversational feedback against current chart parameters to categorize the intended action (e.g., `chart_type_change`, `title_change`, `add_chart`, `sql_modification`) or flag when clarification is needed.

### LangGraph
An orchestration extension for LangChain designed to build robust, stateful, multi-actor applications with cycles. The AI Dashboard relies on LangGraph (`StateGraph`) to govern transitions between agent stages and stream partial execution events.

### Layout Agent
The fourth and final stage of the generation pipeline. It processes an array of single Vega-Lite specifications alongside metadata to compute responsive multi-column layouts (grid or explicit concatenation) preventing overlaps and styling inconsistencies.

### Pydantic
A Python data validation library using standard type hints. Used extensively across all input parsing, LLM structured outputs, and database interaction boundaries to guarantee compile-time and runtime type safety.

### Server-Sent Events (SSE)
A unidirectional streaming protocol used over standard HTTP. It enables the FastAPI server to emit live telemetry updates (`progress`, `complete`, `error`) to the React client during multi-stage generation tasks.

### Strategy Agent
The entry stage of the generation pipeline. It takes natural language user prompts and database schema context to formulate precise analytical objectives (`ChartGoal`) outlining the visual approach.

### Sub-query Injection
A localized filtering technique used by the fast-filtering engine (`POST /dashboard/filter`). It wraps base SQL queries inside outer sub-queries appending dynamic `WHERE` constraints to slice pre-existing dashboard metrics instantly.

### Vega-Lite
A high-level declarative visualization grammar. It enables data graphics to be described in JSON format using intuitive visual encoding channels (x, y, color, size, shape) mapping directly to underlying data fields.

### Viz Spec Agent
The third stage of the generation pipeline. It accepts raw tabular results alongside targeted objectives to synthesize valid, responsive single-chart Vega-Lite JSON blocks.
