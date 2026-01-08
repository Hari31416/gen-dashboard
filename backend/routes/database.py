"""
Database Routes

Endpoints for managing database connections and fetching schemas.
All endpoints require authentication.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from routes.auth import User, get_current_active_user
from services.database.db_config_models import (
    delete_db_config,
    delete_db_relationships_updates,
    get_db_config,
    get_db_info,
    get_db_relationships,
    get_db_relationships_updates,
    get_effective_relationships,
    list_db_configs,
    list_db_infos,
    list_db_relationships_updates,
    save_db_config,
    save_db_info,
    save_db_relationships,
    save_db_relationships_updates,
)
from services.database.db_connection_service import (
    fetch_table_relationships,
    fetch_table_schemas,
    test_query_execution,
    validate_connection,
)
from utilities import create_simple_logger

logger = create_simple_logger(__name__)

router = APIRouter(prefix="/database", tags=["database"])


# ============================================================================
# Request/Response Models
# ============================================================================


class DatabaseConnectionRequest(BaseModel):
    """Request model for database connection"""

    host: str = Field(..., description="Database host address")
    port: int = Field(..., description="Database port", gt=0, lt=65536)
    username: str = Field(..., description="Database username")
    password: str = Field(..., description="Database password")
    database_name: str = Field(..., description="Database name")
    connection_name: str = Field(..., description="Friendly name for this connection")
    db_type: str = Field(
        default="mysql",
        description="Database type (mysql, postgresql, sqlite, mariadb)",
    )
    db_description: Optional[str] = Field(
        None, description="Optional description of the database"
    )


class DatabaseConnectionValidateRequest(BaseModel):
    """Request model for validating database connection"""

    host: str
    port: int = Field(gt=0, lt=65536)
    username: str
    password: str
    database_name: str
    db_type: str = "mysql"


class DatabaseConnectionResponse(BaseModel):
    """Response model for database connection"""

    connection_name: str
    host: str
    port: int
    username: str
    database_name: str
    db_type: str
    fetched_at: str


class DatabaseSchemaResponse(BaseModel):
    """Response model for database schema"""

    connection_name: str
    database_name: str
    tables: List[dict]
    table_count: int
    fetched_at: str


class DatabaseRelationshipsResponse(BaseModel):
    """Response model for database relationships"""

    connection_name: str
    database_name: str
    relationships: List[dict]
    relationship_count: int
    fetched_at: str


class TestQueryRequest(BaseModel):
    """Request model for testing queries"""

    connection_name: str
    query: str = Field(..., description="SQL query to execute")


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/validate")
async def validate_database_connection(
    request: DatabaseConnectionValidateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Validate database connection details without saving.

    This endpoint tests if the provided database credentials are valid
    and the database is accessible.
    """
    try:
        result = validate_connection(
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            database_name=request.database_name,
            db_type=request.db_type,
        )

        if not result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=result["message"]
            )

        logger.info(
            f"User {current_user.username} validated connection to {request.database_name}"
        )
        return {
            "valid": True,
            "message": result["message"],
            "database_name": result["database_name"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate connection: {str(e)}",
        )


@router.post("/connect", status_code=status.HTTP_201_CREATED)
async def connect_to_database(
    request: DatabaseConnectionRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Connect to a database and save the configuration.

    This endpoint:
    1. Validates the connection
    2. Fetches table schemas
    3. Fetches table relationships
    4. Saves everything to MongoDB
    """
    try:
        # Step 1: Validate connection
        validation_result = validate_connection(
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            database_name=request.database_name,
            db_type=request.db_type,
        )

        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_result["message"],
            )

        # Step 2: Save configuration
        config = save_db_config(
            username=current_user.username,
            host=request.host,
            port=request.port,
            db_username=request.username,
            password=request.password,
            database_name=request.database_name,
            connection_name=request.connection_name,
            db_type=request.db_type,
            db_description=request.db_description,
        )

        # Step 3: Fetch and save table schemas
        schema_data = fetch_table_schemas(
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            database_name=request.database_name,
            db_type=request.db_type,
        )

        db_info = save_db_info(
            username=current_user.username,
            connection_name=request.connection_name,
            database_name=request.database_name,
            tables=schema_data["tables"],
        )

        # Step 4: Fetch and save relationships
        relationships = fetch_table_relationships(
            host=request.host,
            port=request.port,
            username=request.username,
            password=request.password,
            database_name=request.database_name,
            db_type=request.db_type,
        )

        db_relationships = save_db_relationships(
            username=current_user.username,
            connection_name=request.connection_name,
            database_name=request.database_name,
            relationships=relationships,
        )

        logger.info(
            f"User {current_user.username} connected to database '{request.connection_name}' "
            f"with {schema_data['table_count']} tables and {len(relationships)} relationships"
        )

        return {
            "message": "Successfully connected to database and fetched schema",
            "connection": config,
            "schema": {
                "table_count": schema_data["table_count"],
                "tables": schema_data["tables"],
            },
            "relationships": {
                "relationship_count": len(relationships),
                "relationships": relationships,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to connect to database: {str(e)}",
        )


@router.get("/connections")
async def list_connections(current_user: User = Depends(get_current_active_user)):
    """
    List all database connections for the current user.
    """
    try:
        configs = list_db_configs(current_user.username, ignore_user_data_db=True)
        logger.info(
            f"User {current_user.username} listed {len(configs)} database connections"
        )
        return {"connections": configs, "count": len(configs)}
    except Exception as e:
        logger.error(f"Error listing connections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list connections: {str(e)}",
        )


@router.get("/connections/{connection_name}")
async def get_connection(
    connection_name: str, current_user: User = Depends(get_current_active_user)
):
    """
    Get details of a specific database connection (without password).
    """
    try:
        config = get_db_config(current_user.username, connection_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection '{connection_name}' not found",
            )

        # Remove password from response
        config.pop("password", None)

        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get connection: {str(e)}",
        )


@router.delete("/connections/{connection_name}")
async def delete_connection(
    connection_name: str, current_user: User = Depends(get_current_active_user)
):
    """
    Delete a database connection and all associated data.
    """
    try:
        success = delete_db_config(current_user.username, connection_name)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection '{connection_name}' not found",
            )

        logger.info(
            f"User {current_user.username} deleted connection '{connection_name}'"
        )
        return {"message": f"Successfully deleted connection '{connection_name}'"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting connection: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete connection: {str(e)}",
        )


@router.get("/schema/{connection_name}")
async def get_database_schema(
    connection_name: str, current_user: User = Depends(get_current_active_user)
):
    """
    Get the schema (tables and columns) for a specific database connection.
    """
    try:
        db_info = get_db_info(current_user.username, connection_name)

        if not db_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schema for connection '{connection_name}' not found",
            )

        return {
            "connection_name": connection_name,
            "database_name": db_info["database_name"],
            "tables": db_info["tables"],
            "table_count": len(db_info["tables"]),
            "fetched_at": (
                db_info["fetched_at"].isoformat()
                if hasattr(db_info["fetched_at"], "isoformat")
                else str(db_info["fetched_at"])
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting database schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database schema: {str(e)}",
        )


@router.get("/relationships/{connection_name}")
async def get_database_relationships(
    connection_name: str, current_user: User = Depends(get_current_active_user)
):
    """
    Get table relationships for a specific database connection.
    """
    try:
        relationships = get_db_relationships(current_user.username, connection_name)

        if not relationships:
            logger.warning(
                f"Relationships for connection '{connection_name}' not found"
            )
            relationships = {
                "database_name": "",
                "relationships": [],
                "fetched_at": None,
            }

        return {
            "connection_name": connection_name,
            "database_name": relationships["database_name"],
            "relationships": relationships["relationships"],
            "relationship_count": len(relationships["relationships"]),
            "fetched_at": (
                relationships["fetched_at"].isoformat()
                if hasattr(relationships["fetched_at"], "isoformat")
                else str(relationships["fetched_at"])
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting database relationships: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get database relationships: {str(e)}",
        )


@router.post("/refresh/{connection_name}")
async def refresh_database_schema(
    connection_name: str, current_user: User = Depends(get_current_active_user)
):
    """
    Refresh the schema and relationships for a database connection.

    This re-fetches the table schemas and relationships from the database.
    """
    try:
        # Get the stored config (with decrypted password)
        config = get_db_config(current_user.username, connection_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection '{connection_name}' not found",
            )

        # Fetch fresh schema data
        schema_data = fetch_table_schemas(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            database_name=config["database_name"],
            db_type=config.get("db_type", "mysql"),
        )

        # Save updated schema
        save_db_info(
            username=current_user.username,
            connection_name=connection_name,
            database_name=config["database_name"],
            tables=schema_data["tables"],
        )

        # Fetch fresh relationships
        relationships = fetch_table_relationships(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            database_name=config["database_name"],
            db_type=config.get("db_type", "mysql"),
        )

        # Save updated relationships
        save_db_relationships(
            username=current_user.username,
            connection_name=connection_name,
            database_name=config["database_name"],
            relationships=relationships,
        )

        logger.info(
            f"User {current_user.username} refreshed schema for '{connection_name}' "
            f"with {schema_data['table_count']} tables and {len(relationships)} relationships"
        )

        return {
            "message": "Successfully refreshed database schema and relationships",
            "table_count": schema_data["table_count"],
            "relationship_count": len(relationships),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing database schema: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh database schema: {str(e)}",
        )


@router.post("/test-query")
async def execute_test_query(
    request: TestQueryRequest, current_user: User = Depends(get_current_active_user)
):
    """
    Execute a test SQL query on a database connection.

    This is useful for testing queries before using them in production.
    """
    try:
        # Get the stored config
        config = get_db_config(current_user.username, request.connection_name)

        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection '{request.connection_name}' not found",
            )

        # Execute the query
        result = test_query_execution(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            database_name=config["database_name"],
            query=request.query,
            db_type=config.get("db_type", "mysql"),
        )

        if not result["success"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Query execution failed: {result.get('error', 'Unknown error')}",
            )

        logger.info(
            f"User {current_user.username} executed test query on '{request.connection_name}' "
            f"returning {result['row_count']} rows"
        )

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing test query: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute test query: {str(e)}",
        )


# ============================================================================
# ERD Updates Endpoints (User-Modified Relationships)
# ============================================================================


class RelationshipUpdateRequest(BaseModel):
    """Request model for updating ERD relationships"""

    connection_name: str = Field(..., description="Connection name")
    relationships: List[dict] = Field(..., description="Updated list of relationships")
    description: Optional[str] = Field(None, description="Description of changes")


@router.post("/relationships/updates", status_code=status.HTTP_201_CREATED)
async def save_erd_updates(
    request: RelationshipUpdateRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    Save user-modified ERD relationships.

    This endpoint allows users to customize the ERD by adding, removing,
    or modifying relationships beyond what was automatically detected.
    """
    try:
        # Verify the connection exists
        config = get_db_config(current_user.username, request.connection_name)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Connection '{request.connection_name}' not found",
            )

        # Save the updates
        result = save_db_relationships_updates(
            username=current_user.username,
            connection_name=request.connection_name,
            database_name=config["database_name"],
            relationships=request.relationships,
            description=request.description,
        )

        logger.info(
            f"User {current_user.username} saved ERD updates for '{request.connection_name}' "
            f"with {len(request.relationships)} relationships"
        )

        return {
            "message": "Successfully saved ERD updates",
            "connection_name": request.connection_name,
            "relationship_count": len(request.relationships),
            "updated_at": (
                result["updated_at"].isoformat()
                if hasattr(result["updated_at"], "isoformat")
                else str(result["updated_at"])
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving ERD updates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save ERD updates: {str(e)}",
        )


@router.get("/relationships/updates/{connection_name}")
async def get_erd_updates(
    connection_name: str, current_user: User = Depends(get_current_active_user)
):
    """
    Get user-modified ERD relationships for a specific connection.

    Returns None if no custom modifications exist.
    """
    try:
        updates = get_db_relationships_updates(current_user.username, connection_name)

        if not updates:
            return {
                "connection_name": connection_name,
                "has_updates": False,
                "message": "No custom ERD modifications found",
            }

        return {
            "connection_name": connection_name,
            "has_updates": True,
            "database_name": updates["database_name"],
            "relationships": updates["relationships"],
            "relationship_count": len(updates["relationships"]),
            "description": updates.get("description"),
            "updated_at": (
                updates["updated_at"].isoformat()
                if hasattr(updates["updated_at"], "isoformat")
                else str(updates["updated_at"])
            ),
        }
    except Exception as e:
        logger.error(f"Error getting ERD updates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get ERD updates: {str(e)}",
        )


@router.get("/relationships/effective/{connection_name}")
async def get_effective_erd(
    connection_name: str, current_user: User = Depends(get_current_active_user)
):
    """
    Get the effective ERD relationships for a connection.

    Returns user-modified relationships if they exist, otherwise returns
    the default auto-detected relationships.
    """
    try:
        effective = get_effective_relationships(current_user.username, connection_name)

        if not effective:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No relationships found for connection '{connection_name}'",
            )

        return {
            "connection_name": connection_name,
            "database_name": effective["database_name"],
            "relationships": effective["relationships"],
            "relationship_count": len(effective["relationships"]),
            "source": effective["source"],  # 'user_modified' or 'default'
            "fetched_at": (
                effective.get("updated_at", effective.get("fetched_at")).isoformat()
                if hasattr(
                    effective.get("updated_at", effective.get("fetched_at")),
                    "isoformat",
                )
                else str(effective.get("updated_at", effective.get("fetched_at")))
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting effective relationships: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get effective relationships: {str(e)}",
        )


@router.delete("/relationships/updates/{connection_name}")
async def delete_erd_updates(
    connection_name: str, current_user: User = Depends(get_current_active_user)
):
    """
    Delete user-modified ERD relationships.

    This reverts to using the default auto-detected relationships.
    """
    try:
        success = delete_db_relationships_updates(
            current_user.username, connection_name
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No ERD modifications found for connection '{connection_name}'",
            )

        logger.info(
            f"User {current_user.username} deleted ERD updates for '{connection_name}'"
        )
        return {
            "message": f"Successfully deleted ERD modifications for '{connection_name}'",
            "connection_name": connection_name,
            "reverted_to": "default",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting ERD updates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete ERD updates: {str(e)}",
        )


@router.get("/relationships/updates")
async def list_all_erd_updates(current_user: User = Depends(get_current_active_user)):
    """
    List all ERD modifications for the current user across all connections.
    """
    try:
        updates = list_db_relationships_updates(current_user.username)

        logger.info(
            f"User {current_user.username} listed {len(updates)} ERD modifications"
        )

        return {
            "updates": updates,
            "count": len(updates),
        }
    except Exception as e:
        logger.error(f"Error listing ERD updates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list ERD updates: {str(e)}",
        )
