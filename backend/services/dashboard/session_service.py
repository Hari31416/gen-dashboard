"""
Session Service for Dashboard Generation.

This module handles MongoDB-backed session storage for:
- Conversation history per session
- Previous dashboard specifications
- SQL queries for refresh operations
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from env import MONGO_URI
from pymongo import MongoClient
from pymongo.collection import Collection
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


from services.database.connection_pool import mongo_pool


def get_mongo_client() -> MongoClient:
    """Get MongoDB client connection."""
    return mongo_pool.get_client(MONGO_URI)


def get_dashboard_sessions_collection(username: str) -> Collection:
    """
    Get the dashboard sessions collection for a user.

    Args:
        username: Username

    Returns:
        MongoDB collection for dashboard_sessions
    """
    client = get_mongo_client()
    db = client[f"{username}_dashboard"]
    return db["sessions"]


def save_dashboard_session(
    username: str,
    session_id: str,
    user_prompt: str,
    connection_name: str,
    dashboard_spec: Dict[str, Any],
    chart_goals: List[Dict[str, Any]],
    sql_queries: List[Dict[str, str]],
    generation_time_ms: float,
) -> Dict[str, Any]:
    """
    Save a dashboard generation session.

    Args:
        username: User's username
        session_id: Unique session identifier
        user_prompt: Original user request
        connection_name: Database connection used
        dashboard_spec: Generated dashboard specification
        chart_goals: Chart goals from strategy agent
        sql_queries: SQL queries for refresh
        generation_time_ms: Total generation time

    Returns:
        Saved session document
    """
    collection = get_dashboard_sessions_collection(username)

    # Strip inline data from individual_specs to reduce storage size
    # Data will be fetched via URL endpoint instead
    cleaned_dashboard_spec = _strip_inline_data(dashboard_spec)

    session_doc = {
        "session_id": session_id,
        "user_prompt": user_prompt,
        "connection_name": connection_name,
        "dashboard_spec": cleaned_dashboard_spec,
        "chart_goals": chart_goals,
        "sql_queries": sql_queries,
        "generation_time_ms": generation_time_ms,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "refinement_history": [],
    }

    # Upsert to handle updates
    collection.update_one(
        {"session_id": session_id},
        {"$set": _serialize_for_mongo(session_doc)},
        upsert=True,
    )

    logger.info(f"Saved dashboard session: {session_id}")
    return session_doc


def _strip_inline_data(dashboard_spec: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove inline data.values from specs to reduce MongoDB storage.

    Specs will use URL-based data loading instead.
    """
    import copy

    spec = copy.deepcopy(dashboard_spec)

    # Strip from individual_specs
    for individual_spec in spec.get("individual_specs", []):
        if "data" in individual_spec:
            data = individual_spec["data"]
            # Keep URL-based data references, strip only inline values
            if isinstance(data, dict) and "values" in data and "url" not in data:
                # If there's inline data but no URL, the spec wasn't properly using URL loading
                # Just clear the values to save space (data fetched via endpoint anyway)
                individual_spec["data"] = {"values": []}  # Placeholder
            elif isinstance(data, dict) and "url" in data:
                # URL-based - keep as is
                pass

    # Strip from vega_lite_spec (concat charts)
    for key in ["hconcat", "vconcat", "concat"]:
        if key in spec.get("vega_lite_spec", {}):
            for chart in spec["vega_lite_spec"][key]:
                if "data" in chart and isinstance(chart["data"], dict):
                    if "values" in chart["data"]:
                        chart["data"]["values"] = []  # Placeholder

    return spec


def _serialize_for_mongo(obj: Any) -> Any:
    """
    Recursively convert non-serializable objects for MongoDB.
    Handles datetime.date, datetime.datetime, Decimal, and other types.
    """
    import datetime
    from decimal import Decimal

    if isinstance(obj, datetime.datetime):
        return obj  # MongoDB handles datetime.datetime natively
    elif isinstance(obj, datetime.date):
        return obj.isoformat()  # Convert date to string
    elif isinstance(obj, Decimal):
        return float(obj)  # Convert Decimal to float for MongoDB
    elif isinstance(obj, dict):
        return {key: _serialize_for_mongo(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_for_mongo(item) for item in obj]
    elif hasattr(obj, "__dict__"):
        # Handle Pydantic models or other objects
        return _serialize_for_mongo(obj.__dict__)
    else:
        return obj


def get_dashboard_session(
    username: str,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve a dashboard session.

    Args:
        username: User's username
        session_id: Session ID to retrieve

    Returns:
        Session document or None if not found
    """
    collection = get_dashboard_sessions_collection(username)

    session = collection.find_one({"session_id": session_id})

    if session:
        # Remove MongoDB _id for JSON serialization
        session.pop("_id", None)

    return session


def update_dashboard_session(
    username: str,
    session_id: str,
    dashboard_spec: Dict[str, Any],
    refinement_feedback: Optional[str] = None,
    chart_goals: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    """
    Update a dashboard session after refinement.

    Args:
        username: User's username
        session_id: Session ID
        dashboard_spec: Updated dashboard specification
        refinement_feedback: Optional feedback that triggered the update
        chart_goals: Optional updated chart goals

    Returns:
        True if updated, False if not found
    """
    collection = get_dashboard_sessions_collection(username)

    update_fields = {
        "dashboard_spec": dashboard_spec,
        "sql_queries": dashboard_spec.get("sql_queries", []),
        "updated_at": datetime.utcnow(),
    }

    # Also update chart_goals if provided
    if chart_goals is not None:
        update_fields["chart_goals"] = chart_goals

    # Serialize to handle MongoDB reserved characters ($ and .)
    serialized_fields = _serialize_for_mongo(update_fields)
    update_doc = {"$set": serialized_fields}

    # Add refinement to history
    if refinement_feedback:
        update_doc["$push"] = {
            "refinement_history": {
                "feedback": refinement_feedback,
                "timestamp": datetime.utcnow(),
            }
        }

    result = collection.update_one(
        {"session_id": session_id},
        update_doc,
    )

    return result.modified_count > 0


def update_dashboard_layout(
    username: str,
    session_id: str,
    layout_config: Dict[str, Any],
) -> bool:
    """
    Update only the layout configuration for a dashboard session.

    This is called when the user customizes the layout from the frontend.

    Args:
        username: User's username
        session_id: Session ID
        layout_config: New layout configuration (react-grid-layout format)

    Returns:
        True if updated, False if not found
    """
    collection = get_dashboard_sessions_collection(username)

    # Mark layout as custom since user modified it
    layout_config["custom"] = True

    update_doc = {
        "$set": {
            "dashboard_spec.layout_config": layout_config,
            "updated_at": datetime.utcnow(),
        }
    }

    result = collection.update_one(
        {"session_id": session_id},
        update_doc,
    )

    logger.info(
        f"Updated layout for session {session_id}: modified={result.modified_count > 0}"
    )
    return result.modified_count > 0


def list_dashboard_sessions(
    username: str,
    limit: int = 20,
    skip: int = 0,
) -> List[Dict[str, Any]]:
    """
    List dashboard sessions for a user.

    Args:
        username: User's username
        limit: Maximum sessions to return
        skip: Number of sessions to skip (for pagination)

    Returns:
        List of session documents (without full specs for efficiency)
    """
    collection = get_dashboard_sessions_collection(username)

    # Only return summary fields, not full specs
    projection = {
        "_id": 0,
        "session_id": 1,
        "user_prompt": 1,
        "connection_name": 1,
        "dashboard_spec.title": 1,
        "dashboard_spec.chart_count": 1,
        "created_at": 1,
        "updated_at": 1,
    }

    sessions = list(
        collection.find({}, projection).sort("created_at", -1).skip(skip).limit(limit)
    )

    return sessions


def delete_dashboard_session(
    username: str,
    session_id: str,
) -> bool:
    """
    Delete a dashboard session.

    Args:
        username: User's username
        session_id: Session ID to delete

    Returns:
        True if deleted, False if not found
    """
    collection = get_dashboard_sessions_collection(username)

    result = collection.delete_one({"session_id": session_id})

    return result.deleted_count > 0


def update_chart_customizations(
    username: str,
    session_id: str,
    chart_customizations: Dict[str, Any],
) -> bool:
    """
    Update chart customization settings for a dashboard session.

    This stores user's visual preferences (colors, themes, axis settings, etc.)
    for individual charts in MongoDB.

    Args:
        username: User's username
        session_id: Session ID
        chart_customizations: Dict mapping chart_id -> customization settings

    Returns:
        True if updated, False if not found
    """
    collection = get_dashboard_sessions_collection(username)

    update_doc = {
        "$set": {
            "chart_customizations": chart_customizations,
            "updated_at": datetime.utcnow(),
        }
    }

    result = collection.update_one(
        {"session_id": session_id},
        update_doc,
    )

    logger.info(
        f"Updated chart customizations for session {session_id}: "
        f"modified={result.modified_count > 0}"
    )
    return result.modified_count > 0
