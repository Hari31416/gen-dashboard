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
    session_id = state.get("session_id", "")
    
    if not chart_data_results:
        return {
            "error": "No chart data provided to Viz Spec Agent",
            "failed_stage": "viz_spec",
        }
    
    logger.info(f"Viz Spec Agent processing {len(chart_data_results)} charts")
    
    try:
        llm = get_llm(temperature=0.2)
        system_prompt = _get_viz_spec_system_prompt()
        
        # Build list of valid charts to process in parallel
        import asyncio
        
        async def process_chart(data_result):
            chart_id = data_result.get("chart_id", "unknown")
            
            # Skip failed queries
            if data_result.get("error"):
                logger.warning(f"Skipping {chart_id} due to data error: {data_result['error']}")
                return None
            
            # Find matching goal
            goal = next((g for g in chart_goals if g.get("chart_id") == chart_id), None)
            if not goal:
                logger.warning(f"No goal found for {chart_id}")
                return None
            
            # Generate viz spec with URL-based data loading
            return await _generate_single_viz_spec(
                llm, system_prompt, goal, data_result, session_id
            )
        
        # Run all spec generations in parallel
        results = await asyncio.gather(*[process_chart(dr) for dr in chart_data_results])
        
        # Filter out None results
        viz_specs = [spec for spec in results if spec is not None]
        
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
    session_id: str = "",
) -> Dict[str, Any]:
    """
    Generate a Vega-Lite spec for a single chart.
    
    Args:
        llm: LLM instance
        system_prompt: System prompt for viz generation
        goal: Chart goal from strategy agent
        data_result: Data from data agent
        session_id: Session ID for URL-based data loading
        
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
        
        # Parse the spec and use URL-based data loading
        spec = _parse_viz_spec_response(response_text, chart_id, data, goal, session_id)
        
        if spec:
            spec["title"] = title
            return spec
        
    except Exception as e:
        logger.error(f"Failed to generate viz spec for {chart_id}: {e}")
    
    # Fallback: generate a basic spec
    return _generate_fallback_viz_spec(goal, data_result)


def _parse_viz_spec_response(
    response_text: str, 
    chart_id: str, 
    data: List[Dict],
    goal: Dict[str, Any] = None,
    session_id: str = ""
) -> Dict[str, Any]:
    """Parse Vega-Lite spec from LLM response and use URL-based data loading."""
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
        
        # Add chart_id
        spec["chart_id"] = chart_id
        
        # Check if this is a geoshape (map) chart
        mark = spec.get("mark", {})
        mark_type = mark.get("type") if isinstance(mark, dict) else mark
        
        logger.info(f"Parsed viz spec for {chart_id}: mark_type={mark_type}")
        
        if mark_type == "geoshape":
            # Transform to proper geoshape spec with GeoJSON
            logger.info(f"Applying geoshape transformation for {chart_id}")
            spec = _transform_to_geoshape_spec(spec, data, goal, chart_id, session_id)
            logger.info(f"Geoshape spec has projection={spec.get('projection')}, transform={bool(spec.get('transform'))}")
        else:
            # Use URL-based data loading if session_id is available
            if session_id:
                # Use full backend URL for Vega to fetch data
                from env import BACKEND_URL
                spec["data"] = {
                    "url": f"{BACKEND_URL}/dashboard/{session_id}/chart/{chart_id}/data"
                }
            else:
                # Fallback to inline data if no session_id
                spec["data"] = {"values": data}
        
        # Set defaults
        if "width" not in spec:
            spec["width"] = 400 if mark_type != "geoshape" else 500
        if "height" not in spec:
            spec["height"] = 300 if mark_type != "geoshape" else 400
        
        return spec
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse viz spec JSON: {e}")
        return None


def _transform_to_geoshape_spec(
    spec: Dict[str, Any], 
    data: List[Dict], 
    goal: Dict[str, Any] = None,
    chart_id: str = "",
    session_id: str = ""
) -> Dict[str, Any]:
    """
    Transform an LLM-generated geoshape spec to include proper GeoJSON loading.
    
    The LLM generates the encoding but not the GeoJSON URL/transform structure.
    This function adds the necessary data source and lookup transform.
    """
    from services.geojson_service import get_geojson_config
    from env import BACKEND_URL
    
    goal = goal or {}
    
    # Get geography configuration
    geography_level = goal.get("geography_level", "us")  # Default to US for testing
    geography_field = goal.get("geography_field")
    target_state = goal.get("target_state")
    
    geojson_config = get_geojson_config(geography_level, target_state)
    geojson_url = geojson_config["url"]
    feature_key = geojson_config["feature_key"]
    
    # Find the geography field from data if not specified
    if not geography_field and data:
        columns = list(data[0].keys()) if data else []
        # Common geography field patterns
        for pattern in ["state", "province", "territory", "district", "region", "country", "area", "location", "name"]:
            for col in columns:
                if pattern in col.lower():
                    geography_field = col
                    break
            if geography_field:
                break
        if not geography_field:
            geography_field = columns[0] if columns else "state"
    
    # Find the value field from encoding
    value_field = None
    encoding = spec.get("encoding", {})
    if "color" in encoding:
        value_field = encoding["color"].get("field")
    
    if not value_field and data:
        # Find first numeric column
        for key, val in data[0].items():
            if isinstance(val, (int, float)) and key != geography_field:
                value_field = key
                break
    
    value_field = value_field or "value"
    
    # Build data source for lookup transform - use URL if session_id available
    if session_id and chart_id:
        lookup_data = {"url": f"{BACKEND_URL}/dashboard/{session_id}/chart/{chart_id}/data"}
    else:
        lookup_data = {"values": data}
    
    # Build the proper geoshape spec
    transformed_spec = {
        "chart_id": spec.get("chart_id", "map"),
        "title": spec.get("title", "Map"),
        "width": 500,
        "height": 400,
        "projection": spec.get("projection", {"type": "mercator"}),
        "data": {
            "url": geojson_url,
            "format": {"type": "json", "property": "features"}
        },
        "transform": [
            {
                "lookup": f"properties.{feature_key}",
                "from": {
                    "data": lookup_data,
                    "key": geography_field,
                    "fields": [value_field]
                }
            }
        ],
        "mark": spec.get("mark", {"type": "geoshape", "stroke": "white", "strokeWidth": 0.5}),
        "encoding": {
            "color": {
                "field": value_field,
                "type": "quantitative",
                "scale": {"scheme": "blues"},
                "title": value_field.replace("_", " ").title()
            },
            "tooltip": [
                {"field": f"properties.{feature_key}", "type": "nominal", "title": "Region"},
                {"field": value_field, "type": "quantitative", "title": value_field.replace("_", " ").title()}
            ]
        }
    }
    
    # Preserve any custom color scale from LLM
    if "color" in encoding and "scale" in encoding["color"]:
        transformed_spec["encoding"]["color"]["scale"] = encoding["color"]["scale"]
    
    return transformed_spec


def _generate_fallback_viz_spec(goal: Dict[str, Any], data_result: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a basic fallback visualization spec."""
    from services.geojson_service import get_geojson_config
    
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
        "geoshape": {"type": "geoshape", "stroke": "white", "strokeWidth": 0.5},
    }
    
    mark = mark_map.get(chart_type, {"type": "bar"})
    
    # Handle geoshape (choropleth map) specially
    if chart_type == "geoshape":
        return _generate_geoshape_spec(goal, data_result)
    
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


def _generate_geoshape_spec(goal: Dict[str, Any], data_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a Vega-Lite geoshape (choropleth map) specification.
    
    Uses external GeoJSON with lookup transform to join data.
    """
    from services.geojson_service import get_geojson_config
    
    chart_id = goal.get("chart_id", "unknown")
    title = goal.get("title", "Map")
    data = data_result.get("data", [])
    columns = data_result.get("columns", [])
    
    # Get geography configuration
    geography_level = goal.get("geography_level", "country")
    geography_field = goal.get("geography_field")
    target_state = goal.get("target_state")
    
    geojson_config = get_geojson_config(geography_level, target_state)
    geojson_url = geojson_config["url"]
    feature_key = geojson_config["feature_key"]
    
    # Determine the value field (y_field typically contains the metric)
    value_field = goal.get("y_field")
    if not value_field:
        # Find first numeric column
        for col in columns:
            if data and isinstance(data[0].get(col), (int, float)):
                value_field = col
                break
        if not value_field:
            value_field = columns[1] if len(columns) > 1 else columns[0] if columns else "value"
    
    # If no geography_field specified, try to detect
    if not geography_field:
        # Common geography field patterns
        for pattern in ["state", "district", "region", "area", "location", "name"]:
            for col in columns:
                if pattern in col.lower():
                    geography_field = col
                    break
            if geography_field:
                break
        if not geography_field:
            geography_field = columns[0] if columns else "state"
    
    # Build the Vega-Lite spec with lookup transform
    # The GeoJSON is the primary data source, and we lookup values from our data
    spec = {
        "chart_id": chart_id,
        "title": title,
        "width": 500,
        "height": 400,
        "projection": {"type": "mercator"},
        "data": {
            "url": geojson_url,
            "format": {"type": "json", "property": "features"}
        },
        "transform": [
            {
                "lookup": f"properties.{feature_key}",
                "from": {
                    "data": {"values": data},
                    "key": geography_field,
                    "fields": [value_field]
                }
            }
        ],
        "mark": {"type": "geoshape", "stroke": "white", "strokeWidth": 0.5},
        "encoding": {
            "color": {
                "field": value_field,
                "type": "quantitative",
                "scale": {"scheme": "blues"},
                "title": value_field.replace("_", " ").title()
            },
            "tooltip": [
                {"field": f"properties.{feature_key}", "type": "nominal", "title": "Region"},
                {"field": value_field, "type": "quantitative", "title": value_field.replace("_", " ").title()}
            ]
        }
    }
    
    return spec

