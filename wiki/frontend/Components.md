# Dashboard Components

The UI is built on a library of reusable Shadcn-based components.

## Main View Components

### `DashboardView.tsx`
The primary container for a dashboard session. It manages the lifecycle of a dashboard, from initial generation to refinements and filtering.

### `ChartRenderer.tsx`
Handles the rendering of individual charts using Vega-Lite. It supports:
- Automatic resizing.
- Interactive selections (brushing/clicking).
- Custom loaders for authenticated data fetching.

### `PromptInput.tsx`
The AI interface. Supports both initial generation prompts and refinement feedback ("Make the chart blue").

### `FilterPanel.tsx`
Displays active global filters and allows users to modify them, triggering fast re-calculations on the backend.

## UI Components
Standard UI elements (Buttons, Inputs, Dialogs, Popovers) are located in `src/components/ui`, following the **Shadcn UI** pattern of direct file ownership.
