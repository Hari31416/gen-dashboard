"""
LangGraph Workflow for Dashboard Generation.

This module defines the main graph that orchestrates the 4-stage
sequential agent pipeline:
1. Strategy Agent -> Chart Goals
2. Data Agent -> SQL & Data
3. Viz Spec Agent -> Vega-Lite Specs
4. Layout Agent -> Composed Dashboard
"""

import time
import uuid
from typing import Dict, Any, Optional, AsyncGenerator

from langgraph.graph import StateGraph, END

from langchain_agents.dashboard.state import (
    DashboardGraphState,
    create_initial_dashboard_state,
)
from langchain_agents.dashboard.agents.strategy_agent import strategy_agent_node
from langchain_agents.dashboard.agents.data_agent import data_agent_node
from langchain_agents.dashboard.agents.viz_spec_agent import viz_spec_agent_node
from langchain_agents.dashboard.agents.layout_agent import layout_agent_node
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


def _should_continue_after_strategy(state: DashboardGraphState) -> str:
    """Check if strategy stage succeeded."""
    if state.get("error"):
        logger.warning(f"Strategy stage failed: {state['error']}")
        return "error"
    if not state.get("chart_goals"):
        logger.warning("No chart goals generated")
        return "error"
    return "continue"


def _should_continue_after_data(state: DashboardGraphState) -> str:
    """Check if data stage succeeded."""
    if state.get("error"):
        logger.warning(f"Data stage failed: {state['error']}")
        return "error"

    results = state.get("chart_data_results", [])
    successful = [r for r in results if not r.get("error")]

    if not successful:
        logger.warning("No successful data results")
        return "error"

    return "continue"


def _should_continue_after_viz(state: DashboardGraphState) -> str:
    """Check if viz spec stage succeeded."""
    if state.get("error"):
        logger.warning(f"Viz spec stage failed: {state['error']}")
        return "error"
    if not state.get("viz_specs"):
        logger.warning("No viz specs generated")
        return "error"
    return "continue"


def _error_handler_node(state: DashboardGraphState) -> Dict[str, Any]:
    """Handle errors and return error state."""
    return {
        "error": state.get("error", "Unknown error occurred"),
        "failed_stage": state.get("failed_stage", "unknown"),
    }


def create_dashboard_graph() -> StateGraph:
    """
    Create the LangGraph workflow for dashboard generation.

    Returns:
        Compiled StateGraph
    """
    # Create graph with state schema
    workflow = StateGraph(DashboardGraphState)

    # Add nodes
    workflow.add_node("strategy", strategy_agent_node)
    workflow.add_node("data", data_agent_node)
    workflow.add_node("viz_spec", viz_spec_agent_node)
    workflow.add_node("layout", layout_agent_node)
    workflow.add_node("error_handler", _error_handler_node)

    # Set entry point
    workflow.set_entry_point("strategy")

    # Add conditional edges after each stage
    workflow.add_conditional_edges(
        "strategy",
        _should_continue_after_strategy,
        {
            "continue": "data",
            "error": "error_handler",
        },
    )

    workflow.add_conditional_edges(
        "data",
        _should_continue_after_data,
        {
            "continue": "viz_spec",
            "error": "error_handler",
        },
    )

    workflow.add_conditional_edges(
        "viz_spec",
        _should_continue_after_viz,
        {
            "continue": "layout",
            "error": "error_handler",
        },
    )

    # Layout and error_handler go to END
    workflow.add_edge("layout", END)
    workflow.add_edge("error_handler", END)

    return workflow.compile()


# Compiled graph singleton
_dashboard_graph = None


def get_dashboard_graph():
    """Get the compiled dashboard graph (singleton)."""
    global _dashboard_graph
    if _dashboard_graph is None:
        _dashboard_graph = create_dashboard_graph()
    return _dashboard_graph


async def run_dashboard_generation(
    user_prompt: str,
    username: str,
    connection_name: str,
    session_id: Optional[str] = None,
    max_charts: int = 10,
    theme: str = "default",
) -> Dict[str, Any]:
    """
    Run the full dashboard generation pipeline.

    Args:
        user_prompt: Natural language request
        username: User's username
        connection_name: Database connection name
        session_id: Optional session ID (generated if not provided)
        max_charts: Maximum charts to generate (1-10)
        theme: Dashboard theme

    Returns:
        Final dashboard state with dashboard_spec or error
    """
    start_time = time.time()

    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())

    logger.info(f"Starting dashboard generation for session {session_id}")

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

    # Get graph and run
    graph = get_dashboard_graph()

    try:
        # Run the graph
        final_state = await graph.ainvoke(initial_state)

        # Calculate total time
        total_time = (time.time() - start_time) * 1000
        final_state["total_time_ms"] = total_time

        if final_state.get("error"):
            logger.error(f"Dashboard generation failed: {final_state['error']}")
        else:
            logger.info(f"Dashboard generation completed in {total_time:.2f}ms")

        return final_state

    except Exception as e:
        logger.exception(f"Dashboard generation failed with exception: {e}")
        return {
            "error": str(e),
            "failed_stage": "graph_execution",
            "session_id": session_id,
            "total_time_ms": (time.time() - start_time) * 1000,
        }


async def run_dashboard_refresh(
    session_id: str,
    username: str,
    connection_name: str,
    sql_queries: list,
) -> Dict[str, Any]:
    """
    Refresh dashboard data by re-executing stored SQL queries.

    This does NOT use the LLM - it simply re-runs the saved queries.

    Args:
        session_id: Session ID
        username: Username
        connection_name: Database connection
        sql_queries: List of {chart_id, sql_query} dicts

    Returns:
        Updated chart data results
    """
    from langchain_agents.dashboard.agents.data_agent import _execute_query_safe
    from services.database.db_config_models import get_db_config
    from services.database.db_connection_service import build_connection_string

    logger.info(f"Refreshing dashboard data for session {session_id}")

    try:
        db_config = get_db_config(username, connection_name)
        if not db_config:
            return {"error": f"Database configuration not found for {connection_name}"}

        connection_string = build_connection_string(**db_config)

        # Re-execute all queries
        results = []
        for q in sql_queries:
            chart_id = q.get("chart_id")
            sql_query = q.get("sql_query")

            result = _execute_query_safe(connection_string, chart_id, sql_query)
            results.append(result)

        return {
            "success": True,
            "chart_data_results": results,
        }

    except Exception as e:
        logger.exception(f"Dashboard refresh failed: {e}")
        return {"error": str(e)}


async def run_selective_refinement(
    session_id: str,
    username: str,
    connection_name: str,
    actions: list,
    current_dashboard: Dict[str, Any],
    chart_goals: list,
    sql_queries: list,
    user_feedback: str,
    original_prompt: str,
) -> Dict[str, Any]:
    """
    Execute selective refinement based on classified actions.

    Delegates to the modular refinement executor which supports:
    - Parallel execution of independent actions (title, chart type, rerun SQL)
    - Sequential execution of dependent actions (modify SQL, add chart, etc.)
    - Context passing for LLM-based operations

    Args:
        session_id: Session ID
        username: Username
        connection_name: Database connection
        actions: List of RefinementAction objects
        current_dashboard: Current dashboard spec
        chart_goals: Original chart goals
        sql_queries: Current SQL queries
        user_feedback: User's feedback text
        original_prompt: Original generation prompt

    Returns:
        Updated dashboard spec and any changed data
    """
    from langchain_agents.dashboard.refinement.executor import (
        execute_refinement_actions,
    )

    logger.info(
        f"Running selective refinement with {len(actions)} actions for session {session_id}"
    )

    return await execute_refinement_actions(
        session_id=session_id,
        username=username,
        connection_name=connection_name,
        actions=actions,
        current_dashboard=current_dashboard,
        chart_goals=chart_goals,
        sql_queries=sql_queries,
        user_feedback=user_feedback,
        original_prompt=original_prompt,
    )


# =============================================================================
# Streaming Dashboard Generation
# =============================================================================

# Progress stage mapping with base percentages
# Dynamic sub-progress within stages (e.g., 0-25 for strategy, 25-50 for data)
STAGE_PROGRESS = {
    "strategy": {"base": 0, "end": 25, "message": "Planning chart objectives..."},
    "data": {
        "base": 25,
        "end": 50,
        "message": "Generating and executing SQL queries...",
    },
    "viz_spec": {"base": 50, "end": 75, "message": "Creating visualizations..."},
    "layout": {"base": 75, "end": 100, "message": "Composing dashboard layout..."},
    "error_handler": {"base": -1, "end": -1, "message": "Error occurred"},
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

    Yields progress updates after each stage completes, with dynamic
    sub-progress within stages based on items processed.

    Yields:
        dict with either:
        - {"type": "progress", "stage": str, "progress": int, "message": str}
        - {"type": "complete", "result": dict}
        - {"type": "error", "error": str, "stage": str}
    """
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
                base_progress = stage_info.get("base", 0)
                end_progress = stage_info.get("end", base_progress)
                message = stage_info.get("message", f"Processing {node_name}...")

                # Check for errors in state update
                if state_update.get("error"):
                    yield {
                        "type": "error",
                        "error": state_update["error"],
                        "stage": node_name,
                    }
                    return

                # Calculate dynamic sub-progress based on items completed
                progress = end_progress  # Default to end of stage
                details = {}

                if node_name == "strategy":
                    charts_planned = len(state_update.get("chart_goals", []))
                    details["charts_planned"] = charts_planned
                    # Dynamic: max_charts requested vs planned
                    if max_charts > 0:
                        ratio = min(charts_planned / max_charts, 1.0)
                        progress = int(
                            base_progress + (end_progress - base_progress) * ratio
                        )
                    progress = end_progress  # Stage complete

                elif node_name == "data":
                    results = state_update.get("chart_data_results", [])
                    queries_executed = len(results)
                    successful = len([r for r in results if not r.get("error")])
                    details["queries_executed"] = queries_executed
                    details["successful_queries"] = successful
                    progress = end_progress  # Stage complete

                elif node_name == "viz_spec":
                    specs_created = len(state_update.get("viz_specs", []))
                    details["specs_created"] = specs_created
                    progress = end_progress  # Stage complete

                elif node_name == "layout":
                    progress = end_progress  # 100% complete

                # Yield progress update
                yield {
                    "type": "progress",
                    "stage": node_name,
                    "progress": progress,
                    "message": message,
                    "details": details if details else None,
                }

                # Keep track of final state
                if final_state is None:
                    final_state = state_update.copy()
                else:
                    final_state.update(state_update)

        # Calculate total time
        total_time = (time.time() - start_time) * 1000
        if final_state:
            final_state["total_time_ms"] = total_time
            final_state["session_id"] = session_id

        # Yield completion
        yield {
            "type": "complete",
            "result": final_state or {},
        }

        logger.info(f"Streaming dashboard generation completed in {total_time:.2f}ms")

    except Exception as e:
        logger.exception(f"Streaming dashboard generation failed: {e}")
        yield {
            "type": "error",
            "error": str(e),
            "stage": "graph_execution",
        }
