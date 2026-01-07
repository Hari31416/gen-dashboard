"""
Server-Sent Events (SSE) utilities for streaming responses.
"""

import json
from typing import Any
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder for Decimal types."""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def format_sse_event(event_type: str, data: Any, event_id: str | None = None) -> str:
    """
    Format data as an SSE event string.

    Args:
        event_type: Event name (e.g., 'progress', 'complete', 'error')
        data: Data payload (will be JSON serialized)
        event_id: Optional event ID for client reconnection

    Returns:
        SSE-formatted string
    """
    lines = []

    if event_id:
        lines.append(f"id: {event_id}")

    lines.append(f"event: {event_type}")

    # JSON serialize the data
    if isinstance(data, str):
        json_data = data
    else:
        # Use custom encoder to handle decimals
        json_data = json.dumps(data, cls=DecimalEncoder)

    lines.append(f"data: {json_data}")

    # SSE requires double newline to end event
    return "\n".join(lines) + "\n\n"


def format_progress_event(
    stage: str, progress: int, message: str, details: dict | None = None
) -> str:
    """
    Format a progress update event.

    Args:
        stage: Current stage name
        progress: Progress percentage (0-100)
        message: Human-readable status message
        details: Optional additional details

    Returns:
        SSE-formatted progress event
    """
    data = {
        "stage": stage,
        "progress": progress,
        "message": message,
    }
    if details:
        data["details"] = details

    return format_sse_event("progress", data)


def format_complete_event(result: dict) -> str:
    """Format a completion event with the final result."""
    return format_sse_event("complete", result)


def format_error_event(error: str, stage: str | None = None) -> str:
    """Format an error event."""
    data = {"error": error}
    if stage:
        data["failed_stage"] = stage
    return format_sse_event("error", data)
