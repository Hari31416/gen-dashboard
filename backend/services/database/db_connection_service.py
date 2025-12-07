"""
Database Connection Service

This module handles:
- Database connection validation using SQLAlchemy
- Fetching table names and schemas
- Password encryption/decryption for secure storage
"""

from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from cryptography.fernet import Fernet
import os
from utilities import create_simple_logger, get_or_generate_key

logger = create_simple_logger(__name__)

# Encryption key management
# In production, this should be stored securely (e.g., environment variable, key vault)
ENCRYPTION_KEY = get_or_generate_key(
    env_var="DB_PASSWORD_ENCRYPTION_KEY",
    key_file=".env.key",  # Optional: Try loading from file
    auto_generate=True,  # Auto-generate in development
)

cipher_suite = Fernet(
    ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY
)


def encrypt_password(password: str) -> str:
    """
    Encrypt a password for secure storage.

    Args:
        password: Plain text password

    Returns:
        Encrypted password as string
    """
    try:
        encrypted = cipher_suite.encrypt(password.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Error encrypting password: {e}")
        raise


def decrypt_password(encrypted_password: str) -> str:
    """
    Decrypt an encrypted password.

    Args:
        encrypted_password: Encrypted password string

    Returns:
        Decrypted plain text password
    """
    try:
        if not encrypted_password:
            raise ValueError("Encrypted password is empty")
        decrypted = cipher_suite.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Error decrypting password: {e}")
        logger.debug(
            f"Encrypted password length: {len(encrypted_password) if encrypted_password else 0}"
        )
        raise ValueError(f"Password decryption failed: {str(e)}")


def build_connection_string(
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str,
    db_type: str = "mysql",
    **kwargs,  # ignored
) -> str:
    """
    Build a SQLAlchemy connection string.

    Args:
        host: Database host
        port: Database port
        username: Database username
        password: Database password
        database_name: Database name
        db_type: Database type (postgresql, mysql, etc.)

    Returns:
        SQLAlchemy connection string
    """
    if db_type.lower() in ["postgresql", "postgres"]:
        return (
            f"postgresql+psycopg2://{username}:{password}@{host}:{port}/{database_name}"
        )
    elif db_type.lower() == "mysql":
        return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}"
    elif db_type.lower() == "sqlite":
        return f"sqlite:///{database_name}"
    elif db_type.lower() == "mariadb":
        return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database_name}"
    else:
        raise ValueError(f"Unsupported database type: {db_type}")


def validate_connection(
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str,
    db_type: str = "mysql",
) -> Dict[str, Any]:
    """
    Validate database connection details.

    Args:
        host: Database host
        port: Database port
        username: Database username
        password: Database password (plain text)
        database_name: Database name
        db_type: Database type

    Returns:
        Dictionary with validation result
    """
    try:
        connection_string = build_connection_string(
            host, port, username, password, database_name, db_type
        )
        engine = create_engine(connection_string, pool_pre_ping=True)

        # Test connection
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        logger.info(
            f"Successfully validated connection to {database_name} at {host}:{port}"
        )
        return {
            "valid": True,
            "message": "Connection successful",
            "database_name": database_name,
        }
    except SQLAlchemyError as e:
        logger.error(f"Database connection validation failed: {e}")
        return {
            "valid": False,
            "message": f"Connection failed: {str(e)}",
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"Unexpected error during connection validation: {e}")
        return {
            "valid": False,
            "message": f"Unexpected error: {str(e)}",
            "error": str(e),
        }


def fetch_table_schemas(
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str,
    db_type: str = "mysql",
    tables_to_fetch: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Fetch all table names and their schemas from the database.

    Args:
        host: Database host
        port: Database port
        username: Database username
        password: Database password (plain text)
        database_name: Database name
        db_type: Database type

    Returns:
        Dictionary with tables and their schemas
    """
    try:
        connection_string = build_connection_string(
            host, port, username, password, database_name, db_type
        )
        engine = create_engine(connection_string, pool_pre_ping=True)
        inspector = inspect(engine)

        tables = []
        table_names = inspector.get_table_names()
        if tables_to_fetch:
            logger.info(f"Filtering tables to fetch: {tables_to_fetch}")
            table_names = [
                t for t in table_names if t in tables_to_fetch
            ]  # Filter tables

        for table_name in table_names:
            columns = []
            primary_keys = inspector.get_pk_constraint(table_name).get(
                "constrained_columns", []
            )

            for column in inspector.get_columns(table_name):
                columns.append(
                    {
                        "column_name": column["name"],
                        "data_type": str(column["type"]),
                        "is_nullable": column["nullable"],
                        "is_primary_key": column["name"] in primary_keys,
                        "column_description": None,
                    }
                )

            tables.append(
                {
                    "table_name": table_name,
                    "columns": columns,
                    "table_description": None,
                }
            )

        logger.info(f"Successfully fetched {len(tables)} tables from {database_name}")

        return {
            "database_name": database_name,
            "tables": tables,
            "table_count": len(tables),
        }
    except SQLAlchemyError as e:
        logger.error(f"Error fetching table schemas: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching table schemas: {e}")
        raise


def fetch_table_relationships(
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str,
    db_type: str = "mysql",
) -> List[Dict[str, Any]]:
    """
    Fetch foreign key relationships between tables.

    Args:
        host: Database host
        port: Database port
        username: Database username
        password: Database password (plain text)
        database_name: Database name
        db_type: Database type

    Returns:
        List of relationship dictionaries
    """
    try:
        connection_string = build_connection_string(
            host, port, username, password, database_name, db_type
        )
        engine = create_engine(connection_string, pool_pre_ping=True)
        inspector = inspect(engine)

        relationships = []
        table_names = inspector.get_table_names()

        for table_name in table_names:
            foreign_keys = inspector.get_foreign_keys(table_name)

            for fk in foreign_keys:
                relationship = {
                    "table_name": table_name,
                    "related_table_name": fk["referred_table"],
                    "foreign_key": (
                        fk["constrained_columns"][0]
                        if fk["constrained_columns"]
                        else None
                    ),
                    "primary_key": (
                        fk["referred_columns"][0] if fk["referred_columns"] else None
                    ),
                    "relationship_type": "many-to-one",  # Default, can be enhanced
                    "relationship_description": None,
                }
                relationships.append(relationship)

        logger.info(
            f"Successfully fetched {len(relationships)} relationships from {database_name}"
        )
        return relationships
    except SQLAlchemyError as e:
        logger.error(f"Error fetching table relationships: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error fetching table relationships: {e}")
        raise


def test_query_execution(
    host: str,
    port: int,
    username: str,
    password: str,
    database_name: str,
    query: str,
    db_type: str = "mysql",
) -> Dict[str, Any]:
    """
    Execute a test query on the database.

    Args:
        host: Database host
        port: Database port
        username: Database username
        password: Database password (plain text)
        database_name: Database name
        query: SQL query to execute
        db_type: Database type

    Returns:
        Dictionary with query results
    """
    try:
        connection_string = build_connection_string(
            host, port, username, password, database_name, db_type
        )
        engine = create_engine(connection_string, pool_pre_ping=True)

        with engine.connect() as connection:
            result = connection.execute(text(query))
            rows = result.fetchall()
            columns = result.keys()

            return {
                "success": True,
                "columns": list(columns),
                "rows": [dict(zip(columns, row)) for row in rows],
                "row_count": len(rows),
            }
    except SQLAlchemyError as e:
        logger.error(f"Error executing query: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error executing query: {e}")
        return {"success": False, "error": str(e)}


def run_query_and_return_df(
    connection_string: str,
    query: str,
):
    """
    Execute a query and return the results as a pandas DataFrame.

    Args:
        host: Database host
        port: Database port
        username: Database username
        password: Database password (plain text)
        database_name: Database name
        query: SQL query to execute
        db_type: Database type
    Returns:
        pandas DataFrame with query results
    """
    import pandas as pd

    try:
        engine = create_engine(connection_string, pool_pre_ping=True)

        df = pd.read_sql(sql=text(query), con=engine)
        return df
    except SQLAlchemyError as e:
        logger.error(f"Error executing query and returning DataFrame: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error executing query and returning DataFrame: {e}")
        raise


def dry_run_sql_query(
    connection_string: str,
    query: str,
) -> Dict[str, Any]:
    """
    Perform a dry run of the SQL query to check for syntax errors without executing it.

    Args:
        connection_string: SQLAlchemy connection string
        query: SQL query to dry run
    Returns:
        Dictionary with dry run result
    """
    try:
        engine = create_engine(connection_string, pool_pre_ping=True)

        with engine.connect() as connection:
            connection.execute(text(f"EXPLAIN {query}"))

        return {"success": True, "message": "Query syntax is valid."}
    except SQLAlchemyError as e:
        logger.error(f"Error during dry run of SQL query: {e}")
        return {"success": False, "error": str(e)}
    except Exception as e:
        logger.error(f"Unexpected error during dry run of SQL query: {e}")
        return {"success": False, "error": str(e)}
