# Project Structure

The frontend code follows a feature-centric component layout to support dynamic, single-page interactions.

---

## Directory Architecture

```txt
frontend/
├── public/                     # Static assets directly loadable by browser clients
├── src/
│   ├── api/                    # HTTP interaction layer (`client.ts`)
│   ├── assets/                 # Embedded graphic brand resources
│   ├── components/
│   │   ├── dashboard/          # Specialized visualization widgets
│   │   │   ├── ChartCustomizationPanel.tsx
│   │   │   ├── ChartRenderer.tsx
│   │   │   ├── ClarificationDialog.tsx
│   │   │   ├── ConnectionDialog.tsx
│   │   │   ├── DashboardView.tsx
│   │   │   ├── DatabaseSelector.tsx
│   │   │   ├── DebugLogin.tsx
│   │   │   ├── FilterPanel.tsx
│   │   │   ├── PromptInput.tsx
│   │   │   └── SavedDashboards.tsx
│   │   └── ui/                 # Reusable Shadcn base primitives
│   ├── contexts/               # Shared global data states
│   │   ├── AuthContext.tsx     # Manages authentication state
│   │   └── ThemeContext.tsx    # Supports multi-theme layouts
│   ├── hooks/                  # Encapsulated state side-effects
│   │   ├── useChartCustomization.ts
│   │   ├── useKeyboardShortcuts.ts
│   │   └── useStreamingGeneration.ts
│   ├── pages/                  # Page-level route views
│   │   └── LoginPage.tsx
│   └── types/                  # Core contract bindings
│       ├── chart-customization.ts
│       ├── dashboard.ts
│       ├── database.ts
│       └── progress.ts
├── index.html                  # Root template markup entry point
└── tailwind.config.js          # Unified CSS token and responsive scale configs
```

---

## High-Level Organization Philosophy

- **Atomic Components**: Basic visual primitives (`ui/`) stay free of business logic, focusing purely on responsive presentation.
- **Feature Encapsulation**: Domain-specific UI behaviors stay grouped inside dedicated domain areas (`components/dashboard/`), preventing dependency clutter across global layers.
