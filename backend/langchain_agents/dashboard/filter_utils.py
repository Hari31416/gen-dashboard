"""
Filter Utilities for Dashboard.

This module provides helper functions to apply filters to existing SQL queries
in a safe and robust way, primarily using subquery wrapping.
"""

import datetime
from typing import Any, Dict, List, Optional


def apply_filters_to_sql(original_sql: str, filters: Dict[str, Any]) -> str:
    """
    Apply filters to an SQL query by wrapping it in a SELECT * FROM (...) subquery.

    Args:
        original_sql: The original SQL query string.
        filters: Dictionary of column_name -> value to filter by.

    Returns:
        New SQL query string with filters applied.
    """
    if not filters:
        return original_sql

    # Remove any trailing semicolons from the original SQL
    cleaned_sql = original_sql.strip().rstrip(";")

    where_conditions = []

    for column, value in filters.items():
        # Sanitize column name (simple check to prevent injection via keys)
        if not column.replace("_", "").isalnum():
            continue

        # Format value based on type
        formatted_value = _format_sql_value(value)
        where_conditions.append(f"base.{column} = {formatted_value}")

    if not where_conditions:
        return original_sql

    where_clause = " AND ".join(where_conditions)

    # Wrap in subquery
    # We use a subquery "base" to safely apply filters to any valid SELECT statement
    # without needing to parse WHERE/GROUP BY/etc in the original query
    new_sql = f"""
SELECT * 
FROM (
{cleaned_sql}
) AS base 
WHERE {where_clause}
"""
    return new_sql.strip()


def _format_sql_value(value: Any) -> str:
    """Format a value for use in a SQL WHERE clause."""
    if value is None:
        return "NULL"

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, (datetime.date, datetime.datetime)):
        return f"'{value.isoformat()}'"

    # Default to string, escaping single quotes
    str_val = str(value).replace("'", "''")
    return f"'{str_val}'"
