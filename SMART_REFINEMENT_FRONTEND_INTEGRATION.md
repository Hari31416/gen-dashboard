# Smart Dashboard Refinement - Frontend Integration Guide

## Backend Changes Summary

The backend now supports **smart refinement** that classifies user feedback and executes only the necessary operations.

### New/Updated Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/dashboard/refine` | POST | Smart intent-based refinement (updated) |
| `/api/dashboard/filter` | POST | Fast filter-only updates (new) |

---

## API Changes

### 1. `/api/dashboard/refine` (Updated)

**Request Body** (unchanged):
```json
{
  "session_id": "uuid-string",
  "new_feedback": "Change chart 1 to a line chart and remove chart 3",
  "target_chart_id": "chart_1"  // optional hint
}
```

**New Response Scenarios:**

#### Success Response:
```json
{
  "success": true,
  "session_id": "uuid",
  "dashboard": { /* ComposedDashboardSpec */ },
  "generation_time_ms": 1234
}
```

#### Clarification Needed Response (NEW):
```json
{
  "success": false,
  "session_id": "uuid",
  "dashboard": null,
  "error": null,
  "requires_clarification": true,
  "clarification_question": "Which chart would you like to modify?",
  "reasoning": "Multiple charts could match the request"
}
```

### 2. `/api/dashboard/filter` (New Endpoint)

Fast filter-only updates without LLM processing (~1s response).

**Request Body**:
```json
{
  "session_id": "uuid-string",
  "filter_state": {
    "region": "US",
    "category": "Electronics"
  }
}
```

**Response**: Same as refine success response.

---

## Frontend Changes Required

### 1. Handle Clarification Responses

Update the refine request handler to check for `requires_clarification`:

```typescript
const handleRefine = async (feedback: string) => {
  const response = await refineDashboard({
    session_id: sessionId,
    new_feedback: feedback,
  });

  if (response.requires_clarification) {
    // Show clarification dialog to user
    showClarificationDialog({
      question: response.clarification_question,
      onSubmit: (clarifiedFeedback) => {
        // Retry with more specific feedback
        handleRefine(clarifiedFeedback);
      },
    });
    return;
  }

  if (response.success) {
    updateDashboard(response.dashboard);
  }
};
```

### 2. Update API Client

Add types and the new filter endpoint:

```typescript
// types.ts
interface RefinementClarificationResponse {
  success: false;
  session_id: string;
  dashboard: null;
  error: null;
  requires_clarification: true;
  clarification_question: string;
  reasoning: string;
}

interface DashboardFilterRequest {
  session_id: string;
  filter_state: Record<string, any>;
}

// api.ts
export const filterDashboard = async (
  request: DashboardFilterRequest
): Promise<DashboardResponse> => {
  return api.post('/api/dashboard/filter', request);
};
```

### 3. Migrate Filter Calls

If currently using `/refine` with `filter_state`, update to use `/filter`:

```typescript
// Before
await refineDashboard({
  session_id,
  filter_state: filters,
});

// After
await filterDashboard({
  session_id,
  filter_state: filters,
});
```

### 4. Add Clarification UI Component

Create a dialog/modal for handling clarification requests:

```tsx
interface ClarificationDialogProps {
  isOpen: boolean;
  question: string;
  onSubmit: (response: string) => void;
  onClose: () => void;
}

const ClarificationDialog: React.FC<ClarificationDialogProps> = ({
  isOpen,
  question,
  onSubmit,
  onClose,
}) => {
  const [input, setInput] = useState('');

  return (
    <Dialog open={isOpen} onClose={onClose}>
      <DialogTitle>Clarification Needed</DialogTitle>
      <DialogContent>
        <p>{question}</p>
        <TextField
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Please provide more details..."
          fullWidth
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={() => onSubmit(input)} variant="contained">
          Submit
        </Button>
      </DialogActions>
    </Dialog>
  );
};
```

---

## Benefits of New System

1. **Faster Responses** - Simple changes (title, remove chart) execute instantly
2. **Smarter Processing** - Only runs necessary pipeline stages
3. **Multi-Action Support** - Handle multiple changes in one request
4. **Better UX** - Asks for clarification instead of guessing incorrectly
5. **Parallel Execution** - Independent actions run concurrently

---

## Files to Update in Frontend

| File | Changes |
|------|---------|
| `api/dashboard.ts` | Add `filterDashboard`, update response types |
| `types/dashboard.ts` | Add clarification response types |
| `components/DashboardRefine.tsx` | Handle clarification responses |
| `components/ClarificationDialog.tsx` | New component (optional) |
