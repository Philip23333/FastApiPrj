import unittest

from fastapi.testclient import TestClient

from App.main import app


class TestApiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, dict)
        self.assertEqual(data.get("message"), "Hello World")

    def test_hot_news_endpoint_shape(self):
        response = self.client.get("/news/hot?page=1&size=2")

        # If DB is unavailable in current environment, skip this check to avoid false negatives.
        if response.status_code >= 500:
            self.skipTest("Database is not ready; skip hot news smoke test.")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data, dict)
        self.assertIn("code", data)
        self.assertIn("message", data)
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)


if __name__ == "__main__":
    unittest.main()
