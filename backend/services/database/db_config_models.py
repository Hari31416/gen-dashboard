"""
Database Configuration Models

This module manages MongoDB collections for:
- <username>_db_config: Database connection configurations
- <username>_db_info: Database schema information
- <username>_db_relationships: Table relationships
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from env import MONGO_URI
from pydantic import BaseModel, Field
from pymongo import MongoClient
from pymongo.collection import Collection
from services.database.db_connection_service import decrypt_password, encrypt_password
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


def get_db_name(user_name: str) -> str:
    # Sanitize user_name to be safe for DB name
    clean_user = re.sub(r"[^a-zA-Z0-9_]", "_", user_name)
    return f"user_{clean_user}"


def get_mongo_client() -> MongoClient:
    """Get MongoDB client connection."""
    try:
        client = MongoClient(
            MONGO_URI, authSource="admin", serverSelectionTimeoutMS=5000
        )
        client.admin.command("ping")
        return client
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


def get_user_db_config_collection(username: str) -> Collection:
    """
    Get the database configuration collection for a user.

    Args:
        username: Username

    Returns:
        MongoDB collection for db_config
    """
    client = get_mongo_client()
    db = client[username]
    return db["db_config"]


def get_user_db_info_collection(username: str) -> Collection:
    """
    Get the database info collection for a user.

    Args:
        username: Username

    Returns:
        MongoDB collection for db_info
    """
    client = get_mongo_client()
    db = client[username]
    return db["db_info"]


def get_user_db_relationships_collection(username: str) -> Collection:
    """
    Get the database relationships collection for a user.

    Args:
        username: Username

    Returns:
        MongoDB collection for db_relationships
    """
    client = get_mongo_client()
    db = client[username]
    return db["db_relationships"]


def get_user_db_relationships_updates_collection(username: str) -> Collection:
    """
    Get the database relationships updates collection for a user.
    This stores user-modified ERD relationships.

    Args:
        username: Username

    Returns:
        MongoDB collection for db_relationships_updates
    """
    client = get_mongo_client()
    db = client[username]
    return db["db_relationships_updates"]


# ============================================================================
# DB Config Operations
# ============================================================================


def save_db_config(
    username: str,
    host: str,
    port: int,
    db_username: str,
    password: str,
    database_name: str,
    connection_name: str,
    db_type: str = "mysql",
    db_description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Save database configuration for a user.

    Args:
        username: User's username
        host: Database host
        port: Database port
        db_username: Database username
        password: Database password (will be encrypted)
        database_name: Database name
        connection_name: Friendly name for the connection
        db_type: Database type (postgresql, mysql, etc.)
        db_description: Optional description of the database

    Returns:
        Saved configuration document
    """
    try:
        collection = get_user_db_config_collection(username)

        # Encrypt password before storing
        encrypted_password = encrypt_password(password)

        config = {
            "host": host,
            "port": port,
            "username": db_username,
            "password": encrypted_password,
            "database_name": database_name,
            "connection_name": connection_name,
            "db_type": db_type,
            "db_description": db_description,
            "fetched_at": datetime.utcnow(),
        }

        # Check if connection with same name exists
        existing = collection.find_one({"connection_name": connection_name})
        if existing:
            # Update existing
            collection.update_one(
                {"connection_name": connection_name}, {"$set": config}
            )
            logger.info(f"Updated DB config '{connection_name}' for user {username}")
        else:
            # Insert new
            result = collection.insert_one(config)
            config["_id"] = str(result.inserted_id)
            logger.info(f"Saved new DB config '{connection_name}' for user {username}")

        # Return config without password
        return_config = config.copy()
        return_config.pop("password", None)
        if "_id" in return_config:
            return_config["_id"] = str(return_config["_id"])

        return return_config
    except Exception as e:
        logger.error(f"Error saving DB config: {e}")
        raise


def get_db_config(username: str, connection_name: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific database configuration.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        Configuration document (with decrypted password)
    """
    try:
        collection = get_user_db_config_collection(username)
        config = collection.find_one({"connection_name": connection_name})

        if config:
            config["_id"] = str(config["_id"])
            # Decrypt password
            try:
                config["password"] = decrypt_password(config["password"])
            except Exception as decrypt_error:
                logger.error(
                    f"Error decrypting password for connection '{connection_name}': {decrypt_error}"
                )
                # If decryption fails, the password might already be in plain text or corrupted
                # Return None to indicate config retrieval failed
                raise ValueError(
                    f"Failed to decrypt password for connection '{connection_name}'. The connection may need to be reconfigured."
                )
            return config
        return None
    except Exception as e:
        logger.error(f"Error getting DB config: {e}")
        raise


def list_db_configs(
    username: str, ignore_user_data_db: bool = False
) -> List[Dict[str, Any]]:
    """
    List all database configurations for a user.

    Args:
        username: User's username

    Returns:
        List of configuration documents (without passwords)
    """
    try:
        collection = get_user_db_config_collection(username)
        configs = list(collection.find())
        user_db_name = get_db_name(username)
        # Remove passwords and convert ObjectId to string
        for config in configs:
            config["_id"] = str(config["_id"])
            config.pop("password", None)
            if ignore_user_data_db and config.get("database_name") == user_db_name:
                configs.remove(config)

        return configs
    except Exception as e:
        logger.error(f"Error listing DB configs: {e}")
        raise


def delete_db_config(username: str, connection_name: str) -> bool:
    """
    Delete a database configuration.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        True if deleted, False if not found
    """
    try:
        collection = get_user_db_config_collection(username)
        result = collection.delete_one({"connection_name": connection_name})

        if result.deleted_count > 0:
            logger.info(f"Deleted DB config '{connection_name}' for user {username}")

            # Also delete associated db_info and relationships
            delete_db_info(username, connection_name)
            delete_db_relationships(username, connection_name)
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting DB config: {e}")
        raise


# ============================================================================
# DB Info Operations
# ============================================================================


class ColumnModel(BaseModel):
    column_name: str = Field(..., description="Name of the column")
    data_type: str = Field(..., description="Data type of the column")
    is_nullable: bool = Field(..., description="Whether the column is nullable")
    is_primary_key: bool = Field(..., description="Whether the column is a primary key")
    column_description: Optional[str] = Field(
        None, description="Optional description of the column"
    )


class TablesModel(BaseModel):
    table_name: str = Field(..., description="Name of the table")
    table_description: Optional[str] = Field(
        None, description="Optional description of the table"
    )
    columns: List[ColumnModel] = Field(..., description="List of columns in the table")


class DBInfoModel(BaseModel):
    database_name: str = Field(..., description="Database name")
    connection_name: str = Field(..., description="Connection name")
    tables: List[TablesModel] = Field(..., description="List of table schemas")
    fetched_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the DB info was fetched",
    )


def save_db_info(
    username: str,
    connection_name: str,
    database_name: str,
    tables: List[TablesModel],
) -> DBInfoModel:
    """
    Save database schema information.

    Args:
        username: User's username
        connection_name: Connection name
        database_name: Database name
        tables: List of table schemas

    Returns:
        Saved info document
    """
    try:
        collection = get_user_db_info_collection(username)

        info = {
            "connection_name": connection_name,
            "database_name": database_name,
            "tables": tables,
            "fetched_at": datetime.utcnow(),
        }

        # Update or insert
        existing = collection.find_one({"connection_name": connection_name})
        if existing:
            collection.update_one({"connection_name": connection_name}, {"$set": info})
            logger.info(f"Updated DB info for '{connection_name}' (user: {username})")
        else:
            result = collection.insert_one(info)
            info["_id"] = str(result.inserted_id)
            logger.info(f"Saved new DB info for '{connection_name}' (user: {username})")

        if "_id" in info:
            info["_id"] = str(info["_id"])

        return info
    except Exception as e:
        logger.error(f"Error saving DB info: {e}")
        raise


def get_db_info(username: str, connection_name: str) -> Optional[DBInfoModel]:
    """
    Get database schema information.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        Info document
    """
    try:
        collection = get_user_db_info_collection(username)
        info = collection.find_one({"connection_name": connection_name})

        if info:
            info["_id"] = str(info["_id"])
            return info
        return None
    except Exception as e:
        logger.error(f"Error getting DB info: {e}")
        raise


def list_db_infos(username: str) -> List[Dict[str, Any]]:
    """
    List all database schema information for a user.

    Args:
        username: User's username

    Returns:
        List of info documents
    """
    try:
        collection = get_user_db_info_collection(username)
        infos = list(collection.find())

        for info in infos:
            info["_id"] = str(info["_id"])

        return infos
    except Exception as e:
        logger.error(f"Error listing DB infos: {e}")
        raise


def delete_db_info(username: str, connection_name: str) -> bool:
    """
    Delete database schema information.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        True if deleted, False if not found
    """
    try:
        collection = get_user_db_info_collection(username)
        result = collection.delete_one({"connection_name": connection_name})

        if result.deleted_count > 0:
            logger.info(f"Deleted DB info for '{connection_name}' (user: {username})")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting DB info: {e}")
        raise


# ============================================================================
# DB Relationships Operations
# ============================================================================


class RelationshipModel(BaseModel):
    table_name: str = Field(..., description="Source table name")
    primary_key: str = Field(..., description="Source column name")
    related_table_name: str = Field(..., description="Target table name")
    foreign_key: str = Field(..., description="Target column name")
    relationship_type: str = Field(
        ..., description="Type of relationship (e.g., one-to-many, many-to-many)"
    )
    relationship_description: Optional[str] = Field(
        None, description="Optional description of the relationship"
    )


def save_db_relationships(
    username: str,
    connection_name: str,
    database_name: str,
    relationships: List[RelationshipModel],
) -> Dict[str, Any]:
    """
    Save database table relationships.

    Args:
        username: User's username
        connection_name: Connection name
        database_name: Database name
        relationships: List of relationship dictionaries

    Returns:
        Saved relationships document
    """
    try:
        collection = get_user_db_relationships_collection(username)

        rel_doc = {
            "connection_name": connection_name,
            "database_name": database_name,
            "relationships": relationships,
            "fetched_at": datetime.utcnow(),
        }

        # Update or insert
        existing = collection.find_one({"connection_name": connection_name})
        if existing:
            collection.update_one(
                {"connection_name": connection_name}, {"$set": rel_doc}
            )
            logger.info(
                f"Updated DB relationships for '{connection_name}' (user: {username})"
            )
        else:
            result = collection.insert_one(rel_doc)
            rel_doc["_id"] = str(result.inserted_id)
            logger.info(
                f"Saved new DB relationships for '{connection_name}' (user: {username})"
            )

        if "_id" in rel_doc:
            rel_doc["_id"] = str(rel_doc["_id"])

        return rel_doc
    except Exception as e:
        logger.error(f"Error saving DB relationships: {e}")
        raise


def get_db_relationships(
    username: str, connection_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get database table relationships.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        Relationships document
    """
    try:
        collection = get_user_db_relationships_collection(username)
        rel_doc = collection.find_one({"connection_name": connection_name})

        if rel_doc:
            rel_doc["_id"] = str(rel_doc["_id"])
            if len(rel_doc.get("relationships", [])) == 0:
                logger.info(
                    f"No relationships found for '{connection_name}' (user: {username})"
                )
                return None
            return rel_doc
        return None
    except Exception as e:
        logger.error(f"Error getting DB relationships: {e}")
        raise


def delete_db_relationships(username: str, connection_name: str) -> bool:
    """
    Delete database table relationships.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        True if deleted, False if not found
    """
    try:
        collection = get_user_db_relationships_collection(username)
        result = collection.delete_one({"connection_name": connection_name})

        if result.deleted_count > 0:
            logger.info(
                f"Deleted DB relationships for '{connection_name}' (user: {username})"
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting DB relationships: {e}")
        raise


# ============================================================================
# DB Relationships Updates Operations (User-Modified ERD)
# ============================================================================


def save_db_relationships_updates(
    username: str,
    connection_name: str,
    database_name: str,
    relationships: List[Dict[str, Any]],
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Save user-modified database table relationships.
    This allows users to customize the ERD by adding, removing, or modifying relationships.

    Args:
        username: User's username
        connection_name: Connection name
        database_name: Database name
        relationships: List of updated relationship dictionaries
        description: Optional description of the changes

    Returns:
        Saved relationships updates document
    """
    try:
        collection = get_user_db_relationships_updates_collection(username)

        update_doc = {
            "connection_name": connection_name,
            "database_name": database_name,
            "relationships": relationships,
            "description": description,
            "updated_at": datetime.utcnow(),
        }

        # Update or insert
        existing = collection.find_one({"connection_name": connection_name})
        if existing:
            collection.update_one(
                {"connection_name": connection_name}, {"$set": update_doc}
            )
            logger.info(
                f"Updated ERD modifications for '{connection_name}' (user: {username})"
            )
        else:
            result = collection.insert_one(update_doc)
            update_doc["_id"] = str(result.inserted_id)
            logger.info(
                f"Saved new ERD modifications for '{connection_name}' (user: {username})"
            )

        if "_id" in update_doc:
            update_doc["_id"] = str(update_doc["_id"])

        return update_doc
    except Exception as e:
        logger.error(f"Error saving DB relationships updates: {e}")
        raise


def get_db_relationships_updates(
    username: str, connection_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get user-modified database table relationships.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        Relationships updates document or None if not found
    """
    try:
        collection = get_user_db_relationships_updates_collection(username)
        update_doc = collection.find_one({"connection_name": connection_name})

        if update_doc:
            update_doc["_id"] = str(update_doc["_id"])
            return update_doc
        return None
    except Exception as e:
        logger.error(f"Error getting DB relationships updates: {e}")
        raise


def list_db_relationships_updates(username: str) -> List[Dict[str, Any]]:
    """
    List all user-modified database relationships for a user.

    Args:
        username: User's username

    Returns:
        List of relationships updates documents
    """
    try:
        collection = get_user_db_relationships_updates_collection(username)
        updates = list(collection.find())

        for update in updates:
            update["_id"] = str(update["_id"])

        return updates
    except Exception as e:
        logger.error(f"Error listing DB relationships updates: {e}")
        raise


def delete_db_relationships_updates(username: str, connection_name: str) -> bool:
    """
    Delete user-modified database table relationships.
    This reverts to using the original relationships from db_relationships.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        True if deleted, False if not found
    """
    try:
        collection = get_user_db_relationships_updates_collection(username)
        result = collection.delete_one({"connection_name": connection_name})

        if result.deleted_count > 0:
            logger.info(
                f"Deleted ERD modifications for '{connection_name}' (user: {username})"
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting DB relationships updates: {e}")
        raise


def get_effective_relationships(
    username: str, connection_name: str
) -> Optional[Dict[str, Any]]:
    """
    Get the effective relationships for a connection.
    Returns user-modified relationships if they exist, otherwise returns default relationships.

    Args:
        username: User's username
        connection_name: Connection name

    Returns:
        Effective relationships document with a 'source' field indicating origin
    """
    try:
        # First try to get user modifications
        updates = get_db_relationships_updates(username, connection_name)

        if updates:
            updates["source"] = "user_modified"
            return updates

        # Fall back to default relationships
        default = get_db_relationships(username, connection_name)

        if default:
            default["source"] = "default"
            return default

        return None
    except Exception as e:
        logger.error(f"Error getting effective relationships: {e}")
        raise
