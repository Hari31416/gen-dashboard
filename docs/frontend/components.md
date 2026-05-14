# Workspace Components

The frontend interface relies on dedicated UI components to manage user interactions, data rendering, and dashboard configuration.

---

## Component Inventory

### 1. `DashboardView`
- **Role**: The main interface layout container.
- **Responsibilities**: Orchestrates child component communications, orchestrates incoming generation streams, and persists current active dashboard specifications in local state.

### 2. `PromptInput`
- **Role**: Conversational command interface.
- **Responsibilities**: Captures natural language queries and modification prompts. Features keyboard shortcuts (e.g., `Cmd + Enter`) to trigger quick submission workflows.

### 3. `ChartRenderer`
- **Role**: Visualization module wrapper.
- **Responsibilities**: Mounts isolated **Vega-Lite** JSON specs to the DOM using dedicated container viewports. Manages fluid CSS responsiveness and catches rendering errors using inline boundaries.

### 4. `FilterPanel`
- **Role**: Filter configuration container.
- **Responsibilities**: Displays currently active sub-query filter states. Allows users to clear applied slices or view active drill-down paths.

### 5. `ChartCustomizationPanel`
- **Role**: Scoped parameter tuner.
- **Responsibilities**: Exposes input controls to modify chart properties (titles, rendering colors, layout sizes) locally without triggering network re-fetches.

### 6. `ClarificationDialog`
- **Role**: Ambiguity resolution interface.
- **Responsibilities**: Displays contextual popups if backend intent classification detects missing variables during a dashboard refinement request. Captures follow-up answers to resume pipeline execution safely.
