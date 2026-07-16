from __future__ import annotations

import json
from unittest.mock import Mock, call, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from users import service as user_service
from users.models import SiteUserProfile, SocialAccount

User = get_user_model()


@override_settings(
    ALLOW_PASSWORD_REGISTRATION=True,
    VK_APP_ID="vk-client",
    TELEGRAM_OIDC_CLIENT_ID="telegram-client",
    GOOGLE_OAUTH_CLIENT_ID="google-client",
    APPLE_OAUTH_CLIENT_ID="apple-client",
    APPLE_OAUTH_TEAM_ID="apple-team",
    APPLE_OAUTH_KEY_ID="apple-key",
    APPLE_OAUTH_PRIVATE_KEY="fake-private-key",
    APPLE_OAUTH_REDIRECT_URI="https://example.test/auth/apple/callback",
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

    @override_settings(
        GOOGLE_OAUTH_CLIENT_ID="",
        GOOGLE_ANDROID_CLIENT_ID="android-client",
        GOOGLE_IOS_CLIENT_ID="",
        GOOGLE_OAUTH_CLIENT_IDS=[],
    )
    @patch("users.auth_methods.urllib.request.urlopen")
    def test_mobile_google_client_configures_google_login(self, urlopen: Mock) -> None:
        urlopen.return_value = self._country_response("DE")

        response = self.client.get(
            "/api/auth/methods/",
            HTTP_X_FORWARDED_FOR="8.8.8.8",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["configured_methods"]["google"])
        self.assertTrue(response.json()["methods"]["google"])

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


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID="web-client",
    GOOGLE_ANDROID_CLIENT_ID="android-client",
    GOOGLE_IOS_CLIENT_ID="ios-client",
    GOOGLE_OAUTH_CLIENT_IDS=["extra-client", "web-client"],
)
class GoogleAuthenticationTests(TestCase):
    @patch("google.oauth2.id_token.verify_oauth2_token")
    def test_all_configured_client_ids_are_allowed_audiences(self, verify_token: Mock) -> None:
        verify_token.return_value = {
            "iss": "https://accounts.google.com",
            "sub": "google-subject",
            "email": "reader@example.com",
            "email_verified": True,
        }

        identity = user_service._authenticate_google_payload({"id_token": "signed-token"})

        self.assertEqual(identity["subject"], "google-subject")
        self.assertEqual(verify_token.call_args.args[0], "signed-token")
        self.assertEqual(
            verify_token.call_args.args[2],
            ["web-client", "android-client", "ios-client", "extra-client"],
        )


@override_settings(
    APPLE_OAUTH_CLIENT_ID="pub.tambur.web",
    APPLE_OAUTH_CLIENT_IDS=["pub.tambur.web", "ru.comuna.mobile"],
)
class AppleAuthenticationTests(TestCase):
    @patch("users.service._verify_apple_identity_token")
    @patch("users.service._exchange_apple_authorization_code")
    @patch("users.service._apple_token_audience")
    def test_authorization_code_is_exchanged_and_both_tokens_are_verified(
        self,
        token_audience: Mock,
        exchange_code: Mock,
        verify_token: Mock,
    ) -> None:
        token_audience.side_effect = ["pub.tambur.web", "pub.tambur.web"]
        exchange_code.return_value = "exchanged-id-token"
        verify_token.side_effect = [
            {"sub": "apple-subject", "nonce": "browser-nonce"},
            {
                "sub": "apple-subject",
                "email": "reader@example.com",
                "email_verified": True,
                "nonce": "browser-nonce",
            },
        ]

        identity = user_service._authenticate_apple_payload(
            {
                "credential": "browser-id-token",
                "code": "one-time-code",
                "nonce": "browser-nonce",
                "user": {"name": {"firstName": "Apple", "lastName": "Reader"}},
            }
        )

        exchange_code.assert_called_once_with("one-time-code", "pub.tambur.web")
        self.assertEqual(
            verify_token.call_args_list,
            [
                call("browser-id-token", "pub.tambur.web"),
                call("exchanged-id-token", "pub.tambur.web"),
            ],
        )
        self.assertEqual(identity["subject"], "apple-subject")
        self.assertEqual(identity["first_name"], "Apple")

    def test_authorization_code_is_required(self) -> None:
        with self.assertRaises(ValueError):
            user_service._authenticate_apple_payload({"credential": "browser-id-token"})

    @patch("users.service._verify_apple_identity_token")
    @patch("users.service._apple_token_audience", return_value="pub.tambur.web")
    def test_nonce_mismatch_is_rejected(self, _token_audience: Mock, verify_token: Mock) -> None:
        verify_token.return_value = {"sub": "apple-subject", "nonce": "different-nonce"}

        with self.assertRaises(ValueError):
            user_service._authenticate_apple_payload(
                {
                    "credential": "browser-id-token",
                    "code": "one-time-code",
                    "nonce": "browser-nonce",
                }
            )

    @patch("users.service.jwt.decode")
    def test_mobile_bundle_id_is_an_allowed_audience(self, decode: Mock) -> None:
        decode.return_value = {"aud": "ru.comuna.mobile"}

        self.assertEqual(user_service._apple_token_audience("signed-token"), "ru.comuna.mobile")

    @patch("users.service.jwt.decode")
    def test_unknown_audience_is_rejected(self, decode: Mock) -> None:
        decode.return_value = {"aud": "malicious-client"}

        with self.assertRaises(ValueError):
            user_service._apple_token_audience("signed-token")
