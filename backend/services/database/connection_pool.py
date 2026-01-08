"""
Connection Pool Manager

This module provides a centralized manager for SQLAlchemy engines to enable
efficient connection pooling across the application.
"""

import os
import threading
from typing import Dict

from pymongo import MongoClient
from sqlalchemy import Engine, create_engine, pool
from utilities import create_simple_logger

logger = create_simple_logger(__name__)


class EnginePool:
    """
    Manages a pool of SQLAlchemy engines.

    This class ensures that we reuse engines (and their underlying connection pools)
    for the same connection string, rather than creating new ones on every request.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EnginePool, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._engines: Dict[str, Engine] = {}
        self._engine_lock = threading.Lock()

        # Load configuration from environment variables
        self.pool_size = int(os.getenv("SQL_POOL_SIZE", "5"))
        self.max_overflow = int(os.getenv("SQL_POOL_MAX_OVERFLOW", "10"))
        self.pool_timeout = int(os.getenv("SQL_POOL_TIMEOUT", "30"))
        self.pool_recycle = int(os.getenv("SQL_POOL_RECYCLE", "1800"))

        logger.info(
            f"Initialized EnginePool with settings: "
            f"size={self.pool_size}, overflow={self.max_overflow}, "
            f"timeout={self.pool_timeout}, recycle={self.pool_recycle}"
        )
        self._initialized = True

    def get_engine(self, connection_string: str) -> Engine:
        """
        Get or create an SQLAlchemy engine for the given connection string.

        Args:
            connection_string: The database connection string.

        Returns:
            An SQLAlchemy Engine instance.
        """
        if connection_string not in self._engines:
            with self._engine_lock:
                # Double-check locking pattern
                if connection_string not in self._engines:
                    try:
                        logger.debug(
                            f"Creating new engine for connection string (hash={hash(connection_string)})"
                        )

                        # Configure engine with pooling parameters
                        engine = create_engine(
                            connection_string,
                            poolclass=pool.QueuePool,
                            pool_size=self.pool_size,
                            max_overflow=self.max_overflow,
                            pool_timeout=self.pool_timeout,
                            pool_recycle=self.pool_recycle,
                            pool_pre_ping=True,
                        )
                        self._engines[connection_string] = engine
                        logger.info("Created and cached new engine for connection.")
                    except Exception as e:
                        logger.error(f"Failed to create engine: {e}")
                        raise

        return self._engines[connection_string]

    def dispose_engine(self, connection_string: str) -> bool:
        """
        Dispose of an engine and remove it from the pool.

        Args:
            connection_string: The connection string of the engine to dispose.

        Returns:
            True if engine was found and disposed, False otherwise.
        """
        with self._engine_lock:
            if connection_string in self._engines:
                engine = self._engines.pop(connection_string)
                engine.dispose()
                logger.info("Disposed and removed engine from pool.")
                return True
            return False

    def dispose_all(self):
        """Dispose of all managed engines."""
        with self._engine_lock:
            count = len(self._engines)
            for engine in self._engines.values():
                engine.dispose()
            self._engines.clear()
            logger.info(f"Disposed all {count} engines in the pool.")


# Global instance
engine_pool = EnginePool()


class MongoPool:
    """
    Manages a singleton MongoDB client.

    Since PyMongo's MongoClient is thread-safe and has built-in connection pooling,
    we only need to ensure we share a single instance across the application.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MongoPool, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._client = None
        self._client_lock = threading.Lock()

        # Load configuration from environment variables
        self.min_pool_size = int(os.getenv("MONGO_MIN_POOL_SIZE", "10"))
        self.max_pool_size = int(os.getenv("MONGO_MAX_POOL_SIZE", "100"))
        self.max_idle_time_ms = int(os.getenv("MONGO_MAX_IDLE_TIME", "60000"))

        logger.info(
            f"Initialized MongoPool with settings: "
            f"min_pool_size={self.min_pool_size}, max_pool_size={self.max_pool_size}, "
            f"max_idle_time_ms={self.max_idle_time_ms}"
        )
        self._initialized = True

    def get_client(
        self, mongo_uri: str
    ) -> "MongoClient":  # Type hint as string or import TYPE_CHECKING
        """
        Get or create the singleton MongoClient.

        Args:
            mongo_uri: The MongoDB connection URI.

        Returns:
            A MongoClient instance.
        """
        # Lazy initialization
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    try:
                        from pymongo import MongoClient

                        logger.debug("Creating new singleton MongoClient.")
                        self._client = MongoClient(
                            mongo_uri,
                            minPoolSize=self.min_pool_size,
                            maxPoolSize=self.max_pool_size,
                            maxIdleTimeMS=self.max_idle_time_ms,
                            authSource="admin",
                            serverSelectionTimeoutMS=5000,
                        )
                        # Quick ping to verify connection
                        self._client.admin.command("ping")
                        logger.info("Successfully connected to MongoDB.")
                    except Exception as e:
                        logger.error(f"Failed to create MongoClient: {e}")
                        raise

        return self._client

    def close(self):
        """Close the MongoClient connection."""
        with self._client_lock:
            if self._client:
                self._client.close()
                self._client = None
                logger.info("Closed MongoDB connection.")


# Global instance
mongo_pool = MongoPool()
