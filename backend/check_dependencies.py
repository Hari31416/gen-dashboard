"""
Dependency health check script for Gen-BI backend.
Checks if all required services are running before starting the application.
"""

from dotenv import load_dotenv
import os
import sys
from typing import Tuple
from pymongo import MongoClient
from sqlalchemy import create_engine, text
from utilities.utils import create_simple_logger
from env import MARIADB_URI

logger = create_simple_logger(__name__)

load_dotenv()


def check_mongodb_connection() -> Tuple[bool, str]:
    """
    Check MongoDB connection status.

    Returns:
        Tuple[bool, str]: (is_alive, message)
    """
    try:
        mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        mongo_db = os.environ.get("MONGO_DB_NAME", "gen_bi")

        # Parse connection info for logging
        connection_info = {
            "uri": mongo_uri,
            "database": mongo_db,
        }

        # Create MongoDB client and test connection
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

        # Test the connection
        client.admin.command("ping")

        # Check if database exists
        db = client[mongo_db]

        message = f"MongoDB connection is alive at {mongo_uri} (database: {mongo_db})"
        logger.info(message)
        client.close()
        return True, message

    except Exception as e:
        message = f"MongoDB connection failed. Tried to connect with: {connection_info}. Error: {str(e)}"
        logger.error(message)
        return False, message


def check_mariadb_connection() -> Tuple[bool, str]:
    """
    Check MariaDB connection status.

    Returns:
        Tuple[bool, str]: (is_alive, message)
    """
    try:
        # Use URI from env
        uri = MARIADB_URI

        # Create engine and test connection
        engine = create_engine(uri)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        message = f"MariaDB connection is alive at {uri}"
        logger.info(message)
        return True, message
    except Exception as e:
        message = f"MariaDB connection failed. URI: {MARIADB_URI}. Error: {str(e)}"
        logger.error(message)
        return False, message


def main() -> int:
    """
    Main function to check all dependencies and provide a summary.

    Returns:
        int: Exit code (0 if all required services are alive, 1 otherwise)
    """
    logger.info("=== Dependency Liveness Check Started ===")

    # Configuration for required services
    raise_if_mongodb_not_alive = (
        os.environ.get("RAISE_IF_MONGODB_NOT_ALIVE", "True").lower() == "true"
    )
    raise_if_mariadb_not_alive = (
        os.environ.get("RAISE_IF_MARIADB_NOT_ALIVE", "True").lower() == "true"
    )

    # Check all services
    services_status = {}

    # Check MongoDB
    mongodb_alive, mongodb_message = check_mongodb_connection()
    services_status["MongoDB"] = {
        "alive": mongodb_alive,
        "message": mongodb_message,
        "required": raise_if_mongodb_not_alive,
    }

    # Check MariaDB
    mariadb_alive, mariadb_message = check_mariadb_connection()
    services_status["MariaDB"] = {
        "alive": mariadb_alive,
        "message": mariadb_message,
        "required": raise_if_mariadb_not_alive,
    }

    # Generate summary
    logger.info("=== Dependency Check Summary ===")

    alive_services = []
    failed_services = []
    failed_required_services = []

    for service_name, status in services_status.items():
        if status["alive"]:
            alive_services.append(service_name)
            logger.info(f"✅ {service_name}: ALIVE - {status['message']}")
        else:
            failed_services.append(service_name)
            if status["required"]:
                failed_required_services.append(service_name)
                logger.error(
                    f"❌ {service_name}: FAILED (REQUIRED) - {status['message']}"
                )
            else:
                logger.warning(
                    f"⚠️  {service_name}: FAILED (OPTIONAL) - {status['message']}"
                )

    # Final summary
    logger.info(
        f"Services alive: {len(alive_services)}/{len(services_status)} - {', '.join(alive_services) if alive_services else 'None'}"
    )
    if failed_services:
        logger.info(
            f"Services failed: {len(failed_services)}/{len(services_status)} - {', '.join(failed_services)}"
        )

    # Determine exit code
    if failed_required_services:
        logger.error(f"Critical services failed: {', '.join(failed_required_services)}")
        logger.error("=== Dependency Check FAILED ===")
        return 1
    else:
        logger.info("=== Dependency Check PASSED ===")
        return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
