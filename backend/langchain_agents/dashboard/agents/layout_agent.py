"""
Layout Agent for Dashboard Generation.

This agent takes all the individual Vega-Lite specs and composes them
into a final dashboard layout.

Input: List[SingleVizSpec], user request
Output: ComposedDashboardSpec (full dashboard JSON)
"""

import json
import time
from typing import Dict, Any, List

from langchain_core.messages import SystemMessage, HumanMessage

from langchain_agents.llm_utils import get_llm
from langchain_agents.dashboard.state import DashboardGraphState
from langchain_agents.dashboard.models import ComposedDashboardSpec, LayoutType
from prompts import prompt_map
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


def _get_layout_system_prompt() -> str:
    """Get the layout agent system prompt."""
    return prompt_map.get("layout_agent_system_prompt", DEFAULT_LAYOUT_PROMPT)


DEFAULT_LAYOUT_PROMPT = """You are a Dashboard Layout Expert.

Your task is to compose individual Vega-Lite chart specifications into a cohesive dashboard layout.

## Layout Options

1. **hconcat**: Horizontal concatenation (charts side by side)
   - Best for: 2-3 charts of similar size
   - Use when comparing related metrics

2. **vconcat**: Vertical concatenation (charts stacked)
   - Best for: Sequential analysis, timeline views
   - Use when charts build on each other

3. **Grid (nested hconcat/vconcat)**: Grid arrangement
   - Best for: 4+ charts
   - Create rows using vconcat, columns using hconcat

## Layout Guidelines

1. **Priority-based placement**: 
   - Priority 1 charts should be largest/most prominent
   - Lower priority charts can be smaller

2. **Visual balance**:
   - Balance chart sizes across the layout
   - Group related charts together

3. **Responsive sizing**:
   - Use "container" for width when possible
   - Avoid fixed pixel widths for flexibility

## Output Format

Return a JSON object describing the layout decision:
```json
{
  "layout_type": "hconcat",
  "arrangement": ["chart_1", "chart_2", "chart_3"],
  "title": "Dashboard Title",
  "description": "What this dashboard shows"
}
```

For grid layouts:
```json
{
  "layout_type": "grid",
  "rows": [
    ["chart_1", "chart_2"],
    ["chart_3", "chart_4"]
  ],
  "title": "Dashboard Title"
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
        for result in state.get("chart_data_results", []):
            if result.get("sql_query"):
                sql_queries.append({
                    "chart_id": result.get("chart_id"),
                    "sql_query": result.get("sql_query"),
                })
        
        dashboard_spec["sql_queries"] = sql_queries
        
        logger.info(f"Layout Agent composed dashboard in {execution_time:.2f}ms")
        
        # Calculate total time
        total_time = (
            state.get("strategy_time_ms", 0) +
            state.get("data_time_ms", 0) +
            state.get("viz_time_ms", 0) +
            execution_time
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
    Compose a simple layout for few charts.
    
    Args:
        viz_specs: Individual chart specifications
        chart_goals: Original chart goals
        user_prompt: User's original request
        theme: Dashboard theme
        
    Returns:
        ComposedDashboardSpec as dict
    """
    num_charts = len(viz_specs)
    
    # Determine layout type
    if num_charts == 1:
        layout_type = LayoutType.SINGLE
        vega_lite_spec = _create_single_chart_spec(viz_specs[0], theme)
    elif num_charts == 2:
        layout_type = LayoutType.HCONCAT
        vega_lite_spec = _create_hconcat_spec(viz_specs, theme)
    else:
        layout_type = LayoutType.VCONCAT
        vega_lite_spec = _create_vconcat_spec(viz_specs, theme)
    
    # Generate title from user prompt
    title = _generate_title(user_prompt, chart_goals)
    vega_lite_spec["title"] = title
    
    return {
        "title": title,
        "description": f"Dashboard generated from: {user_prompt[:100]}",
        "vega_lite_spec": vega_lite_spec,
        "layout_type": layout_type.value,
        "chart_count": num_charts,
        "sql_queries": [],
    }


async def _compose_complex_layout(
    viz_specs: List[Dict[str, Any]],
    chart_goals: List[Dict[str, Any]],
    user_prompt: str,
    theme: str,
) -> Dict[str, Any]:
    """
    Use LLM to compose a complex layout for many charts.
    """
    # Get layout recommendation from LLM
    llm = get_llm(temperature=0.3)
    system_prompt = _get_layout_system_prompt()
    
    charts_info = []
    for i, (spec, goal) in enumerate(zip(viz_specs, chart_goals or [{}] * len(viz_specs))):
        charts_info.append({
            "chart_id": spec.get("chart_id", f"chart_{i+1}"),
            "title": spec.get("title", "Chart"),
            "type": spec.get("mark", {}).get("type", "bar") if isinstance(spec.get("mark"), dict) else spec.get("mark", "bar"),
            "priority": goal.get("priority", 1) if goal else 1,
        })
    
    context = f"""## User Request
{user_prompt}

## Charts to Arrange
{json.dumps(charts_info, indent=2)}

## Number of Charts
{len(viz_specs)}

Decide the best layout arrangement for these charts.
"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context),
    ]
    
    response = await llm.ainvoke(messages)
    response_text = response.content
    
    # Parse layout decision
    layout_decision = _parse_layout_decision(response_text)
    
    # Apply layout
    layout_type = layout_decision.get("layout_type", "vconcat")
    title = layout_decision.get("title", _generate_title(user_prompt, chart_goals))
    
    if layout_type == "grid":
        rows = layout_decision.get("rows", [])
        vega_lite_spec = _create_grid_spec(viz_specs, rows, theme)
        layout_type_enum = LayoutType.GRID
    elif layout_type == "hconcat":
        vega_lite_spec = _create_hconcat_spec(viz_specs, theme)
        layout_type_enum = LayoutType.HCONCAT
    else:
        vega_lite_spec = _create_vconcat_spec(viz_specs, theme)
        layout_type_enum = LayoutType.VCONCAT
    
    vega_lite_spec["title"] = title
    
    return {
        "title": title,
        "description": layout_decision.get("description", f"Dashboard for: {user_prompt[:100]}"),
        "vega_lite_spec": vega_lite_spec,
        "layout_type": layout_type_enum.value,
        "chart_count": len(viz_specs),
        "sql_queries": [],
    }


def _parse_layout_decision(response_text: str) -> Dict[str, Any]:
    """Parse layout decision from LLM response."""
    import re
    
    # Try to extract JSON
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except:
            pass
    
    # Try direct JSON
    json_match = re.search(r"\{[\s\S]*\"layout_type\"[\s\S]*\}", response_text)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except:
            pass
    
    # Default
    return {"layout_type": "vconcat", "title": "Dashboard"}


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
    specs: List[Dict[str, Any]], 
    rows: List[List[str]], 
    theme: str
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
