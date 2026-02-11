# Viz Engine (Vega-Lite Integration)

The AI Dashboard uses **Vega-Lite** for all visualizations because of its declarative nature, which makes it ideal for LLM generation.

## How it Works
1.  **Spec Generation**: The backend returns a complete Vega-Lite JSON specification.
2.  **Embedding**: The frontend uses `vega-embed` to render graphics into a DOM element.
3.  **Data Loading**: Charts are configured with `data: { url: "/api/dashboard/..." }`. We use a custom Vega loader to inject JWT authentication tokens into these outgoing requests.

## Interactivity & Selection
The pipeline is designed to include **Selection Signals** in the generated specs.
- **Single click**: Filters the dashboard based on a single data point.
- **Interval selection**: Allows zooming or filtering by a range (e.g., date ranges).

When a selection is made, the `ChartRenderer` detects the signal and updates the global `filterState`, which can then be synchronized with other charts.

## Performance
- **Memoization**: Charts are memoized to prevent expensive re-renders unless the spec has changed.
- **Lazy Loading**: Data is only fetched when the chart comes into view (optional enhancement).
