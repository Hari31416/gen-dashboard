# Frontend Overview

The frontend is a modern **React 19** application built with **Vite** and styled with **Tailwind CSS**.

## Tech Stack
- **Framework**: React 19 (Functional components + Hooks).
- **Styling**: Tailwind CSS + Shadcn UI.
- **Visualization**: Vega-Lite (via `vega-embed`).
- **State Management**: Context API and local state hooks.
- **Communication**: SSE for streaming generation and standard REST for refinements.

## Key Directories
- `src/components/dashboard`: Main dashboard views and renderers.
- `src/hooks`: Custom hooks for API interaction and SSE streaming.
- `src/api`: Axios-based API client.
- `src/types`: TypeScript interfaces mirroring backend Pydantic models.

## User Experience Flow
1.  **Dashboard Builder**: User enters a prompt in `PromptInput.tsx`.
2.  **Streaming Feedback**: `useDashboardStream` hook listens for SSE events and updates progress bars.
3.  **Dynamic Rendering**: Upon completion, the `DashboardView` renders the `ComposedDashboardSpec`.
