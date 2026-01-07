# Implementation Plan: Loading Progress Percentage

This document provides a step-by-step implementation guide for real-time loading progress using Server-Sent Events (SSE) with LangGraph streaming.

---

## Overview

**Goal**: Display real-time loading progress percentage during dashboard generation using SSE from the backend LangGraph pipeline.

**Architecture**:
```
Frontend (ProgressBar) 
    ↕ EventSource (SSE)
Backend (FastAPI + SSE)
    ↕ LangGraph astream()  
LangGraph Nodes (strategy → data → viz_spec → layout)
```

---

## Current State

| Component | Status |
|-----------|--------|
| `graph.py` | Uses `ainvoke()` - returns only final result |
| `dashboard.py` (route) | POST `/generate` waits for full pipeline completion |
| Frontend | Shows loading spinner with no progress info |
| LangGraph | 4-stage pipeline: strategy → data → viz_spec → layout |

**Key insight**: LangGraph supports `astream()` which yields state updates after each node completes. We can use this to emit SSE events with progress percentage.

---

## Progress Stages

| Stage | Node Name | Progress % | Description |
|-------|-----------|------------|-------------|
| 0 | (start) | 0% | Request received |
| 1 | strategy | 25% | Planning chart objectives |
| 2 | data | 50% | Generating & executing SQL |
| 3 | viz_spec | 75% | Creating Vega-Lite specs |
| 4 | layout | 100% | Composing final dashboard |

---

## Implementation Steps

### Step 1: Create SSE Utilities Module

**File**: `backend/services/sse_utils.py` [NEW]

```python
"""
Server-Sent Events (SSE) utilities for streaming responses.
"""

import json
from typing import Any, AsyncGenerator


def format_sse_event(
    event_type: str,
    data: Any,
    event_id: str | None = None
) -> str:
    """
    Format data as an SSE event string.
    
    Args:
        event_type: Event name (e.g., 'progress', 'complete', 'error')
        data: Data payload (will be JSON serialized)
        event_id: Optional event ID for client reconnection
        
    Returns:
        SSE-formatted string
    """
    lines = []
    
    if event_id:
        lines.append(f"id: {event_id}")
    
    lines.append(f"event: {event_type}")
    
    # JSON serialize the data
    json_data = json.dumps(data) if not isinstance(data, str) else data
    lines.append(f"data: {json_data}")
    
    # SSE requires double newline to end event
    return "\n".join(lines) + "\n\n"


def format_progress_event(
    stage: str,
    progress: int,
    message: str,
    details: dict | None = None
) -> str:
    """
    Format a progress update event.
    
    Args:
        stage: Current stage name
        progress: Progress percentage (0-100)
        message: Human-readable status message
        details: Optional additional details
        
    Returns:
        SSE-formatted progress event
    """
    data = {
        "stage": stage,
        "progress": progress,
        "message": message,
    }
    if details:
        data["details"] = details
    
    return format_sse_event("progress", data)


def format_complete_event(result: dict) -> str:
    """Format a completion event with the final result."""
    return format_sse_event("complete", result)


def format_error_event(error: str, stage: str | None = None) -> str:
    """Format an error event."""
    data = {"error": error}
    if stage:
        data["failed_stage"] = stage
    return format_sse_event("error", data)
```

---

### Step 2: Create Streaming Dashboard Generation Function

**File**: `backend/langchain_agents/dashboard/graph.py` [MODIFY]

Add a new streaming function alongside the existing `run_dashboard_generation`:

```python
# Add to imports
from typing import AsyncGenerator

# Progress stage mapping
STAGE_PROGRESS = {
    "strategy": {"progress": 25, "message": "Planning chart objectives..."},
    "data": {"progress": 50, "message": "Generating and executing SQL queries..."},
    "viz_spec": {"progress": 75, "message": "Creating visualizations..."},
    "layout": {"progress": 100, "message": "Composing dashboard layout..."},
    "error_handler": {"progress": -1, "message": "Error occurred"},
}


async def stream_dashboard_generation(
    user_prompt: str,
    username: str,
    connection_name: str,
    session_id: Optional[str] = None,
    max_charts: int = 10,
    theme: str = "default",
) -> AsyncGenerator[dict, None]:
    """
    Stream dashboard generation progress using LangGraph's astream().
    
    Yields progress updates after each stage completes, then yields
    the final result.
    
    Yields:
        dict with either:
        - {"type": "progress", "stage": str, "progress": int, "message": str}
        - {"type": "complete", "result": dict}
        - {"type": "error", "error": str, "stage": str}
    """
    import time
    import uuid
    
    start_time = time.time()
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    logger.info(f"Starting streaming dashboard generation for session {session_id}")
    
    # Yield initial progress
    yield {
        "type": "progress",
        "stage": "starting",
        "progress": 0,
        "message": "Initializing dashboard generation...",
    }
    
    # Create initial state
    initial_state = create_initial_dashboard_state(
        user_prompt=user_prompt,
        username=username,
        connection_name=connection_name,
        session_id=session_id,
        max_charts=max_charts,
        theme=theme,
    )
    initial_state["start_time"] = start_time
    
    graph = get_dashboard_graph()
    
    try:
        final_state = None
        
        # Stream through graph execution
        async for event in graph.astream(initial_state):
            # LangGraph stream yields {node_name: state_update} dicts
            for node_name, state_update in event.items():
                logger.debug(f"Stream event from node: {node_name}")
                
                # Get progress info for this stage
                stage_info = STAGE_PROGRESS.get(node_name, {})
                progress = stage_info.get("progress", 0)
                message = stage_info.get("message", f"Processing {node_name}...")
                
                # Check for errors in state update
                if state_update.get("error"):
                    yield {
                        "type": "error",
                        "error": state_update["error"],
                        "stage": node_name,
                    }
                    return
                
                # Yield progress update
                yield {
                    "type": "progress",
                    "stage": node_name,
                    "progress": progress,
                    "message": message,
                    "details": {
                        "charts_planned": len(state_update.get("chart_goals", [])) if node_name == "strategy" else None,
                        "queries_executed": len(state_update.get("chart_data_results", [])) if node_name == "data" else None,
                        "specs_created": len(state_update.get("viz_specs", [])) if node_name == "viz_spec" else None,
                    }
                }
                
                # Keep track of final state
                if final_state is None:
                    final_state = state_update
                else:
                    final_state.update(state_update)
        
        # Calculate total time
        total_time = (time.time() - start_time) * 1000
        final_state["total_time_ms"] = total_time
        final_state["session_id"] = session_id
        
        # Yield completion
        yield {
            "type": "complete",
            "result": final_state,
        }
        
        logger.info(f"Streaming dashboard generation completed in {total_time:.2f}ms")
        
    except Exception as e:
        logger.exception(f"Streaming dashboard generation failed: {e}")
        yield {
            "type": "error",
            "error": str(e),
            "stage": "graph_execution",
        }
```

---

### Step 3: Create SSE Streaming Endpoint

**File**: `backend/routes/dashboard.py` [MODIFY]

Add a new streaming endpoint:

```python
# Add to imports
from fastapi.responses import StreamingResponse
from services.sse_utils import (
    format_progress_event,
    format_complete_event,
    format_error_event,
)
from langchain_agents.dashboard.graph import stream_dashboard_generation


@router.post("/generate/stream")
async def generate_dashboard_stream(
    request: DashboardGenerateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate a dashboard with real-time progress updates via SSE.
    
    Returns a Server-Sent Events stream with:
    - 'progress' events: {stage, progress, message}
    - 'complete' event: {dashboard, session_id, ...}
    - 'error' event: {error, failed_stage}
    
    Example usage (JavaScript):
    ```
    const eventSource = new EventSource('/api/dashboard/generate/stream', {
        method: 'POST',
        body: JSON.stringify(request)
    });
    eventSource.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        console.log(`${data.progress}% - ${data.message}`);
    });
    eventSource.addEventListener('complete', (e) => {
        const data = JSON.parse(e.data);
        console.log('Dashboard:', data.dashboard);
        eventSource.close();
    });
    ```
    """
    username = current_user.username
    session_id = str(uuid.uuid4())
    
    logger.info(
        f"Streaming dashboard generation request from {username}: {request.user_prompt[:100]}..."
    )
    
    async def event_generator():
        async for event in stream_dashboard_generation(
            user_prompt=request.user_prompt,
            username=username,
            connection_name=request.connection_name,
            session_id=session_id,
            max_charts=request.max_charts,
            theme=request.theme or "default",
        ):
            event_type = event.get("type")
            
            if event_type == "progress":
                yield format_progress_event(
                    stage=event["stage"],
                    progress=event["progress"],
                    message=event["message"],
                    details=event.get("details"),
                )
            
            elif event_type == "complete":
                result = event["result"]
                dashboard_spec = result.get("dashboard_spec")
                
                # Save session (same as non-streaming endpoint)
                if dashboard_spec:
                    try:
                        save_dashboard_session(
                            username=username,
                            session_id=session_id,
                            user_prompt=request.user_prompt,
                            connection_name=request.connection_name,
                            dashboard_spec=dashboard_spec,
                            chart_goals=result.get("chart_goals", []),
                            sql_queries=dashboard_spec.get("sql_queries", []),
                            generation_time_ms=result.get("total_time_ms", 0),
                        )
                    except Exception as e:
                        logger.error(f"Failed to save session: {e}")
                
                # Build response (same structure as non-streaming)
                layout_config = None
                if dashboard_spec and dashboard_spec.get("layout_config"):
                    lc = dashboard_spec["layout_config"]
                    layout_config = {
                        "cols": lc.get("cols", 12),
                        "row_height": lc.get("row_height", 100),
                        "layout": lc.get("layout", []),
                        "custom": lc.get("custom", False),
                    }
                
                response_data = {
                    "success": True,
                    "session_id": session_id,
                    "dashboard": {
                        "title": dashboard_spec.get("title", "Dashboard") if dashboard_spec else None,
                        "description": dashboard_spec.get("description") if dashboard_spec else None,
                        "vega_lite_spec": dashboard_spec.get("vega_lite_spec", {}) if dashboard_spec else {},
                        "individual_specs": dashboard_spec.get("individual_specs", []) if dashboard_spec else [],
                        "layout_config": layout_config,
                        "chart_count": dashboard_spec.get("chart_count", 0) if dashboard_spec else 0,
                        "sql_queries": dashboard_spec.get("sql_queries", []) if dashboard_spec else [],
                    } if dashboard_spec else None,
                    "generation_time_ms": result.get("total_time_ms"),
                }
                
                yield format_complete_event(response_data)
            
            elif event_type == "error":
                yield format_error_event(
                    error=event["error"],
                    stage=event.get("stage"),
                )
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
```

---

### Step 4: Create Frontend Progress Types

**File**: `frontend/src/types/progress.ts` [NEW]

```tsx
export interface ProgressEvent {
  stage: string
  progress: number
  message: string
  details?: {
    charts_planned?: number | null
    queries_executed?: number | null
    specs_created?: number | null
  }
}

export interface GenerationProgress {
  isLoading: boolean
  progress: number
  stage: string
  message: string
  details?: ProgressEvent['details']
}
```

---

### Step 5: Create useStreamingGeneration Hook

**File**: `frontend/src/hooks/useStreamingGeneration.ts` [NEW]

```tsx
import { useState, useCallback, useRef } from 'react'
import type { ComposedDashboardSpec } from '@/types/dashboard'
import type { GenerationProgress } from '@/types/progress'

interface StreamingGenerationResult {
  success: boolean
  session_id: string
  dashboard: ComposedDashboardSpec | null
  error?: string
  generation_time_ms?: number
}

interface UseStreamingGenerationOptions {
  onProgress?: (progress: GenerationProgress) => void
  onComplete?: (result: StreamingGenerationResult) => void
  onError?: (error: string) => void
}

export function useStreamingGeneration(options: UseStreamingGenerationOptions = {}) {
  const { onProgress, onComplete, onError } = options
  const [progress, setProgress] = useState<GenerationProgress>({
    isLoading: false,
    progress: 0,
    stage: '',
    message: '',
  })
  const [result, setResult] = useState<StreamingGenerationResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const generate = useCallback(async (request: {
    user_prompt: string
    connection_name: string
    max_charts?: number
    theme?: string
  }) => {
    // Reset state
    setProgress({ isLoading: true, progress: 0, stage: 'starting', message: 'Starting...' })
    setResult(null)
    setError(null)

    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController()

    try {
      const token = localStorage.getItem('token')
      
      const response = await fetch('/api/dashboard/generate/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': token ? `Bearer ${token}` : '',
        },
        body: JSON.stringify(request),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error: ${response.status}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('No response body')
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        
        // Parse SSE events from buffer
        const events = buffer.split('\n\n')
        buffer = events.pop() || '' // Keep incomplete event in buffer

        for (const eventStr of events) {
          if (!eventStr.trim()) continue

          const lines = eventStr.split('\n')
          let eventType = ''
          let eventData = ''

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              eventType = line.slice(7)
            } else if (line.startsWith('data: ')) {
              eventData = line.slice(6)
            }
          }

          if (!eventType || !eventData) continue

          try {
            const data = JSON.parse(eventData)

            if (eventType === 'progress') {
              const newProgress: GenerationProgress = {
                isLoading: true,
                progress: data.progress,
                stage: data.stage,
                message: data.message,
                details: data.details,
              }
              setProgress(newProgress)
              onProgress?.(newProgress)
            } else if (eventType === 'complete') {
              setProgress(prev => ({ ...prev, isLoading: false, progress: 100 }))
              setResult(data)
              onComplete?.(data)
            } else if (eventType === 'error') {
              const errorMsg = data.error || 'Unknown error'
              setError(errorMsg)
              setProgress(prev => ({ ...prev, isLoading: false }))
              onError?.(errorMsg)
            }
          } catch (parseError) {
            console.error('Failed to parse SSE event:', parseError)
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        console.log('Generation cancelled')
        return
      }
      const errorMsg = err instanceof Error ? err.message : 'Unknown error'
      setError(errorMsg)
      setProgress(prev => ({ ...prev, isLoading: false }))
      onError?.(errorMsg)
    }
  }, [onProgress, onComplete, onError])

  const cancel = useCallback(() => {
    abortControllerRef.current?.abort()
    setProgress(prev => ({ ...prev, isLoading: false }))
  }, [])

  return {
    generate,
    cancel,
    progress,
    result,
    error,
    isLoading: progress.isLoading,
  }
}
```

---

### Step 6: Create Progress Bar Component

**File**: `frontend/src/components/ui/progress-bar.tsx` [NEW]

```tsx
import React from 'react'
import { cn } from '@/lib/utils'

interface ProgressBarProps {
  progress: number
  message?: string
  stage?: string
  showPercentage?: boolean
  className?: string
  animated?: boolean
}

export function ProgressBar({
  progress,
  message,
  stage,
  showPercentage = true,
  className,
  animated = true,
}: ProgressBarProps) {
  const clampedProgress = Math.min(100, Math.max(0, progress))

  return (
    <div className={cn('w-full space-y-2', className)}>
      {/* Stage and message */}
      <div className="flex items-center justify-between text-sm">
        <div className="flex items-center gap-2">
          {stage && (
            <span className="font-medium text-primary capitalize">
              {stage.replace('_', ' ')}
            </span>
          )}
          {message && (
            <span className="text-muted-foreground">{message}</span>
          )}
        </div>
        {showPercentage && (
          <span className="font-mono text-xs text-muted-foreground">
            {clampedProgress}%
          </span>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
        <div
          className={cn(
            'h-full bg-primary rounded-full transition-all duration-300 ease-out',
            animated && progress < 100 && 'animate-pulse'
          )}
          style={{ width: `${clampedProgress}%` }}
        />
      </div>
    </div>
  )
}
```

---

### Step 7: Update DashboardView to Use Streaming

**File**: `frontend/src/components/dashboard/DashboardView.tsx` [MODIFY]

Replace the current `handleGenerate` with streaming:

```tsx
// Add imports
import { useStreamingGeneration } from '@/hooks/useStreamingGeneration'
import { ProgressBar } from '@/components/ui/progress-bar'

// Inside DashboardView:

const {
  generate: streamGenerate,
  cancel: cancelGeneration,
  progress,
  isLoading,
} = useStreamingGeneration({
  onComplete: (result) => {
    if (result.success && result.dashboard) {
      setDashboard(result.dashboard)
      setSessionId(result.session_id)
      setError(null)
    } else if (result.error) {
      setError(result.error)
    }
  },
  onError: (err) => {
    setError(err)
  },
})

// Replace handleGenerate:
const handleGenerate = useCallback(async (prompt: string) => {
  setError(null)
  setDashboard(null)
  
  await streamGenerate({
    user_prompt: prompt,
    connection_name: selectedConnection || 'default',
    max_charts: 6,
  })
}, [streamGenerate, selectedConnection])

// In JSX, replace loading skeleton with progress bar:
{isLoading && (
  <Card className="w-full p-6">
    <ProgressBar
      progress={progress.progress}
      stage={progress.stage}
      message={progress.message}
      animated
    />
    {progress.details?.charts_planned && (
      <p className="text-xs text-muted-foreground mt-2">
        Planning {progress.details.charts_planned} charts...
      </p>
    )}
    <Button
      variant="ghost"
      size="sm"
      onClick={cancelGeneration}
      className="mt-4"
    >
      Cancel
    </Button>
  </Card>
)}
```

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/services/sse_utils.py` | NEW | SSE event formatting utilities |
| `backend/langchain_agents/dashboard/graph.py` | MODIFY | Add `stream_dashboard_generation` function |
| `backend/routes/dashboard.py` | MODIFY | Add `/generate/stream` SSE endpoint |
| `frontend/src/types/progress.ts` | NEW | Progress event types |
| `frontend/src/hooks/useStreamingGeneration.ts` | NEW | Hook for SSE consumption |
| `frontend/src/components/ui/progress-bar.tsx` | NEW | Progress bar component |
| `frontend/src/components/dashboard/DashboardView.tsx` | MODIFY | Use streaming generation |

---

## Verification Plan

### Backend Testing

```bash
# Test SSE endpoint with curl
curl -X POST http://localhost:8016/api/dashboard/generate/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"user_prompt": "Show sales by region", "connection_name": "test"}' \
  --no-buffer
```

Expected output:
```
event: progress
data: {"stage": "starting", "progress": 0, "message": "Initializing..."}

event: progress
data: {"stage": "strategy", "progress": 25, "message": "Planning chart objectives..."}

event: progress
data: {"stage": "data", "progress": 50, "message": "Generating and executing SQL..."}

event: progress
data: {"stage": "viz_spec", "progress": 75, "message": "Creating visualizations..."}

event: progress
data: {"stage": "layout", "progress": 100, "message": "Composing dashboard layout..."}

event: complete
data: {"success": true, "session_id": "...", "dashboard": {...}}
```

### Frontend Build Verification

```bash
cd frontend
pnpm build
```

Should complete with no TypeScript errors.

### Manual Testing Checklist

1. **Progress Display**:
   - [ ] Enter a prompt and click generate
   - [ ] Progress bar appears immediately at 0%
   - [ ] Progress updates through 25% → 50% → 75% → 100%
   - [ ] Stage name and message update at each step
   - [ ] Dashboard renders after 100%

2. **Cancellation**:
   - [ ] Click cancel during generation
   - [ ] Progress stops and UI resets
   - [ ] No error displayed

3. **Error Handling**:
   - [ ] Trigger error (e.g., invalid connection)
   - [ ] Error event received and displayed
   - [ ] Progress bar stops

4. **Multiple Generations**:
   - [ ] Generate dashboard A
   - [ ] Generate dashboard B
   - [ ] Each shows independent progress

---

## Implementation Order

1. Create `sse_utils.py` with event formatters
2. Add `stream_dashboard_generation` to `graph.py`
3. Add `/generate/stream` endpoint to `dashboard.py`
4. Create frontend types and hook
5. Create progress bar component
6. Update DashboardView to use streaming
7. Test end-to-end

---

## Notes for Implementation Agent

- SSE requires `text/event-stream` content type
- LangGraph `astream()` yields `{node_name: state_update}` dicts
- Use `X-Accel-Buffering: no` header for nginx compatibility
- Frontend uses fetch + ReadableStream (not EventSource, which is GET-only)
- AbortController allows cancellation
- Progress percentages are fixed per stage (25/50/75/100)
- Backend saves session only on successful completion
