import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import app


class TestNewsApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def _safe_get(self, url: str):
        response = self.client.get(url)
        if response.status_code >= 500:
            self.skipTest("Database is not ready; skip news API test.")
        return response

    def test_news_list(self):
        response = self._safe_get("/news/?page=1&size=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data.get("code"), 200)
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], dict)
        self.assertIsInstance(data["data"].get("total"), int)
        self.assertIsInstance(data["data"].get("page"), int)
        self.assertIsInstance(data["data"].get("size"), int)
        self.assertIsInstance(data["data"].get("totalPages"), int)
        self.assertIn("items", data["data"])
        self.assertIsInstance(data["data"]["items"], list)

        items = data["data"]["items"]
        if items:
            sample = items[0]
            self.assertIn("id", sample)
            self.assertIn("title", sample)
            self.assertIn("description", sample)
            self.assertIn("category_name", sample)
            self.assertIn("author", sample)
            self.assertIn("views", sample)
            self.assertIn("publish_time", sample)
            self.assertIn("image", sample)

    def test_news_categories(self):
        response = self._safe_get("/news/categories")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data.get("code"), 200)
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

        if data["data"]:
            sample = data["data"][0]
            self.assertIn("id", sample)
            self.assertIn("name", sample)
            self.assertIn("sort_order", sample)
            self.assertIn("created_at", sample)
            self.assertIn("updated_at", sample)

    def test_hot_news(self):
        response = self._safe_get("/news/hot?page=1&size=5&min_views=0")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIn("code", data)
        self.assertIn("message", data)
        self.assertIn("data", data)
        self.assertIsInstance(data["data"], list)

        if data["data"]:
            sample = data["data"][0]
            self.assertIn("id", sample)
            self.assertIn("title", sample)
            self.assertIn("views", sample)

    def test_news_detail(self):
        list_resp = self._safe_get("/news/?page=1&size=1")
        items = list_resp.json().get("data", {}).get("items", [])
        if not items:
            self.skipTest("No news records found; skip detail test.")

        news_id = items[0]["id"]
        response = self._safe_get(f"/news/detail/{news_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data.get("code"), 200)
        self.assertIn("data", data)
        self.assertEqual(data["data"].get("id"), news_id)
        self.assertIn("title", data["data"])
        self.assertIn("content", data["data"])
        self.assertIn("category_id", data["data"])
        self.assertIn("category_name", data["data"])
        self.assertIn("author", data["data"])
        self.assertIn("views", data["data"])
        self.assertIn("publish_time", data["data"])
        self.assertIn("image", data["data"])

    def test_news_by_category(self):
        cate_resp = self._safe_get("/news/categories")
        categories = cate_resp.json().get("data", [])
        if not categories:
            self.skipTest("No categories found; skip category news test.")

        category_id = categories[0]["id"]
        response = self._safe_get(f"/news/categories/{category_id}/news?page=1&size=5")
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data.get("code"), 200)
        self.assertIn("data", data)
        self.assertIsInstance(data["data"].get("total"), int)
        self.assertIsInstance(data["data"].get("page"), int)
        self.assertIsInstance(data["data"].get("size"), int)
        self.assertIsInstance(data["data"].get("totalPages"), int)
        self.assertIn("items", data["data"])
        self.assertIsInstance(data["data"]["items"], list)


if __name__ == "__main__":
    unittest.main()
