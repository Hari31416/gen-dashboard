"""
Refinement Action Handlers.

Each handler is responsible for a specific type of dashboard modification.
Handlers receive context and return the updated dashboard state.
"""

import copy
from typing import Dict, Any, List, Optional
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


async def handle_rerun_sql(
    action: Any,
    updated_dashboard: Dict[str, Any],
    updated_sql_queries: List[Dict[str, str]],
    connection_string: str,
) -> Dict[str, Any]:
    """
    Re-execute existing SQL queries without modification.

    Args:
        action: RefinementAction with target_chart_id
        updated_dashboard: Current dashboard spec to modify
        updated_sql_queries: Current SQL queries
        connection_string: Database connection string

    Returns:
        Dict with updated individual_specs
    """
    from langchain_agents.dashboard.agents.data_agent import _execute_query_safe

    target_id = action.target_chart_id
    queries_to_run = (
        updated_sql_queries
        if not target_id
        else [q for q in updated_sql_queries if q.get("chart_id") == target_id]
    )

    for q in queries_to_run:
        chart_id = q.get("chart_id")
        sql_query = q.get("sql_query")
        result = _execute_query_safe(connection_string, chart_id, sql_query)

        if not result.get("error"):
            for spec in updated_dashboard.get("individual_specs", []):
                if spec.get("chart_id") == chart_id:
                    spec["data"] = {"values": result.get("data", [])}
                    logger.info(f"Refreshed data for {chart_id}")

    return {"individual_specs": updated_dashboard.get("individual_specs", [])}


async def handle_modify_sql(
    action: Any,
    updated_dashboard: Dict[str, Any],
    updated_sql_queries: List[Dict[str, str]],
    updated_chart_goals: List[Dict[str, Any]],
    original_prompt: str,
    user_feedback: str,
    username: str,
    connection_name: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Modify SQL query using the Data Agent with previous query as context.

    Args:
        action: RefinementAction with target_chart_id
        updated_dashboard: Current dashboard spec
        updated_sql_queries: Current SQL queries (will be updated)
        updated_chart_goals: Chart goals for context
        original_prompt: Original dashboard generation prompt
        user_feedback: User's feedback text
        username: Username
        connection_name: Database connection name
        session_id: Session ID

    Returns:
        Dict with updated sql_queries and individual_specs
    """
    from langchain_agents.dashboard.agents.data_agent import data_agent_node
    from langchain_agents.dashboard.state import create_initial_dashboard_state

    target_id = action.target_chart_id

    # Find the chart goal for context
    target_goal = None
    for goal in updated_chart_goals:
        if goal.get("chart_id") == target_id or target_id is None:
            target_goal = goal
            break

    # Find the current SQL query for context
    current_sql = None
    for q in updated_sql_queries:
        if q.get("chart_id") == target_id or target_id is None:
            current_sql = q.get("sql_query")
            break

    if not target_goal:
        logger.warning(f"No chart goal found for {target_id}")
        return {}

    # Build context-rich prompt including previous SQL
    context_prompt = f"""{original_prompt}

## Current Chart Information
Chart: {target_goal.get('title', target_id)}
Description: {target_goal.get('description', 'N/A')}

## Previous SQL Query (needs modification)
```sql
{current_sql if current_sql else 'No previous query available'}
```

## User Feedback
{user_feedback}

Please generate a corrected SQL query based on the user's feedback. The previous query is provided above as reference."""

    mini_state = create_initial_dashboard_state(
        user_prompt=context_prompt,
        username=username,
        connection_name=connection_name,
        session_id=session_id,
    )
    mini_state["chart_goals"] = [target_goal]

    # Run data agent for this chart
    data_result = await data_agent_node(mini_state)

    if not data_result.get("error"):
        new_results = data_result.get("chart_data_results", [])
        for result in new_results:
            if not result.get("error"):
                chart_id = result.get("chart_id")
                # Update SQL query
                for q in updated_sql_queries:
                    if q.get("chart_id") == chart_id:
                        q["sql_query"] = result.get("sql_query", q["sql_query"])
                # Update data in spec
                for spec in updated_dashboard.get("individual_specs", []):
                    if spec.get("chart_id") == chart_id:
                        spec["data"] = {"values": result.get("data", [])}
                logger.info(f"Modified SQL and data for {chart_id}")
                logger.info(f"New SQL query: {result.get('sql_query')}")

    return {
        "sql_queries": updated_sql_queries,
        "individual_specs": updated_dashboard.get("individual_specs", []),
    }


async def handle_change_chart_type(
    action: Any,
    updated_dashboard: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Change the chart type (bar, line, pie, etc.).

    Also transforms encoding as needed:
    - bar/line/area use x/y encoding
    - arc (pie) uses theta/color encoding

    Args:
        action: RefinementAction with target_chart_id and parameters.new_type
        updated_dashboard: Current dashboard spec

    Returns:
        Dict with updated individual_specs
    """
    target_id = action.target_chart_id
    new_type = action.parameters.get("new_type", "bar")

    for spec in updated_dashboard.get("individual_specs", []):
        if spec.get("chart_id") == target_id:
            # Get current mark info for logging
            current_mark = spec.get("mark", {})
            current_type = (
                current_mark.get("type")
                if isinstance(current_mark, dict)
                else current_mark
            )

            # Update mark type
            if isinstance(spec.get("mark"), dict):
                spec["mark"]["type"] = new_type
            else:
                spec["mark"] = {"type": new_type}

            # Transform encoding if changing to/from arc (pie chart)
            encoding = spec.get("encoding", {})

            if new_type == "arc" and current_type != "arc":
                # Changing TO pie chart: convert x/y to theta/color
                x_field = encoding.get("x", {}).get("field")
                y_field = encoding.get("y", {}).get("field")

                # theta = numeric field (y), color = categorical field (x)
                # They MUST be different for pie chart to show multiple colors
                if y_field and x_field and x_field != y_field:
                    new_encoding = {
                        "theta": {"field": y_field, "type": "quantitative"},
                        "color": {"field": x_field, "type": "nominal"},
                    }
                    # Add tooltip if available
                    if "tooltip" in encoding:
                        new_encoding["tooltip"] = encoding["tooltip"]

                    spec["encoding"] = new_encoding
                    logger.info(
                        f"Transformed encoding for {target_id}: theta={y_field}, color={x_field}"
                    )
                elif y_field:
                    # Fallback: only have y_field, use it for theta but need a color field
                    logger.warning(
                        f"Pie chart {target_id} may have single color - x_field missing or same as y_field"
                    )
                    new_encoding = {
                        "theta": {"field": y_field, "type": "quantitative"},
                        "color": {"field": x_field or y_field, "type": "nominal"},
                    }
                    if "tooltip" in encoding:
                        new_encoding["tooltip"] = encoding["tooltip"]
                    spec["encoding"] = new_encoding

            elif current_type == "arc" and new_type != "arc":
                # Changing FROM pie chart: convert theta/color to x/y
                theta_field = encoding.get("theta", {}).get("field")
                color_field = encoding.get("color", {}).get("field")

                if theta_field or color_field:
                    new_encoding = {
                        "x": {"field": color_field or theta_field, "type": "nominal"},
                        "y": {
                            "field": theta_field or color_field,
                            "type": "quantitative",
                        },
                    }
                    # Add tooltip if available
                    if "tooltip" in encoding:
                        new_encoding["tooltip"] = encoding["tooltip"]

                    spec["encoding"] = new_encoding
                    logger.info(
                        f"Transformed encoding for {target_id}: theta/color -> x/y"
                    )

            logger.info(
                f"Changed {target_id} chart type from {current_type} to {new_type}"
            )
            break

    return {"individual_specs": updated_dashboard.get("individual_specs", [])}


async def handle_change_encoding(
    action: Any,
    updated_dashboard: Dict[str, Any],
    updated_chart_goals: List[Dict[str, Any]],
    user_feedback: str,
) -> Dict[str, Any]:
    """
    Change data encoding (x/y fields, colors, grouping).

    Includes previous encoding in logs for context.

    Args:
        action: RefinementAction with target_chart_id and parameters
        updated_dashboard: Current dashboard spec
        updated_chart_goals: Chart goals for context
        user_feedback: User's feedback

    Returns:
        Dict with updated individual_specs
    """
    target_id = action.target_chart_id

    for spec in updated_dashboard.get("individual_specs", []):
        if spec.get("chart_id") == target_id:
            encoding = spec.get("encoding", {})

            # Log previous encoding for context
            prev_x = encoding.get("x", {}).get("field", "N/A")
            prev_y = encoding.get("y", {}).get("field", "N/A")
            prev_color = encoding.get("color", {}).get("field", "N/A")

            logger.info(
                f"Previous encoding for {target_id}: x={prev_x}, y={prev_y}, color={prev_color}"
            )

            # Apply changes from parameters
            if action.parameters.get("x_field"):
                if "x" not in encoding:
                    encoding["x"] = {"type": "nominal"}
                encoding["x"]["field"] = action.parameters["x_field"]

            if action.parameters.get("y_field"):
                if "y" not in encoding:
                    encoding["y"] = {"type": "quantitative"}
                encoding["y"]["field"] = action.parameters["y_field"]

            if action.parameters.get("color_field"):
                encoding["color"] = {
                    "field": action.parameters["color_field"],
                    "type": "nominal",
                }

            if action.parameters.get("aggregation"):
                if "y" in encoding:
                    encoding["y"]["aggregate"] = action.parameters["aggregation"]

            spec["encoding"] = encoding

            new_x = encoding.get("x", {}).get("field", "N/A")
            new_y = encoding.get("y", {}).get("field", "N/A")
            new_color = encoding.get("color", {}).get("field", "N/A")
            logger.info(
                f"Updated encoding for {target_id}: x={new_x}, y={new_y}, color={new_color}"
            )
            break

    return {"individual_specs": updated_dashboard.get("individual_specs", [])}


async def handle_change_title(
    action: Any,
    updated_dashboard: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Update chart or dashboard title.

    Args:
        action: RefinementAction with target_chart_id and parameters.new_title
        updated_dashboard: Current dashboard spec

    Returns:
        Dict with updated title and/or individual_specs
    """
    new_title = action.parameters.get("new_title", "")

    if not new_title:
        return {}

    if action.target_chart_id:
        # Update specific chart title
        for spec in updated_dashboard.get("individual_specs", []):
            if spec.get("chart_id") == action.target_chart_id:
                old_title = spec.get("title", "Untitled")
                spec["title"] = new_title
                logger.info(
                    f"Updated title for {action.target_chart_id}: '{old_title}' -> '{new_title}'"
                )
                break
        return {"individual_specs": updated_dashboard.get("individual_specs", [])}
    else:
        # Update dashboard title
        old_title = updated_dashboard.get("title", "Dashboard")
        updated_dashboard["title"] = new_title
        logger.info(f"Updated dashboard title: '{old_title}' -> '{new_title}'")
        return {"title": new_title}


async def handle_change_layout(
    action: Any,
    updated_dashboard: Dict[str, Any],
    updated_chart_goals: List[Dict[str, Any]],
    original_prompt: str,
    user_feedback: str,
    username: str,
    connection_name: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Rearrange or resize charts using the Layout Agent.

    Args:
        action: RefinementAction
        updated_dashboard: Current dashboard spec
        updated_chart_goals: Chart goals
        original_prompt: Original prompt
        user_feedback: User's layout feedback
        username: Username
        connection_name: Connection name
        session_id: Session ID

    Returns:
        Dict with updated layout_config
    """
    from langchain_agents.dashboard.agents.layout_agent import layout_agent_node
    from langchain_agents.dashboard.state import create_initial_dashboard_state

    # Include current layout in context
    current_layout = updated_dashboard.get("layout_config", {})

    context_prompt = f"""{original_prompt}

## Current Layout Configuration
{current_layout}

## Layout Change Requested
{user_feedback}"""

    mini_state = create_initial_dashboard_state(
        user_prompt=context_prompt,
        username=username,
        connection_name=connection_name,
        session_id=session_id,
    )
    mini_state["viz_specs"] = updated_dashboard.get("individual_specs", [])
    mini_state["chart_goals"] = updated_chart_goals

    layout_result = await layout_agent_node(mini_state)

    if layout_result.get("dashboard_spec"):
        new_spec = layout_result["dashboard_spec"]
        new_layout = new_spec.get("layout_config", current_layout)
        logger.info("Updated dashboard layout")
        return {"layout_config": new_layout}

    return {}


async def handle_add_chart(
    action: Any,
    updated_dashboard: Dict[str, Any],
    updated_sql_queries: List[Dict[str, str]],
    updated_chart_goals: List[Dict[str, Any]],
    user_feedback: str,
    username: str,
    connection_name: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Add a new chart to the dashboard using full pipeline.

    Args:
        action: RefinementAction with parameters.description
        updated_dashboard: Current dashboard spec
        updated_sql_queries: Current SQL queries
        updated_chart_goals: Current chart goals
        user_feedback: User's feedback
        username: Username
        connection_name: Connection name
        session_id: Session ID

    Returns:
        Dict with updated individual_specs, layout_config, sql_queries, chart_count, chart_goals
    """
    from langchain_agents.dashboard.graph import run_dashboard_generation

    description = action.parameters.get("description", user_feedback)

    # Run full pipeline for the new chart
    new_chart_result = await run_dashboard_generation(
        user_prompt=f"Create a single chart: {description}",
        username=username,
        connection_name=connection_name,
        session_id=session_id,
        max_charts=1,
    )

    if new_chart_result.get("error"):
        logger.error(f"Failed to add chart: {new_chart_result.get('error')}")
        return {}

    new_spec = new_chart_result.get("dashboard_spec", {})
    new_individual = new_spec.get("individual_specs", [])
    new_queries = new_spec.get("sql_queries", [])
    new_goals = new_chart_result.get("chart_goals", [])

    if not new_individual:
        return {}

    # Generate new chart ID based on max existing ID
    existing_ids = [
        s.get("chart_id", "") for s in updated_dashboard.get("individual_specs", [])
    ]
    max_num = 0
    for eid in existing_ids:
        if eid.startswith("chart_"):
            try:
                num = int(eid.replace("chart_", ""))
                max_num = max(max_num, num)
            except ValueError:
                pass
    new_id = f"chart_{max_num + 1}"
    new_individual[0]["chart_id"] = new_id

    # Add to dashboard
    updated_dashboard.setdefault("individual_specs", []).append(new_individual[0])

    # Add to layout
    if updated_dashboard.get("layout_config"):
        num_charts = len(updated_dashboard["individual_specs"])
        updated_dashboard["layout_config"]["layout"].append(
            {
                "i": new_id,
                "x": ((num_charts - 1) % 2) * 6,
                "y": ((num_charts - 1) // 2) * 3,
                "w": 6,
                "h": 3,
                "minW": 3,
                "minH": 2,
            }
        )

    # Add SQL query
    if new_queries:
        new_queries[0]["chart_id"] = new_id
        updated_sql_queries.append(new_queries[0])

    # Add chart goal
    if new_goals:
        new_goals[0]["chart_id"] = new_id
        updated_chart_goals.append(new_goals[0])

    chart_count = len(updated_dashboard.get("individual_specs", []))
    updated_dashboard["chart_count"] = chart_count

    logger.info(f"Added new chart: {new_id}")

    return {
        "individual_specs": updated_dashboard.get("individual_specs", []),
        "layout_config": updated_dashboard.get("layout_config"),
        "sql_queries": updated_sql_queries,
        "chart_count": chart_count,
        "chart_goals": updated_chart_goals,
    }


async def handle_remove_chart(
    action: Any,
    updated_dashboard: Dict[str, Any],
    updated_sql_queries: List[Dict[str, str]],
    updated_chart_goals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Remove a chart from the dashboard.

    Args:
        action: RefinementAction with target_chart_id
        updated_dashboard: Current dashboard spec
        updated_sql_queries: Current SQL queries
        updated_chart_goals: Current chart goals

    Returns:
        Dict with updated individual_specs, layout_config, sql_queries, chart_count, chart_goals
    """
    chart_id = action.target_chart_id

    if not chart_id:
        logger.warning("No chart_id specified for remove_chart action")
        return {}

    # Remove from individual_specs
    updated_dashboard["individual_specs"] = [
        s
        for s in updated_dashboard.get("individual_specs", [])
        if s.get("chart_id") != chart_id
    ]

    # Remove from layout
    if updated_dashboard.get("layout_config"):
        updated_dashboard["layout_config"]["layout"] = [
            l
            for l in updated_dashboard["layout_config"].get("layout", [])
            if l.get("i") != chart_id
        ]

    # Remove from sql_queries
    updated_sql_queries[:] = [
        q for q in updated_sql_queries if q.get("chart_id") != chart_id
    ]

    # Remove from chart_goals
    updated_chart_goals[:] = [
        g for g in updated_chart_goals if g.get("chart_id") != chart_id
    ]

    # Update chart count
    chart_count = len(updated_dashboard.get("individual_specs", []))
    updated_dashboard["chart_count"] = chart_count

    logger.info(f"Removed chart {chart_id}")

    return {
        "individual_specs": updated_dashboard.get("individual_specs", []),
        "layout_config": updated_dashboard.get("layout_config"),
        "sql_queries": updated_sql_queries,
        "chart_count": chart_count,
        "chart_goals": updated_chart_goals,
    }


async def handle_change_theme(
    action: Any,
    updated_dashboard: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Change the dashboard theme/styling.

    Uses an LLM to interpret the user's theme description and generate
    appropriate Vega-Lite color/styling configurations.

    Args:
        action: RefinementAction with parameters.theme_description
        updated_dashboard: Current dashboard spec

    Returns:
        Dict with updated individual_specs containing new theme config
    """
    import json
    from langchain_core.messages import SystemMessage, HumanMessage
    from langchain_agents.llm_utils import get_llm

    theme_desc = action.parameters.get("theme_description", "")
    target_chart_id = action.target_chart_id

    if not theme_desc:
        logger.warning("No theme description provided")
        return {}

    logger.info(f"Theme change requested: {theme_desc}")

    # Build prompt for LLM to generate theme configuration
    theme_prompt = """You are a Vega-Lite theming expert.

Given a user's theme description, generate a JSON object with color and styling configurations.

Output a JSON object with these optional fields:
- "mark_color": A single hex color for chart marks (bars, lines, points, etc.)
- "color_scheme": A Vega color scheme name (e.g., "blues", "greens", "oranges", "purples", "reds", "greys", "viridis", "plasma", "inferno", "magma", "category10", "category20", "tableau10", "tableau20", "dark2", "set1", "set2", "set3", "pastel1", "pastel2")
- "background": Background color for charts (hex)
- "title_color": Color for chart titles (hex)
- "axis_color": Color for axis lines and labels (hex)
- "grid_color": Color for grid lines (hex)

Only include fields that are relevant to the user's request.

Examples:
- "make it darker" -> {"background": "#1a1a2e", "title_color": "#ffffff", "axis_color": "#888888", "grid_color": "#333344"}
- "use blue colors" -> {"mark_color": "#4a90d9", "color_scheme": "blues"}
- "green theme" -> {"mark_color": "#2ecc71", "color_scheme": "greens"}
- "corporate look" -> {"mark_color": "#2c3e50", "color_scheme": "tableau10", "background": "#f8f9fa"}
- "warm colors" -> {"mark_color": "#e74c3c", "color_scheme": "oranges"}
- "pastel colors" -> {"color_scheme": "pastel1"}

User request: """

    try:
        llm = get_llm(temperature=0.2)
        messages = [
            SystemMessage(content=theme_prompt),
            HumanMessage(content=theme_desc),
        ]
        response = await llm.ainvoke(messages)
        response_text = response.content

        # Extract JSON from response
        import re

        json_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
        if not json_match:
            logger.warning("Could not parse theme JSON from LLM response")
            return {}

        theme_config = json.loads(json_match.group(0))
        logger.info(f"Generated theme config: {theme_config}")

    except Exception as e:
        logger.warning(f"LLM theme generation failed, using fallback: {e}")
        # Fallback: simple color mapping based on keywords
        theme_config = _get_fallback_theme(theme_desc)

    if not theme_config:
        return {}

    # Apply theme to charts
    individual_specs = updated_dashboard.get("individual_specs", [])

    for spec in individual_specs:
        # Skip if targeting a specific chart and this isn't it
        if target_chart_id and spec.get("chart_id") != target_chart_id:
            continue

        # Initialize config if not present
        if "config" not in spec:
            spec["config"] = {}

        # Apply mark color
        if theme_config.get("mark_color"):
            mark = spec.get("mark", {})
            if isinstance(mark, dict):
                mark["color"] = theme_config["mark_color"]
            else:
                spec["mark"] = {"type": mark, "color": theme_config["mark_color"]}

        # Apply color scheme to encoding
        if theme_config.get("color_scheme"):
            encoding = spec.get("encoding", {})
            if "color" in encoding:
                encoding["color"]["scale"] = {"scheme": theme_config["color_scheme"]}

        # Apply background
        if theme_config.get("background"):
            spec["config"]["background"] = theme_config["background"]

        # Apply title styling
        if theme_config.get("title_color"):
            spec["config"]["title"] = spec["config"].get("title", {})
            spec["config"]["title"]["color"] = theme_config["title_color"]

        # Apply axis styling
        if theme_config.get("axis_color"):
            spec["config"]["axis"] = spec["config"].get("axis", {})
            spec["config"]["axis"]["labelColor"] = theme_config["axis_color"]
            spec["config"]["axis"]["titleColor"] = theme_config["axis_color"]
            spec["config"]["axis"]["tickColor"] = theme_config["axis_color"]
            spec["config"]["axis"]["domainColor"] = theme_config["axis_color"]

        # Apply grid styling
        if theme_config.get("grid_color"):
            spec["config"]["axis"] = spec["config"].get("axis", {})
            spec["config"]["axis"]["gridColor"] = theme_config["grid_color"]

        chart_id = spec.get("chart_id", "unknown")
        logger.info(f"Applied theme to {chart_id}")

    return {"individual_specs": individual_specs}


def _get_fallback_theme(theme_desc: str) -> Dict[str, Any]:
    """Fallback theme mapping when LLM fails."""
    theme_desc_lower = theme_desc.lower()

    # Color keywords
    if "blue" in theme_desc_lower:
        return {"mark_color": "#3498db", "color_scheme": "blues"}
    elif "green" in theme_desc_lower:
        return {"mark_color": "#2ecc71", "color_scheme": "greens"}
    elif "red" in theme_desc_lower:
        return {"mark_color": "#e74c3c", "color_scheme": "reds"}
    elif "orange" in theme_desc_lower:
        return {"mark_color": "#e67e22", "color_scheme": "oranges"}
    elif "purple" in theme_desc_lower:
        return {"mark_color": "#9b59b6", "color_scheme": "purples"}
    elif "pink" in theme_desc_lower:
        return {"mark_color": "#e91e63", "color_scheme": "set2"}
    elif "grey" in theme_desc_lower or "gray" in theme_desc_lower:
        return {"mark_color": "#7f8c8d", "color_scheme": "greys"}

    # Style keywords
    elif "dark" in theme_desc_lower:
        return {
            "background": "#1a1a2e",
            "title_color": "#ffffff",
            "axis_color": "#888888",
            "grid_color": "#333344",
            "mark_color": "#6c5ce7",
        }
    elif "light" in theme_desc_lower:
        return {
            "background": "#ffffff",
            "title_color": "#2d3436",
            "axis_color": "#636e72",
            "grid_color": "#dfe6e9",
        }
    elif "warm" in theme_desc_lower:
        return {"mark_color": "#e74c3c", "color_scheme": "oranges"}
    elif "cool" in theme_desc_lower:
        return {"mark_color": "#3498db", "color_scheme": "blues"}
    elif "pastel" in theme_desc_lower:
        return {"color_scheme": "pastel1"}
    elif "corporate" in theme_desc_lower or "professional" in theme_desc_lower:
        return {"mark_color": "#2c3e50", "color_scheme": "tableau10"}

    return {}


async def handle_full_redesign(
    updated_dashboard: Dict[str, Any],
    updated_sql_queries: List[Dict[str, str]],
    chart_goals: List[Dict[str, Any]],
    original_prompt: str,
    user_feedback: str,
    username: str,
    connection_name: str,
    session_id: str,
) -> Dict[str, Any]:
    """
    Complete dashboard redesign using full pipeline.

    Args:
        updated_dashboard: Current dashboard (will be replaced)
        updated_sql_queries: Current queries (will be replaced)
        chart_goals: Current goals for reference
        original_prompt: Original prompt
        user_feedback: User's redesign feedback
        username: Username
        connection_name: Connection name
        session_id: Session ID

    Returns:
        Dict with complete new dashboard_spec and sql_queries
    """
    from langchain_agents.dashboard.graph import run_dashboard_generation

    full_result = await run_dashboard_generation(
        user_prompt=f"{original_prompt}\n\nRedesign: {user_feedback}",
        username=username,
        connection_name=connection_name,
        session_id=session_id,
        max_charts=len(chart_goals) if chart_goals else 5,
    )

    if full_result.get("error"):
        logger.error(f"Full redesign failed: {full_result.get('error')}")
        return {"error": full_result.get("error")}

    new_dashboard = full_result.get("dashboard_spec", {})
    new_sql_queries = new_dashboard.get("sql_queries", [])

    logger.info("Full dashboard redesign completed")

    return {
        "dashboard_spec": new_dashboard,
        "sql_queries": new_sql_queries,
    }
