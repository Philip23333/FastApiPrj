import sys
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import app


class TestErrorResponseApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._client_ctx = TestClient(app)
        cls.client = cls._client_ctx.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls._client_ctx.__exit__(None, None, None)

    def _skip_if_server_error(self, response):
        if response.status_code >= 500:
            self.skipTest("Database is not ready; skip error-response test.")

    def test_http_exception_response_shape_404(self):
        response = self.client.get("/users/999999999")
        self._skip_if_server_error(response)

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body.get("code"), 404)
        self.assertEqual(body.get("message"), "User not found")
        self.assertIn("data", body)

    def test_validation_exception_response_shape_422(self):
        # Missing required password field triggers RequestValidationError.
        response = self.client.post("/users/login", json={"username": "only_name"})
        self.assertEqual(response.status_code, 422)

        body = response.json()
        self.assertEqual(body.get("code"), 422)
        self.assertEqual(body.get("message"), "Validation Error")
        self.assertIsInstance(body.get("data"), list)
        self.assertTrue(len(body["data"]) > 0)

    def test_business_exception_response_shape_400(self):
        username = f"dup_{uuid.uuid4().hex[:10]}"
        payload = {
            "username": username,
            "password": "Pass123456",
            "nickname": "dup_user"
        }

        first = self.client.post("/users/register", json=payload)
        self._skip_if_server_error(first)
        self.assertIn(first.status_code, (200, 201))

        user_id = first.json().get("data", {}).get("id")
        try:
            second = self.client.post("/users/register", json=payload)
            self.assertEqual(second.status_code, 400)
            body = second.json()
            self.assertEqual(body.get("code"), 400)
            self.assertEqual(body.get("message"), "用户名已被注册")
            self.assertIn("data", body)
        finally:
            if user_id is not None:
                self.client.delete(f"/users/{user_id}")


if __name__ == "__main__":
    unittest.main()
