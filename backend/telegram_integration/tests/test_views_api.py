import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import resolve

from telegram_integration.models import TelegramAccount
from telegram_integration.service import telegram_payload_from_oidc_claims
from telegram_integration.views import telegram_auth, telegram_webhook
from users.models import SiteUserProfile


class TelegramIntegrationRoutesTests(SimpleTestCase):
    def test_routes_resolve_to_telegram_integration(self):
        self.assertIs(resolve("/api/auth/telegram/").func, telegram_auth)
        self.assertIs(resolve("/tg/webhook/token/").func, telegram_webhook)


User = get_user_model()


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
        self.assertEqual(account.username, "new_owner")
        self.assertEqual(User.objects.count(), 1)
