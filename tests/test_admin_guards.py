"""V50: privileged-route guards must reject guest, non-admin and invalid CSRF."""
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app import user_auth, admin_routes, cms_routes


class FakeRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


class AdminGuards(unittest.TestCase):
    def setUp(self):
        self.admin_id = "4255210d-d19f-46db-a0ef-ad75ddb3ff3f"
        self.guest_id = "fa2bb496-5f1c-4a81-9e25-b640709fa681"
        self.admin_session = {"user_id": self.admin_id, "csrf_token": "test-csrf"}
        self.user_session = {"user_id": self.guest_id, "csrf_token": "test-csrf"}
        self.admin_ids = patch.object(admin_routes, "ADMIN_IDS", {self.admin_id})
        self.admin_ids.start()

    def tearDown(self):
        self.admin_ids.stop()

    def test_no_session_rejected(self):
        with patch.object(user_auth, "required", side_effect=HTTPException(401, "login required")):
            with self.assertRaises(HTTPException) as err:
                cms_routes.require_admin(FakeRequest())
        self.assertEqual(err.exception.status_code, 401)

    def test_normal_user_rejected(self):
        with patch.object(user_auth, "required", return_value=self.user_session):
            with self.assertRaises(HTTPException) as err:
                cms_routes.require_admin(FakeRequest())
        self.assertEqual(err.exception.status_code, 403)

    def test_email_alone_cannot_grant_admin_access(self):
        ordinary = {"user_id": self.guest_id, "email": "atlas-admin@b2b-atlas.local"}
        self.assertFalse(admin_routes.admin_allowed(ordinary))

    def test_admin_can_read(self):
        with patch.object(user_auth, "required", return_value=self.admin_session):
            self.assertIs(cms_routes.require_admin(FakeRequest()), self.admin_session)

    def test_admin_mutation_requires_csrf(self):
        with patch.object(user_auth, "required", return_value=self.admin_session):
            with self.assertRaises(HTTPException) as err:
                cms_routes.require_admin(FakeRequest(), mutate=True)
        self.assertEqual(err.exception.status_code, 403)

    def test_admin_mutation_accepts_valid_same_origin_and_csrf(self):
        request = FakeRequest({"origin": "https://atlas.example",
                               "host": "atlas.example", "x-csrf-token": "test-csrf"})
        with patch.object(user_auth, "required", return_value=self.admin_session):
            self.assertIs(cms_routes.require_admin(request, mutate=True), self.admin_session)

    def test_cross_site_origin_rejected(self):
        request = FakeRequest({"origin": "https://attacker.example",
                               "host": "atlas.example", "x-csrf-token": "test-csrf"})
        with patch.object(user_auth, "required", return_value=self.admin_session):
            with self.assertRaises(HTTPException) as err:
                cms_routes.require_admin(request, mutate=True)
        self.assertEqual(err.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
