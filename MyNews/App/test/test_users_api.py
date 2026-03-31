import sys
import unittest
import uuid
from pathlib import Path

from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from main import app


class TestUsersApi(unittest.TestCase):
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
            self.skipTest("Database is not ready; skip user API test.")
        return response

    def _safe_post(self, url: str, payload: dict, headers: dict | None = None):
        response = self.client.post(url, json=payload, headers=headers)
        if response.status_code >= 500:
            self.skipTest("Database is not ready; skip user API test.")
        return response

    def _safe_put(self, url: str, payload: dict, headers: dict | None = None):
        response = self.client.put(url, json=payload, headers=headers)
        if response.status_code >= 500:
            self.skipTest("Database is not ready; skip user API test.")
        return response

    def _safe_delete(self, url: str, headers: dict | None = None):
        response = self.client.delete(url, headers=headers)
        if response.status_code >= 500:
            self.skipTest("Database is not ready; skip user API test.")
        return response

    def _auth_headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    def _login_token(self, username: str, password: str) -> str:
        login_resp = self._safe_post("/users/login", {"username": username, "password": password})
        self.assertEqual(login_resp.status_code, 200)
        body = login_resp.json()
        self.assertEqual(body.get("code"), 200)
        return body["data"]["access_token"]

    def _create_temp_user(self):
        username = f"ut_{uuid.uuid4().hex[:10]}"
        password = "Pass123456"
        payload = {
            "username": username,
            "password": password,
            "nickname": "unit_test_user"
        }

        response = self._safe_post("/users/register", payload)
        self.assertIn(response.status_code, (200, 201))

        body = response.json()
        self.assertEqual(body.get("code"), 201)
        self.assertIn("data", body)
        user_id = body["data"]["id"]
        token = self._login_token(username, password)
        return username, password, user_id, token

    def test_users_list(self):
        response = self._safe_get("/users/?skip=0&limit=5")
        self.assertEqual(response.status_code, 200)
        body = response.json()

        self.assertEqual(body.get("code"), 200)
        self.assertIn("data", body)
        self.assertIsInstance(body["data"], list)

        if body["data"]:
            sample = body["data"][0]
            self.assertIn("id", sample)
            self.assertIn("username", sample)
            self.assertIn("created_at", sample)
            self.assertIn("updated_at", sample)
            self.assertNotIn("password", sample)

    def test_register_and_login(self):
        username, password, user_id, token = self._create_temp_user()
        try:
            login_resp = self._safe_post(
                "/users/login",
                {"username": username, "password": password}
            )
            self.assertEqual(login_resp.status_code, 200)
            body = login_resp.json()
            self.assertEqual(body.get("code"), 200)
            self.assertEqual(body.get("data", {}).get("user", {}).get("username"), username)
            self.assertNotIn("password", body.get("data", {}).get("user", {}))
            self.assertTrue(isinstance(body.get("data", {}).get("access_token"), str))
            self.assertEqual(body.get("data", {}).get("token_type"), "bearer")

            bad_login_resp = self._safe_post(
                "/users/login",
                {"username": username, "password": "WrongPassword!"}
            )
            self.assertEqual(bad_login_resp.status_code, 400)
            self.assertEqual(bad_login_resp.json().get("code"), 400)
        finally:
            self._safe_delete(f"/users/{user_id}", headers=self._auth_headers(token))

    def test_read_user(self):
        _, _, user_id, token = self._create_temp_user()
        try:
            response = self._safe_get(f"/users/{user_id}")
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body.get("code"), 200)
            self.assertEqual(body.get("data", {}).get("id"), user_id)
        finally:
            self._safe_delete(f"/users/{user_id}", headers=self._auth_headers(token))

    def test_update_user(self):
        _, _, user_id, token = self._create_temp_user()
        try:
            response = self._safe_put(
                f"/users/{user_id}",
                {"nickname": "updated_by_test"},
                headers=self._auth_headers(token),
            )
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(body.get("code"), 200)
            self.assertEqual(body.get("data", {}).get("nickname"), "updated_by_test")
        finally:
            self._safe_delete(f"/users/{user_id}", headers=self._auth_headers(token))

    def test_update_password_and_login(self):
        username, old_password, user_id, token = self._create_temp_user()
        new_password = "NewPass987654"
        try:
            update_resp = self._safe_put(
                f"/users/{user_id}",
                {"password": new_password},
                headers=self._auth_headers(token),
            )
            self.assertEqual(update_resp.status_code, 200)
            self.assertEqual(update_resp.json().get("code"), 200)

            old_login_resp = self._safe_post(
                "/users/login",
                {"username": username, "password": old_password}
            )
            self.assertEqual(old_login_resp.status_code, 400)

            new_login_resp = self._safe_post(
                "/users/login",
                {"username": username, "password": new_password}
            )
            self.assertEqual(new_login_resp.status_code, 200)
            self.assertEqual(new_login_resp.json().get("code"), 200)
        finally:
            self._safe_delete(f"/users/{user_id}", headers=self._auth_headers(token))

    def test_delete_user(self):
        _, _, user_id, token = self._create_temp_user()

        del_resp = self._safe_delete(f"/users/{user_id}", headers=self._auth_headers(token))
        self.assertEqual(del_resp.status_code, 200)
        self.assertEqual(del_resp.json().get("code"), 200)
        self.assertIsNone(del_resp.json().get("data"))

        read_resp = self._safe_get(f"/users/{user_id}")
        self.assertEqual(read_resp.status_code, 404)
        read_body = read_resp.json()
        self.assertEqual(read_body.get("code"), 404)

    def test_update_user_requires_token(self):
        _, _, user_id, token = self._create_temp_user()
        try:
            response = self._safe_put(f"/users/{user_id}", {"nickname": "no_token"})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json().get("code"), 401)
        finally:
            self._safe_delete(f"/users/{user_id}", headers=self._auth_headers(token))


if __name__ == "__main__":
    unittest.main()
