"""
Database tools for LangGraph agents.

This module provides database-related tools that wrap the existing
database services for use with LangChain/LangGraph agents.
"""

from typing import Any, Dict, List, Optional, Type, Union
from langchain_core.tools import BaseTool, tool
from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Field
import pandas as pd
import re

from services.database.db_config_models import (
    get_db_config,
    get_db_info,
    get_db_relationships,
)
from services.database.db_connection_service import (
    build_connection_string,
    run_query_and_return_df,
    dry_run_sql_query,
    fetch_table_schemas,
)
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


def check_for_sql_safety(sql_query: str) -> bool:
    """Returns True if the SQL query is safe, False otherwise."""
    unsafe_patterns = [
        r"\bDROP\s+TABLE\b",
        r"\bDELETE\s+FROM\b",
        r"\bTRUNCATE\s+TABLE\b",
        r"\bALTER\s+TABLE\b",
        r"\bUPDATE\s+\w+\s+SET\b(?!.*\bWHERE\b)",
    ]
    for pattern in unsafe_patterns:
        if re.search(pattern, sql_query, re.IGNORECASE):
            return False
    return True


class GetTableSampleInput(BaseModel):
    """Input for get_table_sample tool."""

    table_name: str = Field(description="Name of the table to sample")
    limit: int = Field(default=5, description="Number of rows to return")


class GetColumnValuesInput(BaseModel):
    """Input for get_column_values tool."""

    table_name: str = Field(description="Name of the table")
    column_name: str = Field(description="Name of the column")
    limit: int = Field(default=10, description="Maximum distinct values to return")


class RunSQLQueryInput(BaseModel):
    """Input for run_sql_query tool."""

    sql_query: str = Field(description="SQL query to execute")
    dry_run: bool = Field(
        default=True, description="If True, validate query without executing"
    )


class GetTableInfoInput(BaseModel):
    """Input for get_table_info tool."""

    table_name: str = Field(description="Name of the table to get info for")


class DatabaseTools:
    """
    Collection of database tools for a specific connection.

    This class creates LangChain-compatible tools that wrap the existing
    database service functions.
    """

    def __init__(self, username: str, connection_name: str):
        """
        Initialize database tools for a specific connection.

        Args:
            username: The username for database access.
            connection_name: The name of the database connection.
        """
        self.username = username
        self.connection_name = connection_name
        self.db_config = get_db_config(username, connection_name)

        if not self.db_config:
            raise ValueError(f"Database configuration not found for {connection_name}")

        self.connection_string = build_connection_string(**self.db_config)
        logger.info(f"Initialized DatabaseTools for {connection_name}")

    def get_db_schema(self) -> Dict[str, Any]:
        """Get high-level schema information."""
        info = get_db_info(self.username, self.connection_name)
        if not info:
            # Fallback if not cached
            return fetch_table_schemas(**self.db_config)

        # Simplify for the agent
        tables = []
        for t in info.get("tables", []):
            tables.append(
                {
                    "table_name": t.get("table_name"),
                    "description": t.get("table_description"),
                }
            )
        return {"tables": tables, "database_name": info.get("database_name")}

    def get_table_info(self, table_name: str) -> Dict[str, Any]:
        """Get detailed information about a specific table."""
        info = get_db_info(self.username, self.connection_name)
        if info:
            for t in info.get("tables", []):
                if t.get("table_name") == table_name:
                    return t

        # Fallback fetch
        schema = fetch_table_schemas(tables_to_fetch=[table_name], **self.db_config)
        if schema.get("tables"):
            return schema["tables"][0]
        return {"error": f"Table {table_name} not found"}

    def get_table_sample(self, table_name: str, limit: int = 5) -> pd.DataFrame:
        """Get sample rows from a table."""
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        try:
            return run_query_and_return_df(self.connection_string, query)
        except Exception as e:
            return pd.DataFrame({"error": [str(e)]})

    def get_column_values(
        self, table_name: str, column_name: str, limit: int = 10
    ) -> List[Any]:
        """Get distinct values from a column."""
        query = f"SELECT DISTINCT {column_name} FROM {table_name} LIMIT {limit}"
        try:
            df = run_query_and_return_df(self.connection_string, query)
            return df[column_name].tolist()
        except Exception as e:
            return [f"Error: {str(e)}"]

    def run_sql_query(
        self, sql_query: str, dry_run: bool = True
    ) -> Union[Dict[str, Any], pd.DataFrame]:
        """Run or validate a SQL query."""
        if not check_for_sql_safety(sql_query):
            return {
                "success": False,
                "error": "Unsafe SQL query detected. Do not use UPDATE/DELETE/ALTER/DROP statements.",
            }
        if dry_run:
            logger.debug(f"Dry run SQL: {sql_query}")
            return dry_run_sql_query(self.connection_string, sql_query)

        try:
            logger.debug(f"Executing SQL: {sql_query}")
            df = run_query_and_return_df(self.connection_string, sql_query)
            return {"success": True, "df": df}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_tools(self) -> List[BaseTool]:
        """
        Create LangChain tools for this database connection.

        Returns:
            List of BaseTool instances.
        """
        # Use closures to capture self
        db_tools = self

        @tool
        def get_db_schema_tool() -> str:
            """Get high-level database schema information including table names and descriptions."""
            schema = db_tools.get_db_schema()
            return str(schema)

        @tool
        def get_table_info_tool(table_name: str) -> str:
            """Get detailed information about a specific table including columns and their types."""
            info = db_tools.get_table_info(table_name)
            return str(info)

        @tool
        def get_table_sample_tool(table_name: str, limit: int = 5) -> str:
            """Get sample rows from a table to understand the data content."""
            df = db_tools.get_table_sample(table_name, limit)
            return df.to_string()

        @tool
        def get_column_values_tool(
            table_name: str, column_name: str, limit: int = 10
        ) -> str:
            """Get distinct values from a column to understand possible filter values."""
            values = db_tools.get_column_values(table_name, column_name, limit)
            return str(values)

        @tool
        def run_sql_query_tool(sql_query: str, dry_run: bool = True) -> str:
            """Run a SQL query. Set dry_run=True to validate syntax, dry_run=False to execute."""
            result = db_tools.run_sql_query(sql_query, dry_run)
            if isinstance(result, dict):
                if result.get("success") and "df" in result:
                    return f"Success. DataFrame shape: {result['df'].shape}\n{result['df'].to_string()}"
                return str(result)
            return str(result)

        return [
            get_db_schema_tool,
            get_table_info_tool,
            get_table_sample_tool,
            get_column_values_tool,
            run_sql_query_tool,
        ]

    def get_tools_as_functions(self) -> Dict[str, Any]:
        """
        Get tools as callable functions for the code executor.

        Returns:
            Dict mapping function names to callables.
        """
        return {
            "get_db_schema": self.get_db_schema,
            "get_table_info": self.get_table_info,
            "get_table_sample": self.get_table_sample,
            "get_column_values": self.get_column_values,
            "run_sql_query": self.run_sql_query,
        }


def create_database_tools(username: str, connection_name: str) -> DatabaseTools:
    """
    Factory function to create DatabaseTools.

    Args:
        username: The username for database access.
        connection_name: The name of the database connection.

    Returns:
        Configured DatabaseTools instance.
    """
    return DatabaseTools(username, connection_name)
