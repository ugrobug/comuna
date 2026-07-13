from __future__ import annotations

import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from users.models import SiteUserProfile, SocialAccount

User = get_user_model()


@override_settings(
    ALLOW_PASSWORD_REGISTRATION=True,
    VK_APP_ID="vk-client",
    TELEGRAM_OIDC_CLIENT_ID="telegram-client",
    GOOGLE_OAUTH_CLIENT_ID="google-client",
    APPLE_OAUTH_CLIENT_ID="apple-client",
    AUTH_COUNTRY_LOOKUP_URL="https://country.test/{ip}",
)
class AuthMethodsApiTests(TestCase):
    def setUp(self) -> None:
        cache.clear()

    @staticmethod
    def _country_response(country: str) -> Mock:
        response = Mock()
        response.read.return_value = json.dumps({"country": country}).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    @patch("users.auth_methods.urllib.request.urlopen")
    def test_russian_ip_gets_email_and_vk_only(self, urlopen: Mock) -> None:
        urlopen.return_value = self._country_response("RU")

        response = self.client.get(
            "/api/auth/methods/",
            HTTP_X_FORWARDED_FOR="5.255.255.70",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["methods"],
            {"email": True, "vk": True, "google": False, "apple": False, "telegram": False},
        )
        self.assertEqual(response.json()["region"], "russia")
        self.assertIn("no-store", response["Cache-Control"])

    @patch("users.auth_methods.urllib.request.urlopen")
    def test_foreign_ip_gets_email_google_apple_and_telegram(self, urlopen: Mock) -> None:
        urlopen.return_value = self._country_response("DE")

        response = self.client.get(
            "/api/auth/methods/",
            HTTP_X_FORWARDED_FOR="8.8.8.8",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["methods"],
            {"email": True, "vk": False, "google": True, "apple": True, "telegram": True},
        )
        self.assertEqual(response.json()["region"], "international")

    @patch("users.auth_methods.urllib.request.urlopen", side_effect=OSError("offline"))
    def test_lookup_failure_falls_back_to_email_only(self, _urlopen: Mock) -> None:
        response = self.client.get(
            "/api/auth/methods/",
            HTTP_X_FORWARDED_FOR="1.1.1.1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["region"], "unknown")
        self.assertEqual(
            response.json()["methods"],
            {"email": True, "vk": False, "google": False, "apple": False, "telegram": False},
        )

    @patch("users.auth_methods.urllib.request.urlopen")
    def test_country_result_is_cached_by_ip(self, urlopen: Mock) -> None:
        urlopen.return_value = self._country_response("US")

        for _ in range(2):
            response = self.client.get(
                "/api/auth/methods/",
                HTTP_X_FORWARDED_FOR="8.8.4.4",
            )
            self.assertEqual(response.status_code, 200)

        self.assertEqual(urlopen.call_count, 1)

    def test_endpoint_rejects_post(self) -> None:
        response = self.client.post("/api/auth/methods/", data="{}", content_type="application/json")
        self.assertEqual(response.status_code, 405)

    @patch("users.auth_methods.urllib.request.urlopen")
    def test_nginx_real_ip_takes_precedence_over_forwarded_header(self, urlopen: Mock) -> None:
        urlopen.return_value = self._country_response("RU")

        response = self.client.get(
            "/api/auth/methods/",
            HTTP_X_REAL_IP="5.255.255.70",
            HTTP_X_FORWARDED_FOR="8.8.8.8",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["region"], "russia")
        requested_url = urlopen.call_args.args[0].full_url
        self.assertTrue(requested_url.endswith("/5.255.255.70"))


class SocialAuthApiTests(TestCase):
    def post_json(self, path: str, payload: dict):
        return self.client.post(path, data=json.dumps(payload), content_type="application/json")

    @patch("users.service._authenticate_social_payload")
    def test_google_signup_creates_linked_account(self, authenticate: Mock) -> None:
        authenticate.return_value = {
            "provider": "google",
            "subject": "google-subject-1",
            "email": "reader@example.com",
            "first_name": "Reader",
            "last_name": "One",
            "avatar_url": "",
        }

        response = self.post_json(
            "/api/auth/google/",
            {
                "credential": "signed-token",
                "auth_intent": "signup",
                "privacy_accepted": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["token"])
        account = SocialAccount.objects.select_related("user").get(
            provider="google",
            subject="google-subject-1",
        )
        self.assertEqual(account.user.email, "reader@example.com")
        self.assertIsNotNone(account.user.site_profile.email_verified_at)

    @patch("users.service._authenticate_social_payload")
    def test_social_login_does_not_silently_register(self, authenticate: Mock) -> None:
        authenticate.return_value = {
            "provider": "apple",
            "subject": "apple-subject-1",
            "email": "apple@example.com",
            "first_name": "",
            "last_name": "",
            "avatar_url": "",
        }

        response = self.post_json(
            "/api/auth/apple/",
            {"credential": "signed-token", "auth_intent": "login"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(SocialAccount.objects.count(), 0)

    @patch("users.service._authenticate_social_payload")
    def test_social_signup_requires_privacy_consent(self, authenticate: Mock) -> None:
        authenticate.return_value = {
            "provider": "apple",
            "subject": "apple-subject-2",
            "email": "privacy@example.com",
            "first_name": "",
            "last_name": "",
            "avatar_url": "",
        }

        response = self.post_json(
            "/api/auth/apple/",
            {"credential": "signed-token", "auth_intent": "signup"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(SocialAccount.objects.count(), 0)

    @patch("users.service._authenticate_social_payload")
    def test_existing_social_account_can_log_in(self, authenticate: Mock) -> None:
        user = User.objects.create_user(username="existing-reader", email="existing@example.com")
        SocialAccount.objects.create(
            user=user,
            provider="google",
            subject="google-subject-existing",
            email=user.email,
        )
        authenticate.return_value = {
            "provider": "google",
            "subject": "google-subject-existing",
            "email": user.email,
            "first_name": "",
            "last_name": "",
            "avatar_url": "",
        }

        response = self.post_json(
            "/api/auth/google/",
            {"credential": "signed-token", "auth_intent": "login"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["id"], user.id)

    @patch("users.service._authenticate_social_payload")
    def test_social_login_links_an_existing_verified_email(self, authenticate: Mock) -> None:
        user = User.objects.create_user(username="verified-reader", email="verified@example.com")
        profile, _created = SiteUserProfile.objects.get_or_create(user=user)
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["email_verified_at", "updated_at"])
        authenticate.return_value = {
            "provider": "google",
            "subject": "verified-google-subject",
            "email": user.email,
            "first_name": "",
            "last_name": "",
            "avatar_url": "",
        }

        response = self.post_json(
            "/api/auth/google/",
            {"credential": "signed-token", "auth_intent": "login"},
        )

        self.assertEqual(response.status_code, 200)
        account = SocialAccount.objects.get(provider="google", subject="verified-google-subject")
        self.assertEqual(account.user_id, user.id)

    @patch("users.service._authenticate_social_payload")
    def test_social_signup_does_not_claim_an_unverified_email(self, authenticate: Mock) -> None:
        unverified_user = User.objects.create_user(
            username="unverified-reader",
            email="unverified@example.com",
        )
        authenticate.return_value = {
            "provider": "google",
            "subject": "unverified-google-subject",
            "email": unverified_user.email,
            "first_name": "",
            "last_name": "",
            "avatar_url": "",
        }

        response = self.post_json(
            "/api/auth/google/",
            {
                "credential": "signed-token",
                "auth_intent": "signup",
                "privacy_accepted": True,
            },
        )

        self.assertEqual(response.status_code, 200)
        account = SocialAccount.objects.get(provider="google", subject="unverified-google-subject")
        self.assertNotEqual(account.user_id, unverified_user.id)
