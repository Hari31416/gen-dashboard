# Frontend Subsystem

The **AI Dashboard** frontend serves as the visualization client. It consumes structured outputs from the backend API to render interactive Vega-Lite graphics.

---

## Architectural Principles

1. **Decoupled Visual Pipelines**: Isolating raw JSON parsing from primary container views prevents runtime crash cascades.
2. **Predictable Data Types**: Strict Typescript definitions mirroring backend contracts provide compile-time guarantees during deserialization.
3. **Fluid Layout Structures**: Standardized CSS behaviors automatically adjust viewports alongside changing dynamic grid container columns.

---

## Directory Reference

```txt
frontend/src/
├── api/                        # HTTP API clients & streaming utilities
├── components/                 # UI components
│   ├── dashboard/              # Workspace views, filters, dialogs, renderers
│   └── ui/                     # Reusable Shadcn UI design components
├── contexts/                   # Shared React Context providers
├── hooks/                      # Custom React hooks
├── pages/                      # Global views
└── types/                      # Comprehensive Typescript interfaces
```
