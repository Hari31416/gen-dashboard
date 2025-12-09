"""
Refinement Executor.

Orchestrates the execution of refinement actions with support for
parallel execution using asyncio.gather where possible.
"""

import asyncio
import copy
import time
from typing import Dict, Any, List

from langchain_agents.dashboard.models import RefinementActionType, RefinementAction
from langchain_agents.dashboard.refinement.handlers import (
    handle_rerun_sql,
    handle_modify_sql,
    handle_change_chart_type,
    handle_change_encoding,
    handle_change_title,
    handle_change_layout,
    handle_add_chart,
    handle_remove_chart,
    handle_change_theme,
    handle_full_redesign,
)
from services.database.db_config_models import get_db_config
from services.database.db_connection_service import build_connection_string
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


# Action types that can be executed in parallel (independent operations)
PARALLELIZABLE_ACTIONS = {
    RefinementActionType.CHANGE_TITLE,
    RefinementActionType.CHANGE_CHART_TYPE,
    RefinementActionType.RERUN_SQL,
}

# Action types that need sequential execution (depend on previous state)
SEQUENTIAL_ACTIONS = {
    RefinementActionType.MODIFY_SQL,
    RefinementActionType.CHANGE_ENCODING,
    RefinementActionType.CHANGE_LAYOUT,
    RefinementActionType.ADD_CHART,
    RefinementActionType.REMOVE_CHART,
    RefinementActionType.CHANGE_THEME,
    RefinementActionType.FULL_REDESIGN,
}


async def execute_refinement_actions(
    session_id: str,
    username: str,
    connection_name: str,
    actions: List[RefinementAction],
    current_dashboard: Dict[str, Any],
    chart_goals: List[Dict[str, Any]],
    sql_queries: List[Dict[str, str]],
    user_feedback: str,
    original_prompt: str,
) -> Dict[str, Any]:
    """
    Execute refinement actions with parallel execution where possible.
    
    Groups actions by type and executes parallelizable actions concurrently,
    while sequential actions are processed in order.
    
    Args:
        session_id: Session ID
        username: Username
        connection_name: Database connection name
        actions: List of RefinementAction objects
        current_dashboard: Current dashboard spec
        chart_goals: Current chart goals
        sql_queries: Current SQL queries
        user_feedback: User's feedback text
        original_prompt: Original generation prompt
        
    Returns:
        Dict with updated dashboard_spec and sql_queries
    """
    start_time = time.time()
    logger.info(f"Executing {len(actions)} refinement actions for session {session_id}")
    
    # Make deep copies to avoid modifying originals
    updated_dashboard = copy.deepcopy(current_dashboard)
    updated_sql_queries = copy.deepcopy(sql_queries)
    updated_chart_goals = copy.deepcopy(chart_goals)
    
    # Get database connection
    db_config = get_db_config(username, connection_name)
    if not db_config:
        return {"error": f"Database configuration not found for {connection_name}"}
    
    connection_string = build_connection_string(**db_config)
    
    try:
        # Check for full_redesign first - it overrides everything else
        full_redesign_actions = [
            a for a in actions if a.action_type == RefinementActionType.FULL_REDESIGN
        ]
        if full_redesign_actions:
            logger.info("Full redesign requested - executing only this action")
            result = await handle_full_redesign(
                updated_dashboard=updated_dashboard,
                updated_sql_queries=updated_sql_queries,
                chart_goals=updated_chart_goals,
                original_prompt=original_prompt,
                user_feedback=user_feedback,
                username=username,
                connection_name=connection_name,
                session_id=session_id,
            )
            
            if result.get("error"):
                return {"error": result["error"]}
            
            total_time = (time.time() - start_time) * 1000
            return {
                "dashboard_spec": result.get("dashboard_spec", updated_dashboard),
                "updated_sql_queries": result.get("sql_queries", updated_sql_queries),
                "total_time_ms": total_time,
            }
        
        # Group actions by parallelizability
        parallel_actions = [a for a in actions if a.action_type in PARALLELIZABLE_ACTIONS]
        sequential_actions = [a for a in actions if a.action_type in SEQUENTIAL_ACTIONS]
        
        # =====================================================================
        # Execute parallelizable actions concurrently
        # =====================================================================
        if parallel_actions:
            logger.info(f"Executing {len(parallel_actions)} actions in parallel")
            
            parallel_tasks = []
            for action in parallel_actions:
                if action.action_type == RefinementActionType.CHANGE_TITLE:
                    parallel_tasks.append(
                        handle_change_title(action, updated_dashboard)
                    )
                elif action.action_type == RefinementActionType.CHANGE_CHART_TYPE:
                    parallel_tasks.append(
                        handle_change_chart_type(action, updated_dashboard)
                    )
                elif action.action_type == RefinementActionType.RERUN_SQL:
                    parallel_tasks.append(
                        handle_rerun_sql(
                            action, updated_dashboard, updated_sql_queries, connection_string
                        )
                    )
            
            if parallel_tasks:
                results = await asyncio.gather(*parallel_tasks, return_exceptions=True)
                
                # Merge results into updated_dashboard
                for result in results:
                    if isinstance(result, Exception):
                        logger.error(f"Parallel action failed: {result}")
                        continue
                    if isinstance(result, dict):
                        _merge_result(updated_dashboard, result)
        
        # =====================================================================
        # Execute sequential actions in order
        # =====================================================================
        for action in sequential_actions:
            logger.info(f"Executing sequential action: {action.action_type.value}")
            
            try:
                if action.action_type == RefinementActionType.REMOVE_CHART:
                    result = await handle_remove_chart(
                        action, updated_dashboard, updated_sql_queries
                    )
                    
                elif action.action_type == RefinementActionType.MODIFY_SQL:
                    result = await handle_modify_sql(
                        action=action,
                        updated_dashboard=updated_dashboard,
                        updated_sql_queries=updated_sql_queries,
                        updated_chart_goals=updated_chart_goals,
                        original_prompt=original_prompt,
                        user_feedback=user_feedback,
                        username=username,
                        connection_name=connection_name,
                        session_id=session_id,
                    )
                    
                elif action.action_type == RefinementActionType.CHANGE_ENCODING:
                    result = await handle_change_encoding(
                        action=action,
                        updated_dashboard=updated_dashboard,
                        updated_chart_goals=updated_chart_goals,
                        user_feedback=user_feedback,
                    )
                    
                elif action.action_type == RefinementActionType.CHANGE_LAYOUT:
                    result = await handle_change_layout(
                        action=action,
                        updated_dashboard=updated_dashboard,
                        updated_chart_goals=updated_chart_goals,
                        original_prompt=original_prompt,
                        user_feedback=user_feedback,
                        username=username,
                        connection_name=connection_name,
                        session_id=session_id,
                    )
                    
                elif action.action_type == RefinementActionType.ADD_CHART:
                    result = await handle_add_chart(
                        action=action,
                        updated_dashboard=updated_dashboard,
                        updated_sql_queries=updated_sql_queries,
                        user_feedback=user_feedback,
                        username=username,
                        connection_name=connection_name,
                        session_id=session_id,
                    )
                    
                elif action.action_type == RefinementActionType.CHANGE_THEME:
                    result = await handle_change_theme(
                        action=action,
                        updated_dashboard=updated_dashboard,
                    )
                else:
                    logger.warning(f"Unknown action type: {action.action_type}")
                    continue
                
                # Merge result
                if isinstance(result, dict):
                    _merge_result(updated_dashboard, result)
                    if result.get("sql_queries"):
                        updated_sql_queries = result["sql_queries"]
                        
            except Exception as e:
                logger.error(f"Sequential action {action.action_type.value} failed: {e}")
                # Continue with other actions
        
        total_time = (time.time() - start_time) * 1000
        logger.info(f"Selective refinement completed in {total_time:.2f}ms")
        
        return {
            "dashboard_spec": updated_dashboard,
            "updated_sql_queries": updated_sql_queries,
            "total_time_ms": total_time,
        }
        
    except Exception as e:
        logger.exception(f"Refinement execution failed: {e}")
        return {"error": str(e)}


def _merge_result(dashboard: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Merge handler result into dashboard (in-place)."""
    if not result:
        return
    
    # Update individual_specs if present
    if "individual_specs" in result:
        dashboard["individual_specs"] = result["individual_specs"]
    
    # Update title if present
    if "title" in result:
        dashboard["title"] = result["title"]
    
    # Update layout_config if present
    if "layout_config" in result:
        dashboard["layout_config"] = result["layout_config"]
    
    # Update chart_count if present
    if "chart_count" in result:
        dashboard["chart_count"] = result["chart_count"]
