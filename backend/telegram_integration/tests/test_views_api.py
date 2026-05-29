import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import resolve

from telegram_integration.models import TelegramAccount
from telegram_integration.service import telegram_payload_from_oidc_claims
from telegram_integration.views import telegram_auth, telegram_webhook
from users import service as user_service
from users.models import SiteUserProfile


class TelegramIntegrationRoutesTests(SimpleTestCase):
    def test_routes_resolve_to_telegram_integration(self):
        self.assertIs(resolve("/api/auth/telegram/").func, telegram_auth)
        self.assertIs(resolve("/tg/webhook/token/").func, telegram_webhook)


User = get_user_model()
TELEGRAM_NATIVE_ORIGIN = "https://app1299099924-login.tg.dev"


@override_settings(TELEGRAM_OIDC_CLIENT_ID="123456789")
class TelegramOidcAuthTests(TestCase):
    def setUp(self):
        self.client = Client()

    def post_json(self, payload: dict):
        return self.client.post(
            "/api/auth/telegram/",
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_oidc_login_accepts_telegram_native_origin(self):
        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "Reader One",
                "preferred_username": "reader_tg",
            },
        ):
            response = self.client.post(
                "/api/auth/telegram/",
                data=json.dumps({"id_token": "token", "auth_intent": "login"}),
                content_type="application/json",
                HTTP_ORIGIN=TELEGRAM_NATIVE_ORIGIN,
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["token"])

    def test_oidc_login_rejects_untrusted_cross_origin(self):
        response = self.client.post(
            "/api/auth/telegram/",
            data=json.dumps({"id_token": "token", "auth_intent": "login"}),
            content_type="application/json",
            HTTP_ORIGIN="https://evil.example",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"], "forbidden origin")

    @override_settings(CORS_ALLOWED_ORIGINS=[TELEGRAM_NATIVE_ORIGIN])
    def test_telegram_native_origin_gets_cors_preflight(self):
        response = self.client.options(
            "/api/auth/telegram/",
            HTTP_ORIGIN=TELEGRAM_NATIVE_ORIGIN,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            TELEGRAM_NATIVE_ORIGIN,
        )

    def test_oidc_payload_maps_phone_claim(self):
        payload = telegram_payload_from_oidc_claims(
            {
                "id": 987654321,
                "name": "Reader One",
                "preferred_username": "reader",
                "picture": "https://example.test/avatar.jpg",
                "phone_number": "79991234567",
            }
        )

        self.assertEqual(payload["id"], 987654321)
        self.assertEqual(payload["first_name"], "Reader")
        self.assertEqual(payload["last_name"], "One")
        self.assertEqual(payload["username"], "reader")
        self.assertEqual(payload["phone"], "+79991234567")

    def test_oidc_payload_keeps_sub_when_bot_api_id_is_absent(self):
        with patch("telegram_integration.service._telegram_oidc_jwks_client") as jwks_client:
            jwks_client.return_value.get_signing_key_from_jwt.return_value.key = "public-key"
            with patch(
                "telegram_integration.service.jwt.decode",
                return_value={
                    "iss": "https://oauth.telegram.org",
                    "aud": "123456789",
                    "sub": "987654321",
                    "iat": 1700000000,
                    "exp": 1700003600,
                },
            ):
                from telegram_integration.service import validate_telegram_oidc_token

                claims = validate_telegram_oidc_token("token")

        payload = telegram_payload_from_oidc_claims(claims)
        self.assertNotIn("id", claims)
        self.assertEqual(claims["oidc_sub"], "987654321")
        self.assertEqual(payload["id"], "987654321")
        self.assertEqual(payload["oidc_sub"], "987654321")
        self.assertEqual(payload["telegram_id_source"], "sub")

    def test_oidc_login_links_existing_phone_user_without_new_account_privacy(self):
        user = User.objects.create_user(username="reader")
        SiteUserProfile.objects.create(user=user, phone="+79991234567")

        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "name": "Reader One",
                "preferred_username": "reader_tg",
                "phone_number": "79991234567",
            },
        ):
            response = self.post_json({"id_token": "token"})

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user"]["id"], user.id)
        self.assertEqual(TelegramAccount.objects.get(telegram_id=987654321).user_id, user.id)
        self.assertEqual(User.objects.count(), 1)

    def test_oidc_login_new_account_creates_user_without_privacy_checkbox(self):
        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "Reader One",
                "preferred_username": "reader_tg",
            },
        ):
            response = self.post_json({"id_token": "token", "auth_intent": "login"})

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["token"])
        self.assertEqual(User.objects.count(), 1)
        account = TelegramAccount.objects.get(telegram_id=987654321)
        self.assertEqual(account.user_id, payload["user"]["id"])
        self.assertEqual(account.oidc_sub, "1234123412341234123")

    def test_oidc_signup_new_account_requires_privacy_consent(self):
        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "Reader One",
                "preferred_username": "reader_tg",
            },
        ):
            response = self.post_json({"id_token": "token", "auth_intent": "signup"})

        payload = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertIn("политик", payload["error"].lower())
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(TelegramAccount.objects.count(), 0)

    def test_oidc_signup_new_account_with_privacy_consent_creates_user(self):
        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "Reader One",
                "preferred_username": "reader_tg",
            },
        ):
            response = self.post_json(
                {
                    "id_token": "token",
                    "auth_intent": "signup",
                    "privacy_accepted": True,
                }
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["token"])
        self.assertEqual(User.objects.count(), 1)
        account = TelegramAccount.objects.get(telegram_id=987654321)
        self.assertEqual(account.user_id, payload["user"]["id"])
        self.assertEqual(account.oidc_sub, "1234123412341234123")

    def test_oidc_login_keeps_existing_telegram_account_user(self):
        user = User.objects.create_user(username="channel_owner")
        TelegramAccount.objects.create(
            user=user,
            telegram_id=987654321,
            username="old_owner",
            first_name="Old",
        )

        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "New Owner",
                "preferred_username": "new_owner",
            },
        ):
            response = self.post_json({"id_token": "token"})

        payload = response.json()
        account = TelegramAccount.objects.get(telegram_id=987654321)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user"]["id"], user.id)
        self.assertEqual(account.user_id, user.id)
        self.assertEqual(account.oidc_sub, "1234123412341234123")
        self.assertEqual(account.username, "new_owner")
        self.assertEqual(User.objects.count(), 1)

    def test_oidc_login_reuses_stored_sub_when_bot_api_id_is_missing_later(self):
        user = User.objects.create_user(username="channel_owner")
        TelegramAccount.objects.create(
            user=user,
            telegram_id=987654321,
            username="old_owner",
            first_name="Old",
        )

        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "New Owner",
                "preferred_username": "new_owner",
            },
        ):
            first_response = self.post_json({"id_token": "token"})

        self.assertEqual(first_response.status_code, 200)
        account = TelegramAccount.objects.get(user=user)
        self.assertEqual(account.telegram_id, 987654321)
        self.assertEqual(account.oidc_sub, "1234123412341234123")

        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "sub": "1234123412341234123",
                "name": "New Owner",
                "preferred_username": "new_owner",
            },
        ):
            second_response = self.post_json({"id_token": "token"})

        payload = second_response.json()
        account.refresh_from_db()
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(payload["user"]["id"], user.id)
        self.assertEqual(account.telegram_id, 987654321)
        self.assertEqual(TelegramAccount.objects.count(), 1)
        self.assertEqual(User.objects.count(), 1)

    def test_oidc_login_normalizes_legacy_sub_saved_as_telegram_id(self):
        user = User.objects.create_user(username="oidc_duplicate")
        TelegramAccount.objects.create(
            user=user,
            telegram_id=1234123412341234123,
            username="old_oidc",
        )

        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "Reader One",
                "preferred_username": "reader_tg",
            },
        ):
            response = self.post_json({"id_token": "token"})

        payload = response.json()
        account = TelegramAccount.objects.get(user=user)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user"]["id"], user.id)
        self.assertEqual(account.telegram_id, 987654321)
        self.assertEqual(account.oidc_sub, "1234123412341234123")
        self.assertEqual(TelegramAccount.objects.count(), 1)
        self.assertEqual(User.objects.count(), 1)

    def test_oidc_login_merges_existing_real_id_and_legacy_sub_accounts(self):
        real_user = User.objects.create_user(username="real_id")
        legacy_user = User.objects.create_user(username="legacy_sub")
        TelegramAccount.objects.create(
            user=real_user,
            telegram_id=987654321,
            username="real",
        )
        TelegramAccount.objects.create(
            user=legacy_user,
            telegram_id=1234123412341234123,
            username="legacy",
        )

        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "Reader One",
                "preferred_username": "reader_tg",
            },
        ):
            response = self.post_json({"id_token": "token"})

        payload = response.json()
        legacy_user.refresh_from_db()
        account = TelegramAccount.objects.get(telegram_id=987654321)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user"]["id"], real_user.id)
        self.assertFalse(legacy_user.is_active)
        self.assertEqual(account.user_id, real_user.id)
        self.assertEqual(account.oidc_sub, "1234123412341234123")
        self.assertEqual(TelegramAccount.objects.count(), 1)

    def test_oidc_authenticated_link_merges_existing_telegram_account(self):
        target = User.objects.create_user(username="target")
        duplicate = User.objects.create_user(username="duplicate")
        TelegramAccount.objects.create(
            user=duplicate,
            telegram_id=987654321,
            username="old_owner",
        )
        token = user_service._issue_token(target)

        with patch(
            "telegram_integration.views.validate_telegram_oidc_token",
            return_value={
                "id": 987654321,
                "sub": "1234123412341234123",
                "name": "New Owner",
                "preferred_username": "new_owner",
            },
        ):
            response = self.client.post(
                "/api/auth/telegram/",
                data=json.dumps({"id_token": "token", "auth_intent": "login"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        payload = response.json()
        duplicate.refresh_from_db()
        account = TelegramAccount.objects.get(telegram_id=987654321)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user"]["id"], target.id)
        self.assertFalse(duplicate.is_active)
        self.assertEqual(account.user_id, target.id)
        self.assertEqual(account.oidc_sub, "1234123412341234123")
