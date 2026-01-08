"""
Refinement Intent Classifier Agent.

This agent analyzes user feedback on an existing dashboard and classifies
their intent into specific refinement actions.

Input: User feedback, current dashboard state
Output: RefinementIntent with classified actions
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

from langchain_agents.dashboard.models import (
    RefinementAction,
    RefinementActionType,
    RefinementIntent,
)
from langchain_agents.llm_utils import get_llm
from langchain_core.messages import HumanMessage, SystemMessage
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


REFINEMENT_CLASSIFIER_PROMPT = """You are a Dashboard Refinement Intent Classifier.

Your task is to analyze user feedback about an existing dashboard and determine what specific changes they want to make.

## Available Action Types

1. **rerun_sql** - Re-execute existing SQL queries to refresh data (no query modification)
   - Use when: "refresh the data", "data looks stale", "update the numbers"
   
2. **modify_sql** - Fix or change the SQL query (LLM will regenerate)
   - Use when: "data is wrong", "fix the chart data", "show different data", "add a filter for X"
   
3. **change_chart_type** - Switch visualization type (bar, line, pie, etc.)
   - Use when: "change to line chart", "make it a bar chart", "show as pie"
   - Parameters: new_type (bar, line, arc, point, text, rect, area)
   
4. **change_encoding** - Change data fields, visual encoding, or number formatting
   - Use when: "group by region instead", "show by month", "color by category", "format numbers as currency", "show percentages", "use thousands separator"
   - Parameters: x_field, y_field, color_field, aggregation, number_format, x_format, tooltip_format
   
5. **change_title** - Update chart or dashboard title
   - Use when: "change title to X", "rename the chart"
   - Parameters: new_title
   
6. **change_layout** - Rearrange or resize charts
   - Use when: "move chart to top", "make it bigger", "put side by side"
   
7. **add_chart** - Add a new chart to the dashboard
   - Use when: "add a chart for X", "also show Y", "include a pie chart"
   - Parameters: description (what the new chart should show)
   
8. **remove_chart** - Remove an existing chart
   - Use when: "remove chart 2", "delete the pie chart", "I don't need the KPI"
   
9. **change_theme** - Change color scheme or styling
   - Use when: "make it darker", "use blue colors", "change the theme", "use green color"
   - Parameters: theme_description
   
10. **full_redesign** - Complete dashboard overhaul
    - Use when: "start over", "completely different", "redesign everything"

## Rules

1. **Be specific**: Identify the exact chart_id if mentioned (e.g., "chart_1", "first chart", "the bar chart")
2. **Multi-action**: If user wants multiple changes, output multiple actions
3. **Clarification**: If the intent is unclear or ambiguous, set requires_clarification=true
4. **Confidence**: Set confidence lower (0.5-0.8) if you're inferring intent, higher (0.9-1.0) if explicit

## Output Format

You MUST respond with a valid JSON object:
```json
{
  "actions": [
    {
      "action_type": "change_chart_type",
      "target_chart_id": "chart_1",
      "parameters": {"new_type": "line"},
      "confidence": 0.95
    }
  ],
  "requires_clarification": false,
  "clarification_question": null,
  "reasoning": "User explicitly asked to change chart 1 to a line chart"
}
```

If clarification is needed:
```json
{
  "actions": [],
  "requires_clarification": true,
  "clarification_question": "Which chart would you like me to modify? You have: Chart 1 (Sales by Region), Chart 2 (Monthly Trend), Chart 3 (Top Products)",
  "reasoning": "User said 'fix the chart' but didn't specify which one"
}
```
"""


async def classify_refinement_intent(
    user_feedback: str,
    current_dashboard: Dict[str, Any],
    chart_goals: List[Dict[str, Any]],
    target_chart_hint: Optional[str] = None,
) -> RefinementIntent:
    """
    Classify user feedback into refinement actions.

    Args:
        user_feedback: Natural language feedback from user
        current_dashboard: Current dashboard spec
        chart_goals: Original chart goals from strategy agent
        target_chart_hint: Optional hint about which chart to target

    Returns:
        RefinementIntent with classified actions
    """
    start_time = time.time()

    logger.info(f"Classifying refinement intent: {user_feedback[:100]}...")

    try:
        # Build context about current dashboard
        dashboard_summary = _build_dashboard_summary(current_dashboard, chart_goals)

        # Build the prompt
        context = f"""## User Feedback
{user_feedback}

## Current Dashboard State
{dashboard_summary}

{f"## Hint: User is likely referring to chart: {target_chart_hint}" if target_chart_hint else ""}

Analyze the user's feedback and classify their refinement intent.
"""

        messages = [
            SystemMessage(content=REFINEMENT_CLASSIFIER_PROMPT),
            HumanMessage(content=context),
        ]

        # Call LLM
        llm = get_llm(temperature=0.1)  # Very low temperature for classification
        response = await llm.ainvoke(messages)
        response_text = response.content

        logger.debug(f"Classifier response: {response_text[:500]}...")

        # Parse the response
        intent = _parse_classifier_response(response_text)

        execution_time = (time.time() - start_time) * 1000
        logger.info(
            f"Intent classified in {execution_time:.2f}ms: {len(intent.actions)} actions, clarification={intent.requires_clarification}"
        )

        return intent

    except Exception as e:
        logger.exception(f"Intent classification failed: {e}")
        # Return a safe fallback - ask for clarification
        return RefinementIntent(
            actions=[],
            requires_clarification=True,
            clarification_question="I couldn't understand your request. Could you please rephrase what changes you'd like to make to the dashboard?",
            reasoning=f"Classification error: {str(e)}",
        )


def _build_dashboard_summary(
    dashboard: Dict[str, Any], chart_goals: List[Dict[str, Any]]
) -> str:
    """Build a summary of the current dashboard for the classifier."""
    lines = []

    # Dashboard title
    title = dashboard.get("title", "Untitled Dashboard")
    lines.append(f"Dashboard Title: {title}")
    lines.append("")

    # List charts
    individual_specs = dashboard.get("individual_specs", [])
    lines.append("Charts in Dashboard:")

    for i, spec in enumerate(individual_specs):
        chart_id = spec.get("chart_id", f"chart_{i+1}")
        chart_title = spec.get("title", "Untitled")

        # Get chart type from mark
        mark = spec.get("mark", {})
        if isinstance(mark, str):
            chart_type = mark
        else:
            chart_type = mark.get("type", "unknown")

        # Find matching goal for more context
        goal_info = ""
        for goal in chart_goals:
            if goal.get("chart_id") == chart_id:
                goal_info = f" - {goal.get('description', '')}"
                break

        lines.append(f"  - {chart_id}: {chart_title} ({chart_type}){goal_info}")

    return "\n".join(lines)


def _parse_classifier_response(response_text: str) -> RefinementIntent:
    """Parse the LLM response into a RefinementIntent."""

    # Try to extract JSON from code block
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)

    if json_match:
        json_str = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r"\{[\s\S]*\"actions\"[\s\S]*\}", response_text)
        if json_match:
            json_str = json_match.group(0)
        else:
            logger.error("Could not find JSON in classifier response")
            return RefinementIntent(
                requires_clarification=True,
                clarification_question="I couldn't process your request. Could you try rephrasing?",
                reasoning="Failed to parse classifier response",
            )

    try:
        parsed = json.loads(json_str)

        # Parse actions
        actions = []
        for action_data in parsed.get("actions", []):
            try:
                action_type_str = action_data.get("action_type", "")

                # Validate action type
                try:
                    action_type = RefinementActionType(action_type_str)
                except ValueError:
                    logger.warning(f"Invalid action type: {action_type_str}")
                    continue

                action = RefinementAction(
                    action_type=action_type,
                    target_chart_id=action_data.get("target_chart_id"),
                    parameters=action_data.get("parameters", {}),
                    confidence=action_data.get("confidence", 1.0),
                )
                actions.append(action)
            except Exception as e:
                logger.warning(f"Failed to parse action: {e}")
                continue

        return RefinementIntent(
            actions=actions,
            requires_clarification=parsed.get("requires_clarification", False),
            clarification_question=parsed.get("clarification_question"),
            reasoning=parsed.get("reasoning", ""),
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse classifier JSON: {e}")
        return RefinementIntent(
            requires_clarification=True,
            clarification_question="I couldn't process your request. Could you try rephrasing?",
            reasoning=f"JSON parse error: {str(e)}",
        )
