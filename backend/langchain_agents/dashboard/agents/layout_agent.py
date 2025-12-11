"""
Layout Agent for Dashboard Generation.

This agent takes all the individual Vega-Lite specs and composes them
into a final dashboard layout with react-grid-layout compatible positions.

Input: List[SingleVizSpec], user request
Output: ComposedDashboardSpec with individual_specs and layout_config
"""

import json
import time
from typing import Dict, Any, List

from langchain_core.messages import SystemMessage, HumanMessage

from langchain_agents.llm_utils import get_llm
from langchain_agents.dashboard.state import DashboardGraphState
from langchain_agents.dashboard.models import (
    ComposedDashboardSpec,
    LayoutType,
    LayoutConfig,
    ChartLayoutPosition,
)
from prompts import prompt_map
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


def _get_layout_system_prompt() -> str:
    """Get the layout agent system prompt."""
    return prompt_map.get("layout_agent_system_prompt", DEFAULT_LAYOUT_PROMPT)


DEFAULT_LAYOUT_PROMPT = """You are a Dashboard Layout Expert specializing in CSS Grid layouts.

Your task is to arrange charts in a 12-column grid layout. The grid uses react-grid-layout format.

## Chart Position Format

Each chart needs:
- i: chart identifier (use the chart_id)
- x: column position (0-11, left to right)
- y: row position (0-based, top to bottom)
- w: width in columns (1-12)
- h: height in row units (typically 2-4)

## Layout Rules

1. **KPI/Text charts**: 
   - Small (w: 3-4, h: 2)
   - Place at top in a row together
   - Good for showing key metrics

2. **Line/Area charts**:
   - Wide (w: 6-12, h: 3)
   - Best for trends over time
   - Often span full width or half

3. **Bar charts**:
   - Medium (w: 4-6, h: 3)
   - Good for comparisons
   
4. **Pie/Arc charts**:
   - Square-ish (w: 4, h: 3)
   - Use sparingly

5. **Priority placement**:
   - Priority 1 charts: larger, more prominent (top positions)
   - Lower priority: smaller, can be grouped

6. **Balance**:
   - Fill rows completely (total w per row = 12)
   - Keep visual weight balanced

## Output Format

Return JSON with the layout:
```json
{
  "title": "Dashboard Title",
  "description": "What this dashboard shows",
  "layout": [
    {"i": "chart_1", "x": 0, "y": 0, "w": 4, "h": 2},
    {"i": "chart_2", "x": 4, "y": 0, "w": 4, "h": 2},
    {"i": "chart_3", "x": 8, "y": 0, "w": 4, "h": 2},
    {"i": "chart_4", "x": 0, "y": 2, "w": 6, "h": 3},
    {"i": "chart_5", "x": 6, "y": 2, "w": 6, "h": 3}
  ]
}
```
"""


async def layout_agent_node(state: DashboardGraphState) -> Dict[str, Any]:
    """
    Layout Agent node for dashboard generation.

    Composes individual chart specs into a final dashboard.

    Args:
        state: Current dashboard graph state

    Returns:
        Updated state with dashboard_spec
    """
    start_time = time.time()

    user_prompt = state.get("user_prompt", "")
    viz_specs = state.get("viz_specs", [])
    chart_goals = state.get("chart_goals", [])
    theme = state.get("theme", "default")

    if not viz_specs:
        return {
            "error": "No visualization specs provided to Layout Agent",
            "failed_stage": "layout",
        }

    logger.info(f"Layout Agent composing {len(viz_specs)} charts")

    try:
        # For simple cases, use deterministic layout
        if len(viz_specs) <= 3:
            dashboard_spec = _compose_simple_layout(
                viz_specs, chart_goals, user_prompt, theme
            )
        else:
            # For complex layouts, use LLM
            dashboard_spec = await _compose_complex_layout(
                viz_specs, chart_goals, user_prompt, theme
            )

        execution_time = (time.time() - start_time) * 1000

        # Add SQL queries for refresh capability
        sql_queries = []
        chart_data_results = state.get("chart_data_results") or []
        for result in chart_data_results:
            if result and result.get("sql_query"):
                sql_queries.append(
                    {
                        "chart_id": result.get("chart_id"),
                        "sql_query": result.get("sql_query"),
                    }
                )

        dashboard_spec["sql_queries"] = sql_queries

        logger.info(f"Layout Agent composed dashboard in {execution_time:.2f}ms")

        # Calculate total time
        total_time = (
            (state.get("strategy_time_ms") or 0)
            + (state.get("data_time_ms") or 0)
            + (state.get("viz_time_ms") or 0)
            + execution_time
        )

        return {
            "dashboard_spec": dashboard_spec,
            "layout_time_ms": execution_time,
            "total_time_ms": total_time,
        }

    except Exception as e:
        logger.exception(f"Layout Agent failed: {e}")
        return {
            "error": str(e),
            "failed_stage": "layout",
        }


def _compose_simple_layout(
    viz_specs: List[Dict[str, Any]],
    chart_goals: List[Dict[str, Any]],
    user_prompt: str,
    theme: str,
) -> Dict[str, Any]:
    """
    Compose a simple layout for few charts (1-3).
    Uses deterministic grid positions based on chart count.

    Args:
        viz_specs: Individual chart specifications
        chart_goals: Original chart goals
        user_prompt: User's original request
        theme: Dashboard theme

    Returns:
        ComposedDashboardSpec as dict with individual_specs and layout_config
    """
    num_charts = len(viz_specs)
    title = _generate_title(user_prompt, chart_goals)

    # Prepare individual specs with theme config
    individual_specs = []
    for i, spec in enumerate(viz_specs):
        # Ensure spec has a consistent chart_id
        if "chart_id" not in spec:
            spec["chart_id"] = f"chart_{i+1}"

        individual_spec = _prepare_individual_spec(spec, theme)
        individual_specs.append(individual_spec)

    # Generate default layout based on chart count
    layout_positions = []

    if num_charts == 1:
        # Single chart: full width
        layout_positions.append(
            {
                "i": viz_specs[0]["chart_id"],
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 4,
                "minW": 4,
                "minH": 2,
            }
        )
    elif num_charts == 2:
        # Two charts: side by side, half width each
        for i, spec in enumerate(viz_specs):
            layout_positions.append(
                {
                    "i": spec["chart_id"],
                    "x": i * 6,
                    "y": 0,
                    "w": 6,
                    "h": 3,
                    "minW": 3,
                    "minH": 2,
                }
            )
    else:  # 3 charts
        # First chart wider, other two below
        layout_positions.append(
            {
                "i": viz_specs[0]["chart_id"],
                "x": 0,
                "y": 0,
                "w": 12,
                "h": 3,
                "minW": 4,
                "minH": 2,
            }
        )
        for i, spec in enumerate(viz_specs[1:], start=1):
            layout_positions.append(
                {
                    "i": spec["chart_id"],
                    "x": (i - 1) * 6,
                    "y": 3,
                    "w": 6,
                    "h": 3,
                    "minW": 3,
                    "minH": 2,
                }
            )

    layout_config = {
        "cols": 12,
        "row_height": 100,
        "layout": layout_positions,
        "custom": False,
    }

    # Also create backward-compatible vega_lite_spec
    if num_charts == 1:
        vega_lite_spec = _create_single_chart_spec(viz_specs[0], theme)
    elif num_charts == 2:
        vega_lite_spec = _create_hconcat_spec(viz_specs, theme)
    else:
        vega_lite_spec = _create_vconcat_spec(viz_specs, theme)
    vega_lite_spec["title"] = title

    return {
        "title": title,
        "description": f"Dashboard generated from: {user_prompt[:100]}",
        "vega_lite_spec": vega_lite_spec,
        "individual_specs": individual_specs,
        "layout_config": layout_config,
        "layout_type": LayoutType.GRID.value,
        "chart_count": num_charts,
        "sql_queries": [],
    }


def _prepare_individual_spec(spec: Dict[str, Any], theme: str) -> Dict[str, Any]:
    """
    Prepare an individual chart spec for standalone rendering.
    Adds necessary Vega-Lite boilerplate and theme config.
    """
    individual_spec = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "chart_id": spec.get("chart_id", "chart"),
        "title": spec.get("title"),
        "mark": spec.get("mark"),
        "encoding": spec.get("encoding"),
        "data": spec.get("data"),
        "width": "container",
        "height": "container",
        "autosize": {"type": "fit", "contains": "padding"},
        "config": _get_theme_config(theme),
    }

    # Preserve selection for interactivity
    if spec.get("selection"):
        individual_spec["selection"] = spec["selection"]

    # Preserve geoshape-specific fields (projection and transform are critical for maps)
    if spec.get("projection"):
        individual_spec["projection"] = spec["projection"]

    if spec.get("transform"):
        individual_spec["transform"] = spec["transform"]

    return individual_spec


async def _compose_complex_layout(
    viz_specs: List[Dict[str, Any]],
    chart_goals: List[Dict[str, Any]],
    user_prompt: str,
    theme: str,
) -> Dict[str, Any]:
    """
    Use LLM to compose a complex layout for many charts (4+).
    LLM decides optimal grid positions based on chart types and priorities.
    """
    # Get layout recommendation from LLM
    llm = get_llm(temperature=0.3)
    system_prompt = _get_layout_system_prompt()

    # Build chart info for LLM
    charts_info = []
    for i, (spec, goal) in enumerate(
        zip(viz_specs, chart_goals or [{}] * len(viz_specs))
    ):
        chart_type = (
            spec.get("mark", {}).get("type", "bar")
            if isinstance(spec.get("mark"), dict)
            else spec.get("mark", "bar")
        )
        charts_info.append(
            {
                "chart_id": spec.get("chart_id", f"chart_{i+1}"),
                "title": spec.get("title", "Chart"),
                "type": chart_type,
                "priority": goal.get("priority", 1) if goal else 1,
            }
        )

    context = f"""## User Request
{user_prompt}

## Charts to Arrange (in 12-column grid)
{json.dumps(charts_info, indent=2)}

## Number of Charts
{len(viz_specs)}

Create a react-grid-layout compatible layout with positions for each chart.
Remember: x + w should not exceed 12 for any chart. 
Place high-priority charts prominently at the top.
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context),
    ]

    response = await llm.ainvoke(messages)
    response_text = response.content

    logger.debug(f"Layout LLM response: {response_text[:500]}")

    # Parse layout decision
    layout_decision = _parse_layout_decision(response_text, viz_specs)

    title = layout_decision.get("title", _generate_title(user_prompt, chart_goals))
    description = layout_decision.get(
        "description", f"Dashboard for: {user_prompt[:100]}"
    )
    layout_positions = layout_decision.get("layout", [])

    # Prepare individual specs
    individual_specs = []
    for i, spec in enumerate(viz_specs):
        if "chart_id" not in spec:
            spec["chart_id"] = f"chart_{i+1}"
        individual_spec = _prepare_individual_spec(spec, theme)
        individual_specs.append(individual_spec)

    # Validate and ensure all charts have positions
    chart_ids = {spec["chart_id"] for spec in viz_specs}
    positioned_ids = {pos.get("i") for pos in layout_positions}

    # Add fallback positions for any missing charts
    y_offset = max(
        (pos.get("y", 0) + pos.get("h", 2) for pos in layout_positions), default=0
    )
    for i, chart_id in enumerate(chart_ids - positioned_ids):
        layout_positions.append(
            {
                "i": chart_id,
                "x": (i % 2) * 6,
                "y": y_offset + (i // 2) * 3,
                "w": 6,
                "h": 3,
                "minW": 3,
                "minH": 2,
            }
        )

    layout_config = {
        "cols": 12,
        "row_height": 100,
        "layout": layout_positions,
        "custom": False,
    }

    # Also create backward-compatible vega_lite_spec
    vega_lite_spec = _create_grid_spec(viz_specs, [], theme)
    vega_lite_spec["title"] = title

    return {
        "title": title,
        "description": description,
        "vega_lite_spec": vega_lite_spec,
        "individual_specs": individual_specs,
        "layout_config": layout_config,
        "layout_type": LayoutType.GRID.value,
        "chart_count": len(viz_specs),
        "sql_queries": [],
    }


def _parse_layout_decision(
    response_text: str, viz_specs: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Parse layout decision from LLM response.
    Expects JSON with title, description, and layout array.
    """
    import re

    # Try to extract JSON from code block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)

    if json_match:
        try:
            result = json.loads(json_match.group(1))
            if "layout" in result:
                return result
        except:
            pass

    # Try direct JSON extraction
    json_match = re.search(
        r'\{[^{}]*"layout"\s*:\s*\[[^\]]*\][^{}]*\}', response_text, re.DOTALL
    )
    if json_match:
        try:
            result = json.loads(json_match.group(0))
            if "layout" in result:
                return result
        except:
            pass

    # Try to find any JSON array for layout
    array_match = re.search(r'"layout"\s*:\s*(\[[^\]]+\])', response_text, re.DOTALL)
    if array_match:
        try:
            layout = json.loads(array_match.group(1))
            return {"layout": layout, "title": "Dashboard"}
        except:
            pass

    # Fallback: generate default layout
    logger.warning("Failed to parse LLM layout response, using fallback")
    return _generate_fallback_layout(viz_specs)


def _generate_fallback_layout(viz_specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate a sensible default layout when LLM parsing fails.
    Uses a 2-column grid with charts flowing top to bottom.
    """
    layout = []
    num_charts = len(viz_specs)

    for i, spec in enumerate(viz_specs):
        # Ensure we use the exact same ID logic as the main flow
        chart_id = spec.get("chart_id", f"chart_{i+1}")

        # Simple 2-column layout
        layout.append(
            {
                "i": chart_id,
                "x": (i % 2) * 6,
                "y": (i // 2) * 3,
                "w": 6,
                "h": 3,
                "minW": 3,
                "minH": 2,
            }
        )

    return {"title": "Dashboard", "layout": layout}


def _create_single_chart_spec(spec: Dict[str, Any], theme: str) -> Dict[str, Any]:
    """Create a Vega-Lite spec for a single chart."""
    result = {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "mark": spec.get("mark"),
        "encoding": spec.get("encoding"),
        "data": spec.get("data"),
        "width": "container",
        "height": 400,
    }

    if spec.get("selection"):
        result["selection"] = spec["selection"]

    result["config"] = _get_theme_config(theme)

    return result


def _create_hconcat_spec(specs: List[Dict[str, Any]], theme: str) -> Dict[str, Any]:
    """Create a horizontal concatenation layout."""
    charts = []
    for spec in specs:
        chart = {
            "mark": spec.get("mark"),
            "encoding": spec.get("encoding"),
            "data": spec.get("data"),
            "title": spec.get("title"),
            "width": 350,
            "height": 300,
        }
        if spec.get("selection"):
            chart["selection"] = spec["selection"]
        charts.append(chart)

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "hconcat": charts,
        "config": _get_theme_config(theme),
        "spacing": 20,
    }


def _create_vconcat_spec(specs: List[Dict[str, Any]], theme: str) -> Dict[str, Any]:
    """Create a vertical concatenation layout."""
    charts = []
    for spec in specs:
        chart = {
            "mark": spec.get("mark"),
            "encoding": spec.get("encoding"),
            "data": spec.get("data"),
            "title": spec.get("title"),
            "width": "container",
            "height": 250,
        }
        if spec.get("selection"):
            chart["selection"] = spec["selection"]
        charts.append(chart)

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "vconcat": charts,
        "config": _get_theme_config(theme),
        "spacing": 20,
    }


def _create_grid_spec(
    specs: List[Dict[str, Any]], rows: List[List[str]], theme: str
) -> Dict[str, Any]:
    """Create a grid layout."""
    # Map specs by chart_id
    spec_map = {s.get("chart_id"): s for s in specs}

    # Build grid rows
    vconcat_rows = []

    for row_ids in rows:
        row_charts = []
        for chart_id in row_ids:
            spec = spec_map.get(chart_id)
            if spec:
                chart = {
                    "mark": spec.get("mark"),
                    "encoding": spec.get("encoding"),
                    "data": spec.get("data"),
                    "title": spec.get("title"),
                    "width": 350,
                    "height": 250,
                }
                row_charts.append(chart)

        if row_charts:
            if len(row_charts) == 1:
                vconcat_rows.append(row_charts[0])
            else:
                vconcat_rows.append({"hconcat": row_charts})

    # Handle any remaining specs not in rows
    used_ids = set()
    for row in rows:
        used_ids.update(row)

    for spec in specs:
        if spec.get("chart_id") not in used_ids:
            chart = {
                "mark": spec.get("mark"),
                "encoding": spec.get("encoding"),
                "data": spec.get("data"),
                "title": spec.get("title"),
                "width": "container",
                "height": 250,
            }
            vconcat_rows.append(chart)

    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "vconcat": vconcat_rows,
        "config": _get_theme_config(theme),
        "spacing": 20,
    }


def _get_theme_config(theme: str) -> Dict[str, Any]:
    """Get Vega-Lite config for theme."""
    if theme == "dark":
        return {
            "background": "#1a1a2e",
            "axis": {
                "labelColor": "#e0e0e0",
                "titleColor": "#ffffff",
                "gridColor": "#2a2a4a",
            },
            "legend": {
                "labelColor": "#e0e0e0",
                "titleColor": "#ffffff",
            },
            "title": {
                "color": "#ffffff",
            },
            "view": {
                "stroke": "#2a2a4a",
            },
        }
    else:
        return {
            "background": "#ffffff",
            "axis": {
                "labelColor": "#333333",
                "titleColor": "#111111",
                "gridColor": "#e5e5e5",
            },
            "legend": {
                "labelColor": "#333333",
                "titleColor": "#111111",
            },
            "title": {
                "color": "#111111",
                "fontSize": 16,
                "fontWeight": "bold",
            },
            "view": {
                "stroke": "#e5e5e5",
            },
        }


def _generate_title(user_prompt: str, chart_goals: List[Dict[str, Any]]) -> str:
    """Generate a dashboard title from the user prompt."""
    # Simple title extraction
    prompt_lower = user_prompt.lower()

    if "sales" in prompt_lower:
        return "Sales Dashboard"
    elif "revenue" in prompt_lower:
        return "Revenue Analytics"
    elif "customer" in prompt_lower:
        return "Customer Insights"
    elif "product" in prompt_lower:
        return "Product Analysis"
    elif "trend" in prompt_lower:
        return "Trend Analysis"
    elif "performance" in prompt_lower:
        return "Performance Dashboard"
    else:
        # Use first 50 chars of prompt
        title = user_prompt[:50].strip()
        if len(user_prompt) > 50:
            title += "..."
        return f"Dashboard: {title}"
