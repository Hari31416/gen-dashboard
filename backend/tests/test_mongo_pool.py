import os
import unittest
from unittest.mock import MagicMock, patch

from services.database.connection_pool import MongoPool, mongo_pool


class TestMongoPool(unittest.TestCase):
    def setUp(self):
        # Reset singleton
        MongoPool._instance = None

    def test_singleton_pattern(self):
        """Test that MongoPool is a singleton"""
        pool1 = MongoPool()
        pool2 = MongoPool()
        self.assertIs(pool1, pool2)

    @patch("pymongo.MongoClient")
    def test_get_client_reuse(self, mock_mongo_client):
        """Test that get_client returns the same client instance"""
        pool = MongoPool()
        uri = "mongodb://localhost:27017"

        # First call creates client
        client1 = pool.get_client(uri)

        # Second call should return same client
        client2 = pool.get_client(uri)

        self.assertIs(client1, client2)
        mock_mongo_client.assert_called_once()  # Should only be called once

    @patch.dict(
        os.environ,
        {
            "MONGO_MIN_POOL_SIZE": "5",
            "MONGO_MAX_POOL_SIZE": "50",
            "MONGO_MAX_IDLE_TIME": "30000",
        },
    )
    def test_configuration_loading(self):
        """Test that configuration is loaded from environment"""
        pool = MongoPool()
        self.assertEqual(pool.min_pool_size, 5)
        self.assertEqual(pool.max_pool_size, 50)
        self.assertEqual(pool.max_idle_time_ms, 30000)


if __name__ == "__main__":
    unittest.main()
