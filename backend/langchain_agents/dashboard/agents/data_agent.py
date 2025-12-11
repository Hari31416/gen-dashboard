"""
Data Agent for Dashboard Generation.

This agent takes the chart goals from the Strategy Agent and generates
SQL queries to fetch the required data for each chart.

Input: List[ChartGoal]
Output: List[ChartDataResult] with raw data and SQL queries
"""

import json
import time
import re
from typing import Dict, Any, List

from langchain_core.messages import SystemMessage, HumanMessage

from langchain_agents.llm_utils import get_llm
from langchain_agents.dashboard.state import DashboardGraphState
from langchain_agents.dashboard.models import ChartDataResult, DataAgentOutput
from langchain_agents.tools.database_tools import check_for_sql_safety
from services.database.db_config_models import get_db_config
from services.database.db_connection_service import (
    build_connection_string,
    run_query_and_return_df,
)
from prompts import prompt_map
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


def _get_data_agent_system_prompt() -> str:
    """Get the data agent system prompt."""
    return prompt_map.get("data_agent_system_prompt", DEFAULT_DATA_PROMPT)


DEFAULT_DATA_PROMPT = """You are a SQL Expert for Dashboard Data Generation.

Your task is to generate SQL queries to fetch data for dashboard visualizations.

## Guidelines

1. **SQL Safety**: 
   - ONLY use SELECT statements
   - NEVER use UPDATE, DELETE, DROP, ALTER, or INSERT
   - Always limit results appropriately (use LIMIT for large datasets)

2. **Query Optimization**:
   - Use appropriate JOINs based on table relationships
   - Apply GROUP BY for aggregations
   - Use ORDER BY for sorted results
   - Apply WHERE clauses for filters

3. **Aggregation Mapping**:
   - "sum" -> SUM()
   - "count" -> COUNT()
   - "average" -> AVG()
   - "min" -> MIN()
   - "max" -> MAX()
   - "distinct" -> COUNT(DISTINCT)

4. **Output Format**:
   For EACH chart goal, provide a SQL query in this format:

```sql
-- chart_id: chart_1
SELECT category, SUM(amount) as total_amount
FROM sales
GROUP BY category
ORDER BY total_amount DESC
LIMIT 10;
```

Generate one SQL query per chart goal. Mark each with `-- chart_id: <id>` comment.
"""


async def data_agent_node(state: DashboardGraphState) -> Dict[str, Any]:
    """
    Data Agent node for dashboard generation.

    Uses ReAct-style iterative approach to generate and execute SQL queries
    for each chart goal. This allows the agent to inspect the database
    and correct errors.

    Args:
        state: Current dashboard graph state

    Returns:
        Updated state with chart_data_results
    """
    start_time = time.time()

    username = state.get("username", "")
    connection_name = state.get("connection_name", "")
    chart_goals = state.get("chart_goals", [])
    db_schema = state.get("db_schema", "")
    db_relationships = state.get("db_relationships", "")

    if not chart_goals:
        return {
            "error": "No chart goals provided to Data Agent",
            "failed_stage": "data",
        }

    logger.info(
        f"Data Agent processing {len(chart_goals)} chart goals using ReAct approach"
    )

    MAX_ITERATIONS = 3  # ReAct iterations per chart

    try:
        # Get database connection
        db_config = get_db_config(username, connection_name)
        if not db_config:
            return {
                "error": f"Database configuration not found for {connection_name}",
                "failed_stage": "data",
            }

        connection_string = build_connection_string(**db_config)
        dialect = db_config.get("db_type", "mysql").upper()

        chart_data_results = []

        # Process all chart goals in parallel using asyncio.gather
        import asyncio

        async def process_chart(goal):
            chart_id = goal.get("chart_id", "chart_1")
            return await _generate_chart_data_react(
                goal=goal,
                connection_string=connection_string,
                dialect=dialect,
                db_schema=db_schema,
                db_relationships=db_relationships,
                max_iterations=MAX_ITERATIONS,
            )

        # Run all charts in parallel
        chart_data_results = await asyncio.gather(
            *[process_chart(goal) for goal in chart_goals]
        )

        total_time = (time.time() - start_time) * 1000

        # Check for complete failures
        successful = [r for r in chart_data_results if not r.get("error")]
        if not successful:
            return {
                "error": "All SQL queries failed to execute",
                "failed_stage": "data",
                "chart_data_results": chart_data_results,
            }

        logger.info(
            f"Data Agent executed {len(successful)}/{len(chart_data_results)} queries successfully in {total_time:.2f}ms"
        )

        return {
            "chart_data_results": chart_data_results,
            "data_execution_time_ms": total_time,
            "data_time_ms": total_time,
        }

    except Exception as e:
        logger.exception(f"Data Agent failed: {e}")
        return {
            "error": str(e),
            "failed_stage": "data",
        }


async def _generate_chart_data_react(
    goal: Dict[str, Any],
    connection_string: str,
    dialect: str,
    db_schema: str,
    db_relationships: str,
    max_iterations: int = 3,
) -> Dict[str, Any]:
    """
    Generate SQL and fetch data for a single chart goal using ReAct approach.

    This allows the agent to:
    1. Generate an initial SQL query
    2. Execute and see results/errors
    3. Correct and retry if needed
    """
    chart_id = goal.get("chart_id", "chart_1")
    title = goal.get("title", "Untitled")
    query_start = time.time()

    result = {
        "chart_id": chart_id,
        "sql_query": "",
        "data": [],
        "columns": [],
        "row_count": 0,
        "error": None,
        "execution_time_ms": None,
    }

    system_prompt = _get_data_agent_system_prompt()

    goal_description = f"""Generate a SQL query for this chart:
- Chart ID: {chart_id}
- Title: {title}
- Type: {goal.get('chart_type', 'bar')}
- Description: {goal.get('description', '')}
- X Field: {goal.get('x_field', 'Not specified')}
- Y Field: {goal.get('y_field', 'Not specified')}
- Color Field: {goal.get('color_field', 'None')}
- Aggregation: {goal.get('aggregation', 'none')}
- Tables: {', '.join(goal.get('tables', [])) or 'Determine from schema'}
- Filters: {json.dumps(goal.get('filters', {})) if goal.get('filters') else 'None'}

## Database Dialect
{dialect}

## Database Schema
{db_schema}

## Table Relationships
{db_relationships}

Generate a single SQL query. Wrap it in ```sql ... ```.
Use appropriate JOINs, GROUP BY, ORDER BY as needed.
"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=goal_description),
    ]

    llm = get_llm()

    for iteration in range(max_iterations):
        logger.info(
            f"Chart {chart_id}: ReAct iteration {iteration + 1}/{max_iterations}"
        )

        # 1. Get LLM response (SQL generation)
        response = await llm.ainvoke(messages)
        response_text = response.content
        messages.append(response)

        # 2. Extract SQL
        sql_match = re.search(r"```sql\s*([\s\S]*?)```", response_text, re.IGNORECASE)
        if not sql_match:
            # Try without sql tag
            sql_match = re.search(
                r"```\s*(SELECT[\s\S]*?)```", response_text, re.IGNORECASE
            )

        if not sql_match:
            if iteration < max_iterations - 1:
                feedback = "No SQL query found. Please provide a SQL query wrapped in ```sql ... ```."
                messages.append(HumanMessage(content=feedback))
                continue
            else:
                result["error"] = "Failed to generate SQL query"
                break

        sql_query = sql_match.group(1).strip()
        # Clean up chart_id comments if present
        sql_query = re.sub(r"--\s*chart_id:\s*\w+\s*\n?", "", sql_query).strip()
        result["sql_query"] = sql_query

        # 3. Safety check
        if not check_for_sql_safety(sql_query):
            if iteration < max_iterations - 1:
                feedback = "Unsafe SQL detected (UPDATE/DELETE/DROP/ALTER). Generate a safe SELECT query only."
                messages.append(HumanMessage(content=feedback))
                continue
            else:
                result["error"] = "Unsafe SQL query generated"
                break

        # 4. Execute query
        try:
            df = run_query_and_return_df(connection_string, sql_query)

            # Convert to result format
            data = df.to_dict(orient="records")
            columns = df.columns.tolist()

            # Handle NaN/Inf
            import math

            for row in data:
                for key, value in row.items():
                    if isinstance(value, float) and (
                        math.isnan(value) or math.isinf(value)
                    ):
                        row[key] = None

            result["data"] = data
            result["columns"] = columns
            result["row_count"] = len(data)
            result["execution_time_ms"] = (time.time() - query_start) * 1000

            logger.info(f"Chart {chart_id}: Query returned {len(data)} rows")
            break  # Success!

        except Exception as e:
            error_msg = str(e)
            logger.warning(
                f"Chart {chart_id}: Query failed (iteration {iteration + 1}): {error_msg}"
            )

            if iteration < max_iterations - 1:
                # Provide error feedback for correction
                feedback = f"""SQL Execution Error: {error_msg}

Please fix the SQL query and try again. Common issues:
- Column names may be wrong (check schema above)
- Table names may be wrong
- JOIN conditions may be incorrect
- Syntax errors

Provide the corrected query in ```sql ... ```."""
                messages.append(HumanMessage(content=feedback))
            else:
                result["error"] = error_msg

    return result


def _format_chart_goals(chart_goals: List[Dict[str, Any]]) -> str:
    """Format chart goals for LLM context."""
    lines = []
    for goal in chart_goals:
        chart_id = goal.get("chart_id", "unknown")
        title = goal.get("title", "Untitled")
        description = goal.get("description", "")
        chart_type = goal.get("chart_type", "bar")
        x_field = goal.get("x_field", "")
        y_field = goal.get("y_field", "")
        color_field = goal.get("color_field", "")
        aggregation = goal.get("aggregation", "none")
        filters = goal.get("filters", {})
        tables = goal.get("tables", [])

        lines.append(
            f"""### {chart_id}: {title}
- Type: {chart_type}
- Description: {description}
- X Field: {x_field or 'Not specified'}
- Y Field: {y_field or 'Not specified'}
- Color Field: {color_field or 'None'}
- Aggregation: {aggregation}
- Tables: {', '.join(tables) if tables else 'Determine from schema'}
- Filters: {json.dumps(filters) if filters else 'None'}
"""
        )

    return "\n".join(lines)


def _parse_sql_queries(
    response_text: str, chart_goals: List[Dict[str, Any]]
) -> Dict[str, str]:
    """
    Parse SQL queries from the Data Agent response.

    Args:
        response_text: Raw LLM response
        chart_goals: Original chart goals for ID matching

    Returns:
        Dict mapping chart_id to SQL query
    """
    queries = {}

    # Pattern to match SQL blocks with chart_id comments
    pattern = r"--\s*chart_id:\s*(\w+)[\s\S]*?```sql\s*([\s\S]*?)```"
    matches = re.findall(pattern, response_text, re.IGNORECASE)

    if matches:
        for chart_id, sql in matches:
            queries[chart_id.strip()] = sql.strip()
    else:
        # Try alternate pattern: chart_id comment inside SQL block
        sql_blocks = re.findall(r"```sql\s*([\s\S]*?)```", response_text, re.IGNORECASE)

        for sql_block in sql_blocks:
            # Look for chart_id in comment
            id_match = re.search(r"--\s*chart_id:\s*(\w+)", sql_block)
            if id_match:
                chart_id = id_match.group(1).strip()
                # Remove the comment line from query
                sql = re.sub(r"--\s*chart_id:\s*\w+\s*\n?", "", sql_block).strip()
                queries[chart_id] = sql

        # If still no queries, assign to chart goals in order
        if not queries and sql_blocks:
            for i, (goal, sql) in enumerate(zip(chart_goals, sql_blocks)):
                chart_id = goal.get("chart_id", f"chart_{i+1}")
                queries[chart_id] = sql.strip()

    # Ensure all chart goals have a query (even if empty/failed)
    for goal in chart_goals:
        chart_id = goal.get("chart_id")
        if chart_id and chart_id not in queries:
            # Generate a fallback query based on goal
            queries[chart_id] = _generate_fallback_query(goal)

    return queries


def _generate_fallback_query(goal: Dict[str, Any]) -> str:
    """Generate a simple fallback query for a chart goal."""
    tables = goal.get("tables", [])
    if not tables:
        return ""

    table = tables[0]
    x_field = goal.get("x_field", "*")
    y_field = goal.get("y_field", "")
    aggregation = goal.get("aggregation", "none")

    if aggregation != "none" and y_field:
        agg_map = {
            "sum": "SUM",
            "count": "COUNT",
            "average": "AVG",
            "min": "MIN",
            "max": "MAX",
        }
        agg_func = agg_map.get(aggregation, "SUM")
        return f"SELECT {x_field}, {agg_func}({y_field}) as {y_field} FROM {table} GROUP BY {x_field} LIMIT 100"
    else:
        return f"SELECT * FROM {table} LIMIT 100"


def _execute_query_safe(
    connection_string: str, chart_id: str, sql_query: str
) -> Dict[str, Any]:
    """
    Safely execute a SQL query with safety checks.

    Args:
        connection_string: Database connection string
        chart_id: Chart ID this query is for
        sql_query: SQL query to execute

    Returns:
        ChartDataResult as dict
    """
    result = {
        "chart_id": chart_id,
        "sql_query": sql_query,
        "data": [],
        "columns": [],
        "row_count": 0,
        "error": None,
        "execution_time_ms": None,
    }

    if not sql_query:
        result["error"] = "No SQL query generated"
        return result

    # Safety check
    if not check_for_sql_safety(sql_query):
        result["error"] = (
            "Unsafe SQL query detected (contains UPDATE/DELETE/DROP/ALTER)"
        )
        logger.warning(f"Blocked unsafe query for {chart_id}: {sql_query[:100]}...")
        return result

    try:
        df = run_query_and_return_df(connection_string, sql_query)

        # Convert DataFrame to list of dicts
        data = df.to_dict(orient="records")
        columns = df.columns.tolist()

        # Handle NaN/Inf values
        import math

        for row in data:
            for key, value in row.items():
                if isinstance(value, float) and (
                    math.isnan(value) or math.isinf(value)
                ):
                    row[key] = None

        result["data"] = data
        result["columns"] = columns
        result["row_count"] = len(data)

        logger.debug(f"Query for {chart_id} returned {len(data)} rows")

    except Exception as e:
        result["error"] = str(e)
        logger.error(f"Query execution failed for {chart_id}: {e}")

    return result
