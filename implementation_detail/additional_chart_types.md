# Implementation Plan: Additional Chart Types

This document provides a step-by-step implementation guide for adding new chart types to the AI Dashboard visualization system.

---

## Overview

**Goal**: Add support for 4 new chart types as specified in `enhancements.md`:
1. **Funnel Charts** - For conversion/pipeline analysis
2. **Treemaps** - Hierarchical data visualization
3. **Gauge Charts** - KPI displays with targets
4. **Combo Charts** - Dual-axis charts (bar + line)

**Excluded**: GeoJSON/Map charts (already removed per user request)

---

## Current Architecture Summary

The visualization pipeline consists of:
1. **Strategy Agent** (`strategy_agent.py`) - Selects chart types based on user intent
2. **Viz Spec Agent** (`viz_spec_agent.py`) - Generates Vega-Lite specifications
3. **System Prompts** (`prompts/`) - LLM instructions for chart generation
4. **Models** (`models.py`) - Pydantic models with ChartType enum
5. **Frontend Renderer** (`ChartRenderer.tsx`) - Renders specs using vega-embed

---

## Implementation Steps

### Step 1: Update ChartType Enum

**File**: `backend/langchain_agents/dashboard/models.py`

**Action**: Add new chart types to the `ChartType` enum.

```python
class ChartType(str, Enum):
    """Supported chart types for Vega-Lite visualization."""

    BAR = "bar"
    LINE = "line"
    AREA = "area"
    PIE = "arc"
    SCATTER = "point"
    KPI = "text"
    HEATMAP = "rect"
    # NEW CHART TYPES
    FUNNEL = "funnel"       # Uses layered bar with calculated widths
    TREEMAP = "treemap"     # Uses rect with treemap transform
    GAUGE = "gauge"         # Uses arc with layered approach
    COMBO = "combo"         # Uses layer with bar + line
```

---

### Step 2: Update Strategy Agent System Prompt

**File**: `backend/prompts/STRATEGY_AGENT_SYSTEM.txt`

**Action**: Add new chart type descriptions to the guidelines section.

**Add the following after the existing chart types (line ~17):**

```markdown
   - `funnel`: For conversion pipelines and stage-based data (shows drop-off at each stage)
   - `treemap`: For hierarchical/part-to-whole data with nested categories
   - `gauge`: For single KPI values with target/threshold comparison
   - `combo`: For comparing two metrics with different scales on dual axes
```

**Update the "Important Rules" section (line ~71):**

```markdown
- chart_type must be one of: bar, line, area, arc, point, text, rect, funnel, treemap, gauge, combo
```

---

### Step 3: Update Viz Spec Agent System Prompt

**File**: `backend/prompts/VIZ_SPEC_AGENT_SYSTEM.txt`

**Action**: Add Vega-Lite spec examples for each new chart type.

**Add after the existing chart examples (after line ~91, before "## Data Types"):**

```markdown
### Funnel Chart (layered approach)
For stage-based conversion data. Use horizontal bars with decreasing widths.
```json
{
  "mark": {"type": "bar", "cornerRadiusEnd": 4},
  "encoding": {
    "y": {"field": "stage", "type": "ordinal", "sort": null, "title": "Stage"},
    "x": {"field": "value", "type": "quantitative", "title": "Count"},
    "color": {"field": "stage", "type": "ordinal", "legend": null}
  }
}
```
Note: Data should be pre-sorted by funnel order. Color gradient gives funnel effect.

### Treemap (mark: rect with treemap transform)
For hierarchical part-to-whole visualization.
```json
{
  "mark": {"type": "rect"},
  "transform": [
    {
      "aggregate": [{"op": "sum", "field": "value", "as": "total"}],
      "groupby": ["category"]
    },
    {
      "window": [{"op": "sum", "field": "total", "as": "sum_total"}],
      "frame": [null, null]
    },
    {
      "calculate": "datum.total / datum.sum_total",
      "as": "percentage"
    }
  ],
  "encoding": {
    "x": {"field": "category", "type": "nominal"},
    "y": {"field": "total", "type": "quantitative"},
    "color": {"field": "category", "type": "nominal"},
    "size": {"field": "total", "type": "quantitative"}
  }
}
```
Note: Vega-Lite doesn't have native treemap. Use sized rectangles or consider Vega for true treemaps.

### Gauge Chart (arc-based approach)
For KPI with target visualization. Uses layered arcs.
```json
{
  "layer": [
    {
      "mark": {"type": "arc", "innerRadius": 60, "outerRadius": 80, "theta": 3.14, "theta2": 0},
      "encoding": {
        "color": {"value": "#e0e0e0"}
      }
    },
    {
      "mark": {"type": "arc", "innerRadius": 60, "outerRadius": 80},
      "encoding": {
        "theta": {"field": "percentage", "type": "quantitative", "scale": {"domain": [0, 1], "range": [0, 3.14]}},
        "color": {"value": "#4CAF50"}
      }
    },
    {
      "mark": {"type": "text", "fontSize": 32, "fontWeight": "bold"},
      "encoding": {
        "text": {"field": "value", "type": "quantitative", "format": ".0%"}
      }
    }
  ]
}
```

### Combo Chart (dual axis with layer)
For comparing two metrics with different scales.
```json
{
  "layer": [
    {
      "mark": {"type": "bar", "opacity": 0.7},
      "encoding": {
        "x": {"field": "date", "type": "temporal"},
        "y": {"field": "revenue", "type": "quantitative", "axis": {"title": "Revenue"}}
      }
    },
    {
      "mark": {"type": "line", "color": "red", "strokeWidth": 2},
      "encoding": {
        "x": {"field": "date", "type": "temporal"},
        "y": {"field": "growth_rate", "type": "quantitative", "axis": {"title": "Growth Rate (%)"}}
      }
    }
  ],
  "resolve": {"scale": {"y": "independent"}}
}
```
```

---

### Step 4: Update Viz Spec Agent Fallback Generation

**File**: `backend/langchain_agents/dashboard/agents/viz_spec_agent.py`

**Action**: Update the `_generate_fallback_viz_spec` function to handle new chart types.

**Modify the `mark_map` dictionary (around line 557):**

```python
mark_map = {
    "bar": {"type": "bar", "cornerRadiusEnd": 4},
    "line": {"type": "line", "point": True},
    "area": {"type": "area", "line": True},
    "arc": {"type": "arc"},
    "point": {"type": "point", "filled": True},
    "text": {"type": "text", "fontSize": 36, "fontWeight": "bold"},
    "rect": {"type": "rect"},
    # New chart types
    "funnel": {"type": "bar", "cornerRadiusEnd": 4},  # Styled horizontal bar
    "treemap": {"type": "rect"},  # Sized rectangles
    "gauge": {"type": "arc", "innerRadius": 50},  # Arc-based
    "combo": {"type": "bar"},  # Default to bar, layer added separately
}
```

**Add new handler functions after `_generate_fallback_viz_spec` (around line 632):**

```python
def _generate_funnel_spec(
    goal: Dict[str, Any], data_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a funnel chart specification.
    
    Funnels show conversion through stages using horizontal bars.
    """
    chart_id = goal.get("chart_id", "unknown")
    title = goal.get("title", "Funnel Chart")
    data = data_result.get("data", [])
    columns = data_result.get("columns", [])
    
    # Determine stage and value fields
    stage_field = goal.get("x_field") or (columns[0] if columns else "stage")
    value_field = goal.get("y_field") or (columns[1] if len(columns) > 1 else "value")
    
    return {
        "chart_id": chart_id,
        "title": title,
        "width": 400,
        "height": 300,
        "mark": {"type": "bar", "cornerRadiusEnd": 4},
        "encoding": {
            "y": {
                "field": stage_field,
                "type": "ordinal",
                "sort": None,  # Preserve data order
                "title": stage_field.replace("_", " ").title(),
            },
            "x": {
                "field": value_field,
                "type": "quantitative",
                "title": value_field.replace("_", " ").title(),
            },
            "color": {
                "field": stage_field,
                "type": "ordinal",
                "scale": {"scheme": "blues"},
                "legend": None,
            },
            "tooltip": [
                {"field": stage_field, "type": "ordinal"},
                {"field": value_field, "type": "quantitative"},
            ],
        },
        "data": {"values": data},
    }


def _generate_gauge_spec(
    goal: Dict[str, Any], data_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a gauge chart specification.
    
    Gauge shows a single value as a percentage of a target.
    """
    chart_id = goal.get("chart_id", "unknown")
    title = goal.get("title", "Gauge")
    data = data_result.get("data", [])
    columns = data_result.get("columns", [])
    
    # Get value from first row
    value_field = goal.get("y_field") or (columns[0] if columns else "value")
    value = data[0].get(value_field, 0) if data else 0
    
    # Normalize to 0-1 range if greater than 1
    if value > 1:
        max_val = goal.get("filters", {}).get("max", 100)
        normalized = min(value / max_val, 1.0)
    else:
        normalized = value
    
    return {
        "chart_id": chart_id,
        "title": title,
        "width": 200,
        "height": 200,
        "layer": [
            {
                "mark": {
                    "type": "arc",
                    "innerRadius": 60,
                    "outerRadius": 80,
                    "theta": 3.14159,
                    "theta2": 0,
                },
                "encoding": {"color": {"value": "#e0e0e0"}},
            },
            {
                "mark": {"type": "arc", "innerRadius": 60, "outerRadius": 80},
                "encoding": {
                    "theta": {
                        "datum": normalized * 3.14159,
                        "type": "quantitative",
                    },
                    "theta2": {"datum": 0},
                    "color": {
                        "value": "#4CAF50" if normalized >= 0.7 else "#FFC107" if normalized >= 0.4 else "#F44336"
                    },
                },
            },
            {
                "mark": {"type": "text", "fontSize": 32, "fontWeight": "bold", "baseline": "middle"},
                "encoding": {
                    "text": {"value": f"{value:.1%}" if value <= 1 else f"{value:,.0f}"},
                },
            },
        ],
        "data": {"values": [{}]},  # Minimal data for layered spec
    }


def _generate_combo_spec(
    goal: Dict[str, Any], data_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a combo (dual-axis) chart specification.
    
    Combines bar and line charts with independent scales.
    """
    chart_id = goal.get("chart_id", "unknown")
    title = goal.get("title", "Combo Chart")
    data = data_result.get("data", [])
    columns = data_result.get("columns", [])
    
    # Need at least 3 columns: x, y1 (bar), y2 (line)
    x_field = goal.get("x_field") or (columns[0] if columns else "x")
    y1_field = goal.get("y_field") or (columns[1] if len(columns) > 1 else "y1")
    y2_field = goal.get("color_field") or (columns[2] if len(columns) > 2 else y1_field)
    
    return {
        "chart_id": chart_id,
        "title": title,
        "width": 400,
        "height": 300,
        "layer": [
            {
                "mark": {"type": "bar", "opacity": 0.7, "cornerRadiusEnd": 4},
                "encoding": {
                    "x": {"field": x_field, "type": "ordinal" if not any(kw in x_field.lower() for kw in ["date", "time"]) else "temporal"},
                    "y": {
                        "field": y1_field,
                        "type": "quantitative",
                        "axis": {"title": y1_field.replace("_", " ").title()},
                    },
                    "tooltip": [
                        {"field": x_field, "type": "nominal"},
                        {"field": y1_field, "type": "quantitative"},
                    ],
                },
            },
            {
                "mark": {"type": "line", "color": "#E53935", "strokeWidth": 2, "point": True},
                "encoding": {
                    "x": {"field": x_field, "type": "ordinal" if not any(kw in x_field.lower() for kw in ["date", "time"]) else "temporal"},
                    "y": {
                        "field": y2_field,
                        "type": "quantitative",
                        "axis": {"title": y2_field.replace("_", " ").title()},
                    },
                    "tooltip": [
                        {"field": x_field, "type": "nominal"},
                        {"field": y2_field, "type": "quantitative"},
                    ],
                },
            },
        ],
        "resolve": {"scale": {"y": "independent"}},
        "data": {"values": data},
    }


def _generate_treemap_spec(
    goal: Dict[str, Any], data_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a treemap-style chart specification.
    
    Note: True treemaps require Vega. This creates a sized-bar approximation.
    """
    chart_id = goal.get("chart_id", "unknown")
    title = goal.get("title", "Treemap")
    data = data_result.get("data", [])
    columns = data_result.get("columns", [])
    
    category_field = goal.get("x_field") or (columns[0] if columns else "category")
    value_field = goal.get("y_field") or (columns[1] if len(columns) > 1 else "value")
    
    return {
        "chart_id": chart_id,
        "title": title,
        "width": 400,
        "height": 300,
        "mark": {"type": "bar", "cornerRadiusEnd": 4},
        "encoding": {
            "x": {
                "field": value_field,
                "type": "quantitative",
                "title": value_field.replace("_", " ").title(),
            },
            "y": {
                "field": category_field,
                "type": "nominal",
                "sort": "-x",
                "title": category_field.replace("_", " ").title(),
            },
            "color": {
                "field": category_field,
                "type": "nominal",
                "scale": {"scheme": "tableau20"},
            },
            "tooltip": [
                {"field": category_field, "type": "nominal"},
                {"field": value_field, "type": "quantitative"},
            ],
        },
        "data": {"values": data},
    }
```

**Update `_generate_fallback_viz_spec` to call new functions (add before the return statement, around line 570):**

```python
    # Handle new chart types
    if chart_type == "funnel":
        return _generate_funnel_spec(goal, data_result)
    if chart_type == "gauge":
        return _generate_gauge_spec(goal, data_result)
    if chart_type == "combo":
        return _generate_combo_spec(goal, data_result)
    if chart_type == "treemap":
        return _generate_treemap_spec(goal, data_result)
```

---

### Step 5: Update Default Viz Spec Prompt (Fallback)

**File**: `backend/langchain_agents/dashboard/agents/viz_spec_agent.py`

**Action**: Update the `DEFAULT_VIZ_SPEC_PROMPT` constant to include new chart types.

**Modify line 38:**

```python
- `mark`: The visual mark type (bar, line, area, arc, point, text, rect)
+ `mark`: The visual mark type (bar, line, area, arc, point, text, rect, layer)
```

**Add after line 85 (after KPI example):**

```python
### Funnel Charts (horizontal bar, ordered)
```json
{
  "mark": {"type": "bar"},
  "encoding": {
    "y": {"field": "stage", "type": "ordinal", "sort": null},
    "x": {"field": "count", "type": "quantitative"},
    "color": {"field": "stage", "type": "ordinal", "legend": null}
  }
}
```

### Combo Charts (layered bar + line)
For dual-axis comparisons, use "layer" instead of a single mark.
Return a specification with "layer" array containing bar and line specs.
```

---


### Step 7: Frontend Verification (No Changes Required)

The frontend `ChartRenderer.tsx` uses `vega-embed` which automatically handles:
- Standard Vega-Lite marks (bar, line, arc, rect, etc.)
- Layered specifications
- Transforms and aggregations

**No changes required** to the frontend as all new chart types use standard Vega-Lite constructs.

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `backend/langchain_agents/dashboard/models.py` | MODIFY | Add new chart types to ChartType enum |
| `backend/prompts/STRATEGY_AGENT_SYSTEM.txt` | MODIFY | Add chart type descriptions |
| `backend/prompts/VIZ_SPEC_AGENT_SYSTEM.txt` | MODIFY | Add spec examples for new types |
| `backend/langchain_agents/dashboard/agents/viz_spec_agent.py` | MODIFY | Add fallback generators for new types |

---

## Verification Plan

### Automated Testing

Run existing tests to ensure no regressions:

```bash
cd backend
pytest tests/ -v
```

### Manual Testing

1. **Start the application**:
   ```bash
   # In one terminal
   cd backend && make dev
   
   # In another terminal  
   cd frontend && pnpm dev
   ```

2. **Test each new chart type** by entering prompts that should trigger them:

   - **Funnel**: "Show me a conversion funnel from visitors to purchases"
   - **Gauge**: "Show the percentage of target achieved this month"
   - **Combo**: "Compare monthly revenue with growth rate on dual axis"
   - **Treemap**: "Show sales distribution by category as a treemap"

3. **Verify fallback behavior**: Test with minimal data to ensure fallback specs generate correctly.

---

## Implementation Order

1. **Step 1**: Update `models.py` - Add ChartType enum values
2. **Step 2**: Update `STRATEGY_AGENT_SYSTEM.txt` - LLM can now suggest new types
3. **Step 3**: Update `VIZ_SPEC_AGENT_SYSTEM.txt` - LLM can generate specs
4. **Step 4**: Update `viz_spec_agent.py` - Add fallback generators
5. **Step 5**: Update default prompt in `viz_spec_agent.py`
7. **Step 7**: Test all changes

---

## Notes for Implementation Agent

- All code snippets are complete and copy-paste ready
- Line numbers are approximate - search for the referenced code patterns
- Maintain existing code style (4-space indentation for Python, type hints)
- Run `black` formatter after making changes
- Test each change incrementally before proceeding
