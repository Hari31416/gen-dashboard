# Frontend Testing Strategies

Frontend validation setups test component rendering correctness and custom state hook logic.

---

## 1. Testing Setup

Frontend unit testing workflows leverage **Vitest** combined with **React Testing Library** to verify DOM interactions and component correctness:

```txt
Vitest Integration Architecture
├── DOM Validation              # Asserts structure properties using `@testing-library/react`
├── Mocked Contexts             # Isolates Auth and Theme containers during component testing
└── Network Mocks               # Mocks HTTP/SSE client streams to test error recovery
```

---

## 2. Component Testing Patterns

### A. Isolated DOM Validation
Tests mount UI widgets inside test runners to assert structural expectations:
- **Form Interception**: Simulates keypress events inside prompt input fields to ensure state updates trigger correctly.
- **Customization Controls**: Tests input range sliders and title input toggles to confirm local component re-renders.

### B. Hook State Isolation
Custom hooks (such as `useStreamingGeneration`) run inside specialized test wrappers (`renderHook`) to verify localized logic:
- **Stream Deserialization**: Yields mocked strings mimicking backend progress steps to ensure progress updates parse smoothly.
- **Error Exits**: Simulates incomplete SSE JSON streams to confirm components fall back to informative error UI automatically.
