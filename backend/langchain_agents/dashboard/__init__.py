"""
Dashboard Generation Agents

This module contains the multi-agent pipeline for dashboard generation.

Agents:
- Strategy Agent: Plans the dashboard structure (3-5 charts)
- Data Agent: Generates and executes SQL queries
- Viz Spec Agent: Creates Vega-Lite specifications
- Layout Agent: Composes the final dashboard layout
"""

from langchain_agents.dashboard.models import (
    ChartGoal,
    ChartType,
    AggregationType,
    ChartDataResult,
    SingleVizSpec,
    ComposedDashboardSpec,
    DashboardGenerateRequest,
    DashboardRefineRequest,
    DashboardRefreshRequest,
    DashboardResponse,
)

from langchain_agents.dashboard.state import (
    DashboardGraphState,
    create_initial_dashboard_state,
)

__all__ = [
    "ChartGoal",
    "ChartType",
    "AggregationType",
    "ChartDataResult",
    "SingleVizSpec",
    "ComposedDashboardSpec",
    "DashboardGenerateRequest",
    "DashboardRefineRequest",
    "DashboardRefreshRequest",
    "DashboardResponse",
    "DashboardGraphState",
    "create_initial_dashboard_state",
]
