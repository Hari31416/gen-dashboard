"""
LangChain/LangGraph based agent system.

This module provides:
- LLM utilities for LangChain integration
- Database tools for SQL operations
- Dashboard generation agents
"""

# Dashboard generation
from langchain_agents.dashboard.graph import (
    get_dashboard_graph,
    run_dashboard_generation,
    run_dashboard_refresh,
)
from langchain_agents.dashboard.models import (
    ChartDataResult,
    ChartGoal,
    ComposedDashboardSpec,
    DashboardGenerateRequest,
    DashboardRefineRequest,
    DashboardRefreshRequest,
    DashboardResponse,
    SingleVizSpec,
)

# LLM utilities
from langchain_agents.llm_utils import (
    LiteLLMChat,
    convert_dict_to_messages,
    convert_messages_to_dict,
    get_llm,
)

# Existing TTS state (for backward compatibility)
from langchain_agents.state import TTSGraphState, create_initial_tts_state

# Database tools
from langchain_agents.tools.database_tools import DatabaseTools, create_database_tools

__all__ = [
    # LLM utilities
    "get_llm",
    "LiteLLMChat",
    "convert_dict_to_messages",
    "convert_messages_to_dict",
    # State
    "TTSGraphState",
    "create_initial_tts_state",
    # Database tools
    "DatabaseTools",
    "create_database_tools",
    # Dashboard
    "run_dashboard_generation",
    "run_dashboard_refresh",
    "get_dashboard_graph",
    "ChartGoal",
    "ChartDataResult",
    "SingleVizSpec",
    "ComposedDashboardSpec",
    "DashboardGenerateRequest",
    "DashboardRefineRequest",
    "DashboardRefreshRequest",
    "DashboardResponse",
]
