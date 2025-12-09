"""
Refinement Handlers Module.

This module contains handlers for each refinement action type.
Each handler is responsible for executing a specific type of dashboard modification.
"""

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
from langchain_agents.dashboard.refinement.executor import execute_refinement_actions

__all__ = [
    "execute_refinement_actions",
    "handle_rerun_sql",
    "handle_modify_sql",
    "handle_change_chart_type",
    "handle_change_encoding",
    "handle_change_title",
    "handle_change_layout",
    "handle_add_chart",
    "handle_remove_chart",
    "handle_change_theme",
    "handle_full_redesign",
]
