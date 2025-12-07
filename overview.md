# Dashboard Generation

## Backend

## 1. Core Technology Stack

| Component             | Technology                         | Role                                                                                       |
| :-------------------- | :--------------------------------- | :----------------------------------------------------------------------------------------- |
| **Backend Framework** | **FastAPI** (Recommended) or Flask | High-performance API server for handling user requests and orchestrating the LLM pipeline. |
| **LLM Orchestration** | **LangChain** or **LangGraph**     | Defines the multi-step, sequential agent workflow.                                         |
| **LLMs**              | OpenAI (GPT-4o) / Google Gemini    | Provides the base models for reasoning, Text-to-SQL, and Viz Spec generation.              |
| **Data Validation**   | **Pydantic**                       | Ensures strict, reliable JSON output schemas from all LLM agents.                          |
| **Database Access**   | **SQLAlchemy** (Async compatible)  | Secure and standardized connection layer to the user's provided database.                  |
| **Environment**       | **Python** 3.11+                   | The primary development language.                                                          |

## 2. Multi-Agent Pipeline Overview (The "Brain")

The system will use a **four-stage sequential agent pipeline** (managed by LangChain/LangGraph) to convert a natural language request into a single, comprehensive Vega-Lite JSON specification.

### A. Agent Stages and Responsibilities

1.  **Strategy Agent (Planner):**

    - **Input:** User Request, Full Database Schema.
    - **Output:** List of **3-5 Chart Objectives** (Pydantic: `List[ChartGoal]`).
    - **Role:** Analyzes the request and decides on the necessary charts (e.g., "Line chart for trend," "Bar chart for comparison," "KPI for total").

2.  **Data Agent (Executor):**

    - **Input:** List of Chart Objectives (including data requirements).
    - **Output:** List of **Raw Data + SQL** (Pydantic: `List[ChartDataResult]`).
    - **Role:** Iterates through objectives, generates the SQL using the schema context, executes it securely via **SQLAlchemy**, and fetches the raw results.
    - **Critical Feature:** Includes **SQL Sanitization/Validation** check before execution.

3.  **Viz Spec Agent (Translator):**

    - **Input:** Raw Data, Chart Objective (for one chart at a time).
    - **Output:** List of **Single Vega-Lite Specifications** (Pydantic: `List[SingleVizSpec]`).
    - **Role:** Maps the data fields to the correct Vega-Lite encoding channels (X, Y, Color, Mark) for a single view.

4.  **Layout Agent (Composer):**
    - **Input:** List of all runnable Single Vega-Lite Specifications, Original User Request.
    - **Output:** **Final Composed Vega-Lite JSON** (Pydantic: `ComposedDashboardSpec`).
    - **Role:** Decides the best layout (`hconcat`, `vconcat`, or nested grid) based on the number and type of charts, and wraps the individual specs into a single, cohesive dashboard JSON.

## 3. Key API Endpoints & Features

The FastAPI application will expose the following primary endpoints to the React frontend:

### 1. `/api/dashboard/generate` (POST)

- **Purpose:** Runs the full 4-agent pipeline to generate a dashboard from scratch.
- **Input:** `user_prompt` (string), `db_connection_params` (JSON).
- **Output:** `ComposedDashboardSpec` (JSON) containing the final Vega-Lite code and embedded data.

### 2. `/api/dashboard/refine` (POST)

- **Purpose:** Accepts user feedback or drill-down filters and adjusts the existing dashboard.
- **Input:** `session_id` (to retrieve history), `new_feedback` (string, e.g., "change chart 2 to a bar chart"), `filter_state` (JSON).
- **Process:** The pipeline will start with the **Data Agent** or **Viz Spec Agent** (bypassing the Planner) and use the feedback to generate new SQL or a new chart specification, keeping the existing layout where possible.

### 3. `/api/dashboard/refresh` (POST)

- **Purpose:** Executes the SQL queries from the _last successful run_ to fetch fresh data without running the LLM agents.
- **Input:** `session_id`.
- **Output:** Updated `ComposedDashboardSpec` with live data.

## 4. Critical Considerations

- **Security (Top Priority):** All LLM-generated SQL must be **pre-filtered and sanitized** (e.g., restricted to `SELECT` statements, checked for `DROP`, `DELETE`, or `UPDATE`) before being executed by SQLAlchemy.
- **Reliability:** Reliance on **Pydantic** validation at every stage is non-negotiable to prevent runtime errors in the frontend due to malformed JSON.
- **Context Management:** Implement a **LangChain Memory** component linked to the `session_id` to store conversation history and previous dashboard specs. This is essential for the refinement and refresh features.
- **Latency:** Since the process involves multiple sequential LLM calls and a database query, optimize the FastAPI deployment for **asynchronous processing** to handle long-running requests efficiently.

## Frontend

The React frontend serves as the visualization and interaction layer, consuming the structured JSON output from your Python backend and providing the necessary input for refinement and drill-down. The architecture must prioritize **dynamic rendering, efficient state management, and seamless interaction** with the backend API.

Here is the plan for the frontend architecture using React and Vega-Lite.

---

## 1\. Core Architecture and Component Structure ⚛️

The frontend will adopt a component-based structure where data flow is unidirectional and state is centrally managed.

### A. Main Components

| Component           | Responsibility                                                                                                                                                                            | Notes                                                                                                                |
| :------------------ | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------- |
| **`DashboardView`** | Manages the primary state: the user prompt, the session ID, and the full `ComposedDashboardSpec` JSON received from the backend.                                                          | Handles the initial call to `/api/dashboard/generate` and subsequent calls to `/api/dashboard/refine`.               |
| **`PromptInput`**   | Handles user input and feedback.                                                                                                                                                          | A simple text area where the user provides the initial query or refinement instructions. Triggers the main API call. |
| **`ChartRenderer`** | The most critical component. Takes the **full Composed Vega-Lite JSON** from the Layout Agent and embeds it using a library like **`react-vega`** or a custom wrapper using `vega-embed`. | Must be optimized for performance (see Section 3).                                                                   |
| **`FilterPanel`**   | Displays the current filters and allows drill-up/drill-down context to be managed.                                                                                                        | Handles interactive elements that translate user clicks into filter state changes.                                   |

### B. State Management

Given the complexity of the dynamic dashboard, consider using **React's Context API** or a library like **Zustand/Redux** to manage the global state, including:

- **`currentDashboardSpec`:** The full JSON specification for the current dashboard.
- **`filterState`:** A JSON object representing all currently applied global filters (e.g., `{'region': 'North', 'date_range': 'Q4 2025'}`).
- **`sessionId`:** A unique ID to maintain conversation/dashboard history on the backend.

## 2\. Vega-Lite Integration Strategy 📊

You must isolate the Vega-Lite rendering logic for reliability and performance.

### A. The `<VegaLiteRenderer>` Component

This reusable component will receive the single, final **Composed Vega-Lite JSON** object and the associated data.

1.  **Rendering Library:** Use **`react-vega`** or wrap the `vega-embed` function within a `React.useEffect` hook. The latter offers maximum control and is often necessary for complex setups.
2.  **Responsiveness:** Vega-Lite charts can often struggle with dynamic container resizing. Set the chart properties like `width` and `height` to `container` or use CSS transformations, as native Vega-Lite resizing can sometimes cause issues.
3.  **Data Binding:** The backend will return the data _embedded_ in the `ComposedDashboardSpec`. The component simply passes this entire JSON object to the renderer.

### B. Implementing Drill-Down/Interactivity

This is the bridge between the frontend click and the backend Agent refinement.

1.  **Vega Selection Signal:** The backend's **Viz Spec Agent** should be prompted to include **Selection Definitions** in its output. A simple `point` or `interval` selection allows a user to click or brush an area on a chart.
2.  **React Event Listener:** The `<VegaLiteRenderer>` component must listen to the selection event signals emitted by Vega-Lite.
3.  **State Update:** When a user clicks a bar chart and selects a category (e.g., "Electronics"), the React component extracts the selection data and updates the global **`filterState`** (e.g., adding `{'category': 'Electronics'}`).
4.  **Refinement Call:** Updating the global state triggers the call to the **`/api/dashboard/refine`** endpoint, sending the new `filterState` to the backend. The backend Agent then generates new SQL and a new Viz Spec based on this filter.

## 3\. Performance and Reliability 🚀

Given the dynamic nature, performance is critical for a smooth user experience.

- **Pydantic Schema Mirroring:** Use **TypeScript** on the frontend to create interfaces that **exactly mirror** the Pydantic schemas (`ComposedDashboardSpec`, `ChartGoal`, etc.) generated on the backend. This provides compile-time safety and prevents rendering crashes from unexpected JSON formats.
- **Memoization:** Wrap your `<ChartRenderer>` and other display components in **`React.memo`**. Since the LLM output (the JSON spec) is likely to be a new object on every API call, use a deep comparison function in `React.memo` (or carefully structure your state updates) to prevent unnecessary re-renders when the data/spec hasn't meaningfully changed.
- **Loading States:** Implement clear **Loading Skeletons** or progress indicators when the API call is in progress. The pipeline involves multiple LLM steps and a database query, meaning latency can range from 3-10 seconds, which needs careful user feedback.
- **Error Boundaries:** Use **React Error Boundaries** around the `<ChartRenderer>` component. If the final Vega-Lite JSON is invalid or crashes the renderer (despite the Pydantic checks), the error boundary prevents the entire dashboard from crashing, allowing the user to provide feedback and fix the error.

### Key Frontend Interactions Summary

| Feature               | User Action                                            | React Action                                    | API Endpoint Triggered    |
| :-------------------- | :----------------------------------------------------- | :---------------------------------------------- | :------------------------ |
| **Initial Build**     | User types prompt and clicks "Generate."               | Sends prompt and starts loading state.          | `/api/dashboard/generate` |
| **Filter/Drill-Down** | User clicks a bar on a chart.                          | Extracts selected value, updates `filterState`. | `/api/dashboard/refine`   |
| **Refinement**        | User types "Make it a line chart" and clicks "Refine." | Sends `new_feedback` and current `filterState`. | `/api/dashboard/refine`   |
| **Live Data**         | User clicks "Refresh Data."                            | Sends `session_id` to rerun SQL queries.        | `/api/dashboard/refresh`  |
