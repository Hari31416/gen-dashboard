"""
State Definitions for Dashboard Generation LangGraph.

This module defines TypedDict state schemas used by the dashboard generation graph:
- DashboardGraphState: Main pipeline state
"""

from typing import TypedDict, Optional, List, Dict, Any
from langchain_agents.dashboard.models import (
    ChartGoal,
    ChartDataResult,
    SingleVizSpec,
    ComposedDashboardSpec,
)


class DashboardGraphState(TypedDict):
    """
    State for the Dashboard Generation LangGraph.
    
    This state flows through the 4-stage pipeline:
    1. Strategy Agent -> chart_goals
    2. Data Agent -> chart_data_results
    3. Viz Spec Agent -> viz_specs
    4. Layout Agent -> dashboard_spec
    """
    
    # =========================================================================
    # Input
    # =========================================================================
    user_prompt: str
    username: str
    connection_name: str
    session_id: str
    
    # Configuration
    max_charts: int
    theme: str
    
    # =========================================================================
    # Database Context (populated at start)
    # =========================================================================
    db_schema: Optional[str]  # Formatted schema string
    db_relationships: Optional[str]  # Formatted relationships string
    db_description: Optional[str]  # Database description
    
    # =========================================================================
    # Agent Outputs
    # =========================================================================
    
    # Strategy Agent output
    chart_goals: Optional[List[Dict[str, Any]]]  # List of ChartGoal as dicts
    strategy_reasoning: Optional[str]
    
    # Data Agent output
    chart_data_results: Optional[List[Dict[str, Any]]]  # List of ChartDataResult as dicts
    data_execution_time_ms: Optional[float]
    
    # Viz Spec Agent output
    viz_specs: Optional[List[Dict[str, Any]]]  # List of SingleVizSpec as dicts
    
    # Layout Agent output (final)
    dashboard_spec: Optional[Dict[str, Any]]  # ComposedDashboardSpec as dict
    
    # =========================================================================
    # Error Handling
    # =========================================================================
    error: Optional[str]
    failed_stage: Optional[str]  # Which stage failed
    
    # =========================================================================
    # Timing
    # =========================================================================
    start_time: Optional[float]
    strategy_time_ms: Optional[float]
    data_time_ms: Optional[float]
    viz_time_ms: Optional[float]
    layout_time_ms: Optional[float]
    total_time_ms: Optional[float]


def create_initial_dashboard_state(
    user_prompt: str,
    username: str,
    connection_name: str,
    session_id: str,
    max_charts: int = 5,
    theme: str = "default",
) -> DashboardGraphState:
    """
    Create initial state for the dashboard generation graph.
    
    Args:
        user_prompt: Natural language request
        username: User's username
        connection_name: Database connection name
        session_id: Unique session identifier
        max_charts: Maximum charts to generate
        theme: Dashboard theme
        
    Returns:
        Initialized DashboardGraphState
    """
    return DashboardGraphState(
        # Input
        user_prompt=user_prompt,
        username=username,
        connection_name=connection_name,
        session_id=session_id,
        max_charts=max_charts,
        theme=theme,
        
        # DB Context
        db_schema=None,
        db_relationships=None,
        db_description=None,
        
        # Agent outputs
        chart_goals=None,
        strategy_reasoning=None,
        chart_data_results=None,
        data_execution_time_ms=None,
        viz_specs=None,
        dashboard_spec=None,
        
        # Error handling
        error=None,
        failed_stage=None,
        
        # Timing
        start_time=None,
        strategy_time_ms=None,
        data_time_ms=None,
        viz_time_ms=None,
        layout_time_ms=None,
        total_time_ms=None,
    )


# =============================================================================
# Refinement State (for /refine endpoint)
# =============================================================================

class RefinementState(TypedDict):
    """
    State for dashboard refinement operations.
    
    Used when the user provides feedback or filter changes.
    """
    session_id: str
    username: str
    connection_name: str
    
    # Previous dashboard state
    previous_dashboard: Dict[str, Any]
    previous_chart_goals: List[Dict[str, Any]]
    previous_sql_queries: List[Dict[str, str]]
    
    # Refinement input
    new_feedback: Optional[str]
    filter_state: Optional[Dict[str, Any]]
    target_chart_id: Optional[str]
    
    # Determine which stage to start from
    start_from_stage: str  # "data", "viz", or "layout"
    
    # Updated outputs
    updated_chart_data: Optional[List[Dict[str, Any]]]
    updated_viz_specs: Optional[List[Dict[str, Any]]]
    updated_dashboard: Optional[Dict[str, Any]]
    
    # Error
    error: Optional[str]
