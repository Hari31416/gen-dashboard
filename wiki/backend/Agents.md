# Agentic Pipeline & Logic

The heart of the AI Dashboard is a 4-stage sequential agent pipeline built on **LangGraph**.

## Orchestration: The StateGraph
The pipeline uses a `StateGraph(DashboardGraphState)` to manage flow. The state is a `TypedDict` that accumulates information as it passes through nodes.

### Pipeline Flow
1.  **Strategy Node**: Plans the dashboard components.
2.  **Conditional Edge**: If "strategy" fails, routes to `error_handler`; otherwise, to "data".
3.  **Data Node**: Fetches results from the target SQL database.
4.  **Conditional Edge**: Validates data presence before moving to "viz_spec".
5.  **Viz Spec Node**: Generates Vega-Lite specifications.
6.  **Layout Node**: Organizes charts and terminates at `END`.

## Agent Deep-Dive

### 1. Strategy Agent (Strategic Planning)
- **Role**: Analyzes the user's natural language prompt alongside the database schema (tables, columns, relationships).
- **Logic**: It selects 3-5 chart types (Bar, Line, Area, etc.) and defines the `x_field`, `y_field`, and `aggregation`.
- **Output**: A list of `ChartGoal` objects.

### 2. Data Agent (SQL Generation & ReAct Loop)
The Data Agent is unique because it uses an **iterative ReAct loop** to ensure SQL correctness.
- **Step 1 (Generate)**: Translates the chart goal into a dialect-specific SQL query.
- **Step 2 (Safety)**: Checks the query against a blacklist of keywords (`UPDATE`, `DROP`, etc.).
- **Step 3 (Execute)**: Runs the query against the database.
- **Step 4 (Correct)**: If the query fails (e.g., column name mismatch), the agent receives the error message and has **up to 3 iterations** to fix and retry.

### 3. Viz Spec Agent (Vega-Lite Composition)
- **Role**: Translates raw data (sample rows) and instructions into valid Vega-Lite JSON.
- **Special Handling**:
    - **Arc Charts**: Manually enforces `theta` and `color` encodings to avoid common LLM mistakes.
    - **Geoshapes (Maps)**: Injects GeoJSON lookup transforms for choropleth maps.
- **Optimization**: Uses URL-based data loading (`/api/dashboard/{session}/chart/{id}/data`) instead of embedding massive datasets directly into the JSON.

### 4. Layout Agent (Grid Arrangement)
- **Role**: Composes the `ComposedDashboardSpec` by determining which charts should be wide (full row) or narrow (side-by-side).
- **Result**: The final JSON layout used by the React frontend.

## Selective Refinement
When a user asks for a modification (e.g., "Change the color"), the **Refinement Classifier** determines which nodes need to re-run:
- **Title Change**: Only the Viz Spec agent re-runs.
- **Data Filter**: Re-runs the Data node (with new parameters) and the Viz Spec node.
- **Add Chart**: Re-starts the pipeline from Strategy node with context of existing charts.
