# Architectural Decision Records

This document tracks core technical design records established during the creation of the **AI Dashboard** application.

---

## ADR 1: Stateful Orchestration via LangGraph

### Context
Generating interactive data dashboards from natural language queries requires multi-step reasoning: understanding broad intent, fetching data contextually, sanitizing SQL strings, and generating visual layout schemas. Attempting this using straightforward, single-pass prompting chains results in unstable outputs and logic failures.

### Decision
We use **LangGraph** to govern execution transitions across explicit, focused agent nodes (`Strategy`, `Data`, `Viz Spec`, `Layout`).

### Consequences
- **Positive**: Decoupling the generation pipeline into specialized micro-agents improves maintainability and bounds runtime errors to individual stages.
- **Positive**: Enables unidirectional progress percentage updates to stream back to the UI smoothly.

---

## ADR 2: Direct DataFrame Deserialization

### Context
Once an agent stage executes read queries against target SQL databases, output data buffers must be translated into JSON objects for client consumption.

### Decision
We bypass intermediate ORM abstraction layers. Results are loaded directly into memory as **Pandas DataFrames** before serializing to target JSON payload endpoints.

### Consequences
- **Positive**: Eliminates the CPU overhead of instantiating large arrays of temporary intermediate ORM models, keeping streaming throughput fast.
- **Negative**: Requires custom translation routines to cast complex native database types (`Decimal`, `datetime`) to JSON-compatible primitives manually.

---

## ADR 3: Isolated Client Rendering Runtime

### Context
Rendering dynamic, raw JSON configuration strings directly into web graphics libraries can cause page instability if specification parameters contain syntax errors.

### Decision
The React UI workspace wraps **Vega-Lite** execution logic inside decoupled functional wrappers combined with inline **React Error Boundaries**.

### Consequences
- **Positive**: Confines configuration syntax faults to localized chart containers, preventing application-wide UI crashes.
- **Positive**: Ensures charts automatically resize alongside fluid dashboard grid columns.
