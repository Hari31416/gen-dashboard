"""
Strategy Agent for Dashboard Generation.

This agent analyzes the user request and database schema to create
a plan of 3-5 chart objectives for the dashboard.

Input: User prompt, database schema
Output: List[ChartGoal] with chart objectives
"""

import json
import time
from typing import Dict, Any, List

from langchain_core.messages import SystemMessage, HumanMessage

from langchain_agents.llm_utils import get_llm
from langchain_agents.dashboard.state import DashboardGraphState
from langchain_agents.dashboard.models import (
    ChartGoal,
    ChartType,
    AggregationType,
    StrategyAgentOutput,
)
from langchain_agents.agents.react_tts_agent import (
    convert_tables_info,
    convert_relationships,
)
from services.database.db_config_models import (
    get_db_config,
    get_db_info,
    get_db_relationships,
)
from prompts import prompt_map
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


def _get_strategy_system_prompt() -> str:
    """Get the strategy agent system prompt."""
    return prompt_map.get("strategy_agent_system_prompt", DEFAULT_STRATEGY_PROMPT)


DEFAULT_STRATEGY_PROMPT = """You are a Dashboard Strategy Expert.

Your task is to analyze a user's natural language request and database schema to create a strategic plan for a data dashboard.

## Your Goal
Generate 3-5 chart objectives that together form a comprehensive dashboard answering the user's question.

## Guidelines

1. **Diverse Chart Types**: Use a variety of visualizations:
   - `bar`: For comparisons across categories
   - `line`: For trends over time
   - `area`: For cumulative trends
   - `arc` (pie): For composition/percentages (max 7 slices)
   - `point` (scatter): For correlation between two variables
   - `text` (KPI): For single important metrics
   - `rect` (heatmap): For two-dimensional comparisons

2. **Chart Priority**: 
   - Priority 1: Most important overview/summary charts
   - Priority 2-3: Supporting detail charts
   - Higher numbers = less important

3. **Data Requirements**: 
   - Specify which tables are needed
   - Identify the x_field, y_field, and optional color_field
   - Specify appropriate aggregation (sum, count, average, min, max)

4. **Filters**: If the user mentions specific conditions (e.g., "last year", "top 10"), include them in filters.

## Output Format
You MUST respond with a valid JSON object in this EXACT format:
```json
{
  "chart_goals": [
    {
      "chart_id": "chart_1",
      "chart_type": "bar",
      "title": "Sales by Category",
      "description": "Bar chart showing total sales amount grouped by product category",
      "x_field": "category_name",
      "y_field": "total_sales",
      "color_field": null,
      "aggregation": "sum",
      "filters": null,
      "tables": ["sales", "categories"],
      "priority": 1
    }
  ],
  "reasoning": "Explanation of why these charts were chosen..."
}
```

Important: 
- chart_type must be one of: bar, line, area, arc, point, text, rect
- aggregation must be one of: sum, count, average, min, max, distinct, none
- Always include 3-5 charts for a comprehensive dashboard
"""


async def strategy_agent_node(state: DashboardGraphState) -> Dict[str, Any]:
    """
    Strategy Agent node for dashboard generation.
    
    Analyzes user request and database schema to create chart objectives.
    
    Args:
        state: Current dashboard graph state
        
    Returns:
        Updated state with chart_goals and strategy_reasoning
    """
    start_time = time.time()
    
    user_prompt = state.get("user_prompt", "")
    username = state.get("username", "")
    connection_name = state.get("connection_name", "")
    max_charts = state.get("max_charts", 5)
    
    logger.info(f"Strategy Agent processing request for connection: {connection_name}")
    
    try:
        # Get database context
        db_config = get_db_config(username, connection_name)
        if not db_config:
            return {
                "error": f"Database configuration not found for {connection_name}",
                "failed_stage": "strategy",
            }
        
        db_info = get_db_info(username, connection_name)
        if not db_info:
            return {
                "error": f"Database schema not found for {connection_name}",
                "failed_stage": "strategy",
            }
        
        relationships = get_db_relationships(username, connection_name)
        
        # Format schema for LLM
        db_description = db_config.get("db_description", "No description provided.")
        formatted_tables = convert_tables_info(db_info)
        formatted_relationships = convert_relationships(relationships)
        
        # Build context message
        context = f"""## User Request
{user_prompt}

## Database Description
{db_description}

## Database Schema
{formatted_tables}

## Table Relationships
{formatted_relationships}

## Configuration
- Maximum charts: {max_charts}

Please analyze this request and create {max_charts} chart objectives for the dashboard.
"""
        
        # Get system prompt
        system_prompt = _get_strategy_system_prompt()
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=context),
        ]
        
        # Call LLM
        llm = get_llm(temperature=0.3)  # Lower temperature for more consistent output
        response = await llm.ainvoke(messages)
        response_text = response.content
        
        logger.debug(f"Strategy Agent response: {response_text[:500]}...")
        
        # Parse JSON response
        chart_goals, reasoning = _parse_strategy_response(response_text)
        
        if not chart_goals:
            return {
                "error": "Failed to parse chart goals from Strategy Agent response",
                "failed_stage": "strategy",
            }
        
        # Limit to max_charts
        if len(chart_goals) > max_charts:
            chart_goals = chart_goals[:max_charts]
        
        execution_time = (time.time() - start_time) * 1000
        
        logger.info(f"Strategy Agent generated {len(chart_goals)} chart goals in {execution_time:.2f}ms")
        
        return {
            "chart_goals": chart_goals,
            "strategy_reasoning": reasoning,
            "strategy_time_ms": execution_time,
            "db_schema": formatted_tables,
            "db_relationships": formatted_relationships,
            "db_description": db_description,
        }
        
    except Exception as e:
        logger.exception(f"Strategy Agent failed: {e}")
        return {
            "error": str(e),
            "failed_stage": "strategy",
        }


def _parse_strategy_response(response_text: str) -> tuple[List[Dict[str, Any]], str]:
    """
    Parse the Strategy Agent response to extract chart goals.
    
    Args:
        response_text: Raw LLM response
        
    Returns:
        Tuple of (chart_goals list, reasoning string)
    """
    import re
    
    # Try to extract JSON from code block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
    
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r"\{[\s\S]*\"chart_goals\"[\s\S]*\}", response_text)
        if json_match:
            json_str = json_match.group(0)
        else:
            logger.error("Could not find JSON in response")
            return [], ""
    
    try:
        parsed = json.loads(json_str)
        chart_goals = parsed.get("chart_goals", [])
        reasoning = parsed.get("reasoning", "")
        
        # Validate chart goals
        validated_goals = []
        for goal in chart_goals:
            try:
                # Ensure required fields
                if not goal.get("chart_id"):
                    goal["chart_id"] = f"chart_{len(validated_goals) + 1}"
                
                # Validate chart type
                chart_type = goal.get("chart_type", "bar")
                valid_types = [t.value for t in ChartType]
                if chart_type not in valid_types:
                    goal["chart_type"] = "bar"
                
                # Validate aggregation
                agg = goal.get("aggregation", "none")
                valid_aggs = [a.value for a in AggregationType]
                if agg not in valid_aggs:
                    goal["aggregation"] = "none"
                
                validated_goals.append(goal)
            except Exception as e:
                logger.warning(f"Skipping invalid chart goal: {e}")
                continue
        
        return validated_goals, reasoning
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return [], ""
