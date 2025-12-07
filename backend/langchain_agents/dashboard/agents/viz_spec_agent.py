"""
Viz Spec Agent for Dashboard Generation.

This agent takes raw data and chart goals to generate Vega-Lite specifications
for each individual chart.

Input: ChartDataResult (one at a time)
Output: SingleVizSpec (Vega-Lite JSON)
"""

import json
import time
from typing import Dict, Any, List

from langchain_core.messages import SystemMessage, HumanMessage

from langchain_agents.llm_utils import get_llm
from langchain_agents.dashboard.state import DashboardGraphState
from langchain_agents.dashboard.models import SingleVizSpec
from prompts import prompt_map
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


def _get_viz_spec_system_prompt() -> str:
    """Get the viz spec agent system prompt."""
    return prompt_map.get("viz_spec_agent_system_prompt", DEFAULT_VIZ_SPEC_PROMPT)


DEFAULT_VIZ_SPEC_PROMPT = """You are a Vega-Lite Visualization Expert.

Your task is to create Vega-Lite specifications that accurately visualize data for dashboard charts.

## Vega-Lite Basics

A Vega-Lite spec has these components:
- `mark`: The visual mark type (bar, line, area, arc, point, text, rect)
- `encoding`: Maps data fields to visual channels (x, y, color, theta, radius)
- `data`: The data to visualize (values array)

## Chart Type Guidelines

### Bar Charts (mark: "bar")
```json
{
  "mark": {"type": "bar", "cornerRadiusEnd": 4},
  "encoding": {
    "x": {"field": "category", "type": "nominal", "title": "Category"},
    "y": {"field": "value", "type": "quantitative", "title": "Value"}
  }
}
```

### Line Charts (mark: "line")
```json
{
  "mark": {"type": "line", "point": true},
  "encoding": {
    "x": {"field": "date", "type": "temporal", "title": "Date"},
    "y": {"field": "value", "type": "quantitative", "title": "Value"}
  }
}
```

### Pie Charts (mark: "arc")
```json
{
  "mark": {"type": "arc", "innerRadius": 50},
  "encoding": {
    "theta": {"field": "value", "type": "quantitative"},
    "color": {"field": "category", "type": "nominal"}
  }
}
```

### KPI/Text (mark: "text")
```json
{
  "mark": {"type": "text", "fontSize": 48, "fontWeight": "bold"},
  "encoding": {
    "text": {"field": "value", "type": "quantitative", "format": ",.0f"}
  }
}
```

## Data Types
- `quantitative`: Numbers (for aggregation, axes)
- `nominal`: Categories (unordered)
- `ordinal`: Categories (ordered)
- `temporal`: Dates/times

## Output Format
Return ONLY a valid JSON object with this structure:
```json
{
  "chart_id": "chart_1",
  "mark": {"type": "bar"},
  "encoding": {...},
  "title": "Chart Title",
  "width": 400,
  "height": 300
}
```

Important:
- Do NOT include $schema or data in your response (they will be added automatically)
- Use appropriate field types based on the data
- Add meaningful titles and axis labels
- Use color encoding for multi-series data
"""


async def viz_spec_agent_node(state: DashboardGraphState) -> Dict[str, Any]:
    """
    Viz Spec Agent node for dashboard generation.
    
    Creates Vega-Lite specifications for each chart based on data.
    
    Args:
        state: Current dashboard graph state
        
    Returns:
        Updated state with viz_specs
    """
    start_time = time.time()
    
    chart_goals = state.get("chart_goals", [])
    chart_data_results = state.get("chart_data_results", [])
    
    if not chart_data_results:
        return {
            "error": "No chart data provided to Viz Spec Agent",
            "failed_stage": "viz_spec",
        }
    
    logger.info(f"Viz Spec Agent processing {len(chart_data_results)} charts")
    
    try:
        viz_specs = []
        llm = get_llm(temperature=0.2)
        system_prompt = _get_viz_spec_system_prompt()
        
        # Process each chart
        for data_result in chart_data_results:
            chart_id = data_result.get("chart_id", "unknown")
            
            # Skip failed queries
            if data_result.get("error"):
                logger.warning(f"Skipping {chart_id} due to data error: {data_result['error']}")
                continue
            
            # Find matching goal
            goal = next((g for g in chart_goals if g.get("chart_id") == chart_id), None)
            if not goal:
                logger.warning(f"No goal found for {chart_id}")
                continue
            
            # Generate viz spec
            spec = await _generate_single_viz_spec(
                llm, system_prompt, goal, data_result
            )
            
            if spec:
                viz_specs.append(spec)
        
        execution_time = (time.time() - start_time) * 1000
        
        if not viz_specs:
            return {
                "error": "Failed to generate any visualization specifications",
                "failed_stage": "viz_spec",
            }
        
        logger.info(f"Viz Spec Agent generated {len(viz_specs)} specs in {execution_time:.2f}ms")
        
        return {
            "viz_specs": viz_specs,
            "viz_time_ms": execution_time,
        }
        
    except Exception as e:
        logger.exception(f"Viz Spec Agent failed: {e}")
        return {
            "error": str(e),
            "failed_stage": "viz_spec",
        }


async def _generate_single_viz_spec(
    llm,
    system_prompt: str,
    goal: Dict[str, Any],
    data_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Generate a Vega-Lite spec for a single chart.
    
    Args:
        llm: LLM instance
        system_prompt: System prompt for viz generation
        goal: Chart goal from strategy agent
        data_result: Data from data agent
        
    Returns:
        SingleVizSpec as dict, or None if failed
    """
    chart_id = goal.get("chart_id", "unknown")
    chart_type = goal.get("chart_type", "bar")
    title = goal.get("title", "Chart")
    
    # Prepare data sample for context (limit to 10 rows)
    data = data_result.get("data", [])
    columns = data_result.get("columns", [])
    sample_data = data[:10] if len(data) > 10 else data
    
    context = f"""## Chart Goal
- Chart ID: {chart_id}
- Type: {chart_type}
- Title: {title}
- Description: {goal.get('description', '')}

## Data Fields
Columns: {', '.join(columns)}

## Sample Data (first {len(sample_data)} rows)
```json
{json.dumps(sample_data, indent=2, default=str)[:2000]}
```

## Requirements
- X Field: {goal.get('x_field', 'Auto-detect')}
- Y Field: {goal.get('y_field', 'Auto-detect')}
- Color Field: {goal.get('color_field', 'None')}
- Aggregation: {goal.get('aggregation', 'none')}

Generate a Vega-Lite specification for this chart.
"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=context),
    ]
    
    try:
        response = await llm.ainvoke(messages)
        response_text = response.content
        
        # Parse the spec
        spec = _parse_viz_spec_response(response_text, chart_id, data)
        
        if spec:
            spec["title"] = title
            return spec
        
    except Exception as e:
        logger.error(f"Failed to generate viz spec for {chart_id}: {e}")
    
    # Fallback: generate a basic spec
    return _generate_fallback_viz_spec(goal, data_result)


def _parse_viz_spec_response(response_text: str, chart_id: str, data: List[Dict]) -> Dict[str, Any]:
    """Parse Vega-Lite spec from LLM response."""
    import re
    
    # Try to extract JSON from code block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r"\{[\s\S]*\"mark\"[\s\S]*\}", response_text)
        if json_match:
            json_str = json_match.group(0)
        else:
            return None
    
    try:
        spec = json.loads(json_str)
        
        # Ensure required fields
        if "mark" not in spec:
            return None
        if "encoding" not in spec:
            return None
        
        # Add chart_id and data
        spec["chart_id"] = chart_id
        spec["data"] = {"values": data}
        
        # Set defaults
        if "width" not in spec:
            spec["width"] = 400
        if "height" not in spec:
            spec["height"] = 300
        
        return spec
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse viz spec JSON: {e}")
        return None


def _generate_fallback_viz_spec(goal: Dict[str, Any], data_result: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a basic fallback visualization spec."""
    chart_id = goal.get("chart_id", "unknown")
    chart_type = goal.get("chart_type", "bar")
    title = goal.get("title", "Chart")
    data = data_result.get("data", [])
    columns = data_result.get("columns", [])
    
    # Map chart type to Vega-Lite mark
    mark_map = {
        "bar": {"type": "bar", "cornerRadiusEnd": 4},
        "line": {"type": "line", "point": True},
        "area": {"type": "area", "line": True},
        "arc": {"type": "arc", "innerRadius": 50},
        "point": {"type": "point", "filled": True},
        "text": {"type": "text", "fontSize": 36, "fontWeight": "bold"},
        "rect": {"type": "rect"},
    }
    
    mark = mark_map.get(chart_type, {"type": "bar"})
    
    # Determine encoding based on columns
    x_field = goal.get("x_field") or (columns[0] if columns else "x")
    y_field = goal.get("y_field") or (columns[1] if len(columns) > 1 else columns[0] if columns else "y")
    
    # Detect field types
    def infer_type(field_name: str, sample_data: List[Dict]) -> str:
        if not sample_data:
            return "nominal"
        value = sample_data[0].get(field_name)
        if isinstance(value, (int, float)):
            return "quantitative"
        if "date" in field_name.lower() or "time" in field_name.lower():
            return "temporal"
        return "nominal"
    
    x_type = infer_type(x_field, data[:5])
    y_type = infer_type(y_field, data[:5])
    
    # Build encoding
    if chart_type == "arc":
        encoding = {
            "theta": {"field": y_field, "type": "quantitative"},
            "color": {"field": x_field, "type": "nominal"},
        }
    elif chart_type == "text":
        # KPI - single value
        encoding = {
            "text": {"field": y_field, "type": "quantitative", "format": ",.0f"}
        }
    else:
        encoding = {
            "x": {"field": x_field, "type": x_type, "title": x_field.replace("_", " ").title()},
            "y": {"field": y_field, "type": y_type, "title": y_field.replace("_", " ").title()},
        }
        
        # Add color if specified
        color_field = goal.get("color_field")
        if color_field:
            encoding["color"] = {"field": color_field, "type": "nominal"}
    
    return {
        "chart_id": chart_id,
        "mark": mark,
        "encoding": encoding,
        "data": {"values": data},
        "title": title,
        "width": 400,
        "height": 300,
    }
