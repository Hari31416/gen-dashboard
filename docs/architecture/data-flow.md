# System Data Flows

The **AI Dashboard** orchestration pathways rely on structured request pipelines. Below are detailed execution tracings for primary generation and operational tasks.

---

## 1. Generation Stream Pipeline (`POST /dashboard/generate/stream`)

This flow handles fresh dashboard construction from user inputs, emitting incremental status updates back to the UI.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as React Client
    participant GW as FastAPI Server
    participant LG as LangGraph Execution
    participant DB as Target Database
    participant Mongo as MongoDB Session Store

    User->>UI: Enter Prompt ("Show daily revenue trends")
    UI->>GW: POST `/dashboard/generate/stream`
    GW-->>UI: Establish SSE Streaming Connection
    
    %% Stage 1
    GW->>LG: Execute Strategy Agent
    LG-->>GW: Yield `progress: 25%` (Planning goals...)
    GW-->>UI: SSE Event (`type: progress`)
    
    %% Stage 2
    LG->>DB: Execute Sanitized Data Queries
    DB-->>LG: Tabular Rowset Results
    LG-->>GW: Yield `progress: 50%` (Fetching data...)
    GW-->>UI: SSE Event (`type: progress`)
    
    %% Stage 3
    LG->>LG: Translate Records to Vega-Lite Specs
    LG-->>GW: Yield `progress: 75%` (Building views...)
    GW-->>UI: SSE Event (`type: progress`)
    
    %% Stage 4
    LG->>LG: Compose Grid Positioning Constraints
    LG-->>GW: Final Composed Contract Spec
    
    GW->>Mongo: Persist Executed Session Payload
    GW-->>UI: SSE Event (`type: complete`, `result: spec`)
    UI->>User: Render Interactive Visual Workspace
```

---

## 2. Intent Refinement Lifecycle (`POST /dashboard/refine`)

When a user initiates modifications on an existing dashboard context, the system utilizes intent classification to bypass complete pipeline re-runs.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as React Client
    participant CL as Intent Classifier Node
    participant EX as Modular Action Executor
    participant DB as Target Database

    User->>UI: Feedback ("Change Chart 2 to a bar chart")
    UI->>CL: POST `/dashboard/refine` (Include Session ID)
    
    CL->>CL: Evaluate Intent vs Target Chart Params
    
    alt Ambiguity Detected
        CL-->>UI: Return Clarification Question payload
        UI->>User: Display Modals requesting details
    else Intent Clear
        CL->>EX: Route Targeted Modification Actions
        EX->>EX: Compute Isolated Spec Updates
        EX-->>UI: Return Partially Updated Dashboard JSON
        UI->>User: Update Specific Visualization Viewports
    end
```

---

## 3. Real-time Sub-query Filtering (`POST /dashboard/filter`)

Enables drill-down selections to instantly slice active metrics across the workspace without invoking the LLM generation stack.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as React Client
    participant GW as FastAPI Server
    participant DB as Target Database

    User->>UI: Select Region Category ("North")
    UI->>GW: POST `/dashboard/filter` (`filter_state: {region: North}`)
    
    GW->>GW: Restore Initial Cached SQL Strings
    GW->>GW: Inject Sub-query Filtering Wrappers
    
    loop Per Workspace Viewport
        GW->>DB: Execute Sub-query Filtered Queries
        DB-->>GW: Sliced Tabular Data Subsets
    end
    
    GW-->>UI: Return Updated Data Array Payload
    UI->>User: Smoothly Transition Rendered Viewports
```
