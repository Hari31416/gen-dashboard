import os
import unittest
from unittest.mock import MagicMock, patch

from services.database.connection_pool import EnginePool, engine_pool


class TestEnginePool(unittest.TestCase):
    def setUp(self):
        # Reset the singleton instance for each test to ensure isolation
        # This is a bit hacky but necessary for testing singletons with different configs
        EnginePool._instance = None

    def test_singleton_pattern(self):
        """Test that EnginePool follows the singleton pattern"""
        pool1 = EnginePool()
        pool2 = EnginePool()
        self.assertIs(pool1, pool2, "EnginePool should be a singleton")

    def test_get_engine_reuse(self):
        """Test that get_engine returns the same engine for the same connection string"""
        pool = EnginePool()

        # Use sqlite in-memory for testing
        conn_str = "sqlite:///:memory:"

        engine1 = pool.get_engine(conn_str)
        engine2 = pool.get_engine(conn_str)

        self.assertIs(engine1, engine2, "Should return the exact same engine instance")

    def test_get_engine_different_strings(self):
        """Test that different connection strings get different engines"""
        pool = EnginePool()

        conn_str1 = "sqlite:///db1.sqlite"
        conn_str2 = "sqlite:///db2.sqlite"

        engine1 = pool.get_engine(conn_str1)
        engine2 = pool.get_engine(conn_str2)

        self.assertIsNot(engine1, engine2, "Should return different engines")

    def test_dispose_engine(self):
        """Test disposing a specific engine"""
        pool = EnginePool()
        conn_str = "sqlite:///:memory:"

        engine = pool.get_engine(conn_str)
        self.assertIn(conn_str, pool._engines)

        removed = pool.dispose_engine(conn_str)
        self.assertTrue(removed)
        self.assertNotIn(conn_str, pool._engines)

        # Verify it was actually disposed (though we can't easily check internal state,
        # checking the map is good enough)

    @patch.dict(
        os.environ,
        {
            "SQL_POOL_SIZE": "10",
            "SQL_POOL_MAX_OVERFLOW": "20",
            "SQL_POOL_TIMEOUT": "60",
            "SQL_POOL_RECYCLE": "3600",
        },
    )
    def test_configuration_loading(self):
        """Test that configuration is loaded from environment variables"""
        pool = EnginePool()

        self.assertEqual(pool.pool_size, 10)
        self.assertEqual(pool.max_overflow, 20)
        self.assertEqual(pool.pool_timeout, 60)
        self.assertEqual(pool.pool_recycle, 3600)


if __name__ == "__main__":
    unittest.main()
