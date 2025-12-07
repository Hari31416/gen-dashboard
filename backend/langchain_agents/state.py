"""
State definitions for the LangGraph-based unified agent system.

This module defines all the TypedDict state schemas used across the graphs:
- MainGraphState: The main graph state
- TTSGraphState: Text-to-SQL subgraph state
- AnalyzerGraphState: Analyzer subgraph state
"""

from typing import TypedDict, Optional, List, Dict, Any, Annotated, Literal


def merge_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, with right values taking precedence."""
    if left is None:
        return right or {}
    if right is None:
        return left or {}
    return {**left, **right}


def append_messages(
    left: List[Dict[str, str]], right: List[Dict[str, str]]
) -> List[Dict[str, str]]:
    """Append new messages to existing message list."""
    if left is None:
        return right or []
    if right is None:
        return left or []
    return left + right


class ConversationMessage(TypedDict):
    """A single message in the conversation."""

    role: str  # 'user', 'assistant', 'system'
    content: str


class TTSGraphState(TypedDict):
    """State for the Text-to-SQL (TTS) subgraph.

    This state is used by:
    - DBSelectorAgent: Selects the appropriate database
    - ReActTTSAgent: Generates SQL and retrieves data
    """

    # Input
    user_query: str
    username: str

    # DB Selection
    selected_connection: Optional[str]
    table_name: Optional[str]
    db_selection_reasoning: Optional[str]

    # ReAct TTS Agent outputs
    dataframe: Optional[Any]  # pd.DataFrame - using Any to avoid serialization issues
    sql_query: Optional[str]
    tts_iterations: Optional[int]
    tts_execution_history: Optional[List[Dict[str, str]]]

    # Error handling
    error: Optional[str]


def create_initial_tts_state(
    user_query: str,
    username: str,
    selected_connection: Optional[str] = None,
    table_name: Optional[str] = None,
    db_selection_reasoning: Optional[str] = None,
) -> TTSGraphState:
    """Create initial state for the TTS subgraph."""
    return {
        "user_query": user_query,
        "username": username,
        "selected_connection": selected_connection,
        "table_name": table_name,
        "db_selection_reasoning": db_selection_reasoning,
        "dataframe": None,
        "sql_query": None,
        "tts_iterations": None,
        "tts_execution_history": None,
        "error": None,
    }
