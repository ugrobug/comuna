import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users import service as user_service
from users.models import SiteUserProfile, TelegramAccount, VkAccount


User = get_user_model()


@override_settings(
    ALLOW_PASSWORD_REGISTRATION=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.test",
    SITE_BASE_URL="https://tambur.test",
)
class EmailAuthApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        mail.outbox = []

    def post_json(self, path: str, payload: dict):
        return self.client.post(
            path,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_register_requires_email(self):
        response = self.post_json(
            "/api/auth/register/",
            {
                "username": "reader",
                "password": "StrongPass123!",
                "privacy_accepted": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("email", response.json()["error"])

    def test_register_sends_email_verification_link(self):
        response = self.post_json(
            "/api/auth/register/",
            {
                "username": "reader",
                "email": "reader@example.test",
                "password": "StrongPass123!",
                "privacy_accepted": True,
            },
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["email_sent"])
        self.assertFalse(payload["user"]["email_verified"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["reader@example.test"])
        self.assertIn("Подтвердите почту", mail.outbox[0].subject)
        self.assertIn("/verify_email/", mail.outbox[0].body)

    def test_verify_email_marks_profile_verified(self):
        response = self.post_json(
            "/api/auth/register/",
            {
                "username": "reader",
                "email": "reader@example.test",
                "password": "StrongPass123!",
                "privacy_accepted": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        secret = mail.outbox[0].body.split("/verify_email/", 1)[1].split()[0]

        verify_response = self.client.get(
            "/api/auth/verify-email/",
            {"token": secret},
        )

        self.assertEqual(verify_response.status_code, 200)
        self.assertTrue(verify_response.json()["user"]["email_verified"])
        user = User.objects.get(username="reader")
        self.assertIsNotNone(SiteUserProfile.objects.get(user=user).email_verified_at)

    def test_update_profile_email_sends_verification_link(self):
        user = User.objects.create_user(username="reader")
        token = user_service._issue_token(user)

        response = self.client.patch(
            "/api/auth/me/",
            data=json.dumps({"email": "reader@example.test"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        payload = response.json()
        user.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(user.email, "reader@example.test")
        self.assertFalse(payload["user"]["email_verified"])
        self.assertTrue(payload["email_verification_sent"])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verify_email/", mail.outbox[0].body)

    def test_verify_email_merges_duplicate_account_with_same_email(self):
        target = User.objects.create_user(username="target", email="reader@example.test")
        duplicate = User.objects.create_user(username="duplicate", email="reader@example.test")
        TelegramAccount.objects.create(user=duplicate, telegram_id=123456)
        SiteUserProfile.objects.create(user=duplicate, display_name="Old profile")
        secret = (
            f"{urlsafe_base64_encode(force_bytes(target.pk))}:"
            f"{default_token_generator.make_token(target)}"
        )

        response = self.client.get("/api/auth/verify-email/", {"token": secret})

        target.refresh_from_db()
        duplicate.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["user"]["email_verified"])
        self.assertFalse(duplicate.is_active)
        self.assertEqual(duplicate.email, "")
        self.assertEqual(TelegramAccount.objects.get(telegram_id=123456).user_id, target.id)
        self.assertEqual(SiteUserProfile.objects.get(user=target).display_name, "Old profile")

    def test_verify_email_rejects_bad_secret(self):
        response = self.client.get(
            "/api/auth/verify-email/",
            {"token": "bad-token"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    def test_password_reset_request_sends_reset_link(self):
        user = User.objects.create_user(
            username="reader",
            email="reader@example.test",
            password="StrongPass123!",
        )

        response = self.post_json(
            "/api/auth/password-reset/",
            {"email": "reader@example.test"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})
        self.assertEqual(len(mail.outbox), 1)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        self.assertIn(f"/login_reset?uid={uid}&token=", mail.outbox[0].body)

    def test_password_reset_confirm_updates_password_and_logs_in(self):
        user = User.objects.create_user(
            username="reader",
            email="reader@example.test",
            password="StrongPass123!",
        )
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        response = self.post_json(
            "/api/auth/password-reset/confirm/",
            {
                "uid": uid,
                "token": token,
                "password": "NewStrongPass123!",
            },
        )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["token"])
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewStrongPass123!"))

    def test_vk_login_links_existing_email_user_without_privacy_checkbox(self):
        user = User.objects.create_user(
            username="reader",
            email="reader@example.test",
            password="StrongPass123!",
        )

        with patch(
            "users.service._authenticate_vk_payload",
            return_value={
                "vk_id": 12345,
                "screen_name": "reader_vk",
                "email": "reader@example.test",
                "phone": "",
                "first_name": "Reader",
                "last_name": "",
                "avatar_url": "",
            },
        ):
            response = self.post_json("/api/auth/vk/", {"access_token": "token"})

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user"]["id"], user.id)
        account = VkAccount.objects.get(vk_id=12345)
        self.assertEqual(account.user_id, user.id)
        self.assertEqual(account.email, "reader@example.test")
        self.assertEqual(User.objects.count(), 1)

    def test_vk_login_new_account_creates_user_without_privacy_checkbox(self):
        with patch(
            "users.service._authenticate_vk_payload",
            return_value={
                "vk_id": 12345,
                "screen_name": "reader_vk",
                "email": "",
                "phone": "",
                "first_name": "Reader",
                "last_name": "",
                "avatar_url": "",
            },
        ):
            response = self.post_json(
                "/api/auth/vk/",
                {"access_token": "token", "auth_intent": "login"},
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["token"])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(VkAccount.objects.get(vk_id=12345).user_id, payload["user"]["id"])

    def test_vk_signup_new_account_requires_privacy_consent(self):
        with patch(
            "users.service._authenticate_vk_payload",
            return_value={
                "vk_id": 12345,
                "screen_name": "reader_vk",
                "email": "",
                "phone": "",
                "first_name": "Reader",
                "last_name": "",
                "avatar_url": "",
            },
        ):
            response = self.post_json(
                "/api/auth/vk/",
                {"access_token": "token", "auth_intent": "signup"},
            )

        payload = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertIn("политик", payload["error"].lower())
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(VkAccount.objects.count(), 0)

    def test_vk_signup_new_account_with_privacy_consent_creates_user(self):
        with patch(
            "users.service._authenticate_vk_payload",
            return_value={
                "vk_id": 12345,
                "screen_name": "reader_vk",
                "email": "",
                "phone": "",
                "first_name": "Reader",
                "last_name": "",
                "avatar_url": "",
            },
        ):
            response = self.post_json(
                "/api/auth/vk/",
                {
                    "access_token": "token",
                    "auth_intent": "signup",
                    "privacy_accepted": True,
                },
            )

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["token"])
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(VkAccount.objects.get(vk_id=12345).user_id, payload["user"]["id"])

    def test_authenticated_vk_link_merges_existing_vk_account(self):
        target = User.objects.create_user(username="target")
        duplicate = User.objects.create_user(username="duplicate")
        VkAccount.objects.create(
            user=duplicate,
            vk_id=12345,
            username="reader_vk",
        )
        token = user_service._issue_token(target)

        with patch(
            "users.service._authenticate_vk_payload",
            return_value={
                "vk_id": 12345,
                "screen_name": "reader_vk",
                "email": "",
                "phone": "",
                "first_name": "Reader",
                "last_name": "",
                "avatar_url": "",
            },
        ):
            response = self.client.post(
                "/api/auth/vk/",
                data=json.dumps({"access_token": "token", "auth_intent": "login"}),
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        payload = response.json()
        duplicate.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["user"]["id"], target.id)
        self.assertFalse(duplicate.is_active)
        self.assertEqual(VkAccount.objects.get(vk_id=12345).user_id, target.id)

    def test_register_email_does_not_claim_existing_vk_only_user(self):
        user = User.objects.create_user(
            username="reader_vk",
            email="reader@example.test",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        original_username = user.username
        VkAccount.objects.create(
            user=user,
            vk_id=12345,
            username="reader_vk",
            email="reader@example.test",
        )

        response = self.post_json(
            "/api/auth/register/",
            {
                "username": "reader",
                "email": "reader@example.test",
                "password": "StrongPass123!",
                "privacy_accepted": True,
            },
        )

        payload = response.json()
        self.assertEqual(response.status_code, 400)
        self.assertIn("уже существует", payload["error"])
        user.refresh_from_db()
        self.assertEqual(user.username, original_username)
        self.assertFalse(user.has_usable_password())
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(VkAccount.objects.get(vk_id=12345).user_id, user.id)


@override_settings(VK_APP_ID="54434029", VK_OIDC_JWKS_URL="")
class VkIdAuthPayloadTests(SimpleTestCase):
    def test_vk_id_user_info_access_token_is_accepted(self):
        with patch(
            "users.service._fetch_vk_id_json",
            return_value={
                "user": {
                    "user_id": "12345",
                    "screen_name": "reader_vk",
                    "email": "reader@example.test",
                    "phone": "+79991234567",
                    "first_name": "Reader",
                    "last_name": "One",
                    "avatar": "https://example.test/avatar.jpg",
                }
            },
        ):
            vk_user = user_service._authenticate_vk_payload({"access_token": "access-token"})

        self.assertEqual(vk_user["vk_id"], 12345)
        self.assertEqual(vk_user["screen_name"], "reader_vk")
        self.assertEqual(vk_user["email"], "reader@example.test")
        self.assertEqual(vk_user["phone"], "+79991234567")
        self.assertEqual(vk_user["avatar_url"], "https://example.test/avatar.jpg")

    def test_vk_id_user_info_rejects_verified_id_token_mismatch(self):
        with override_settings(VK_OIDC_JWKS_URL="https://vk.example.test/jwks"), patch(
            "users.service._parse_vk_id_token",
            return_value={
                "vk_id": 11111,
                "screen_name": "",
                "email": "",
                "phone": "",
                "first_name": "",
                "last_name": "",
                "avatar_url": "",
            },
        ), patch(
            "users.service._fetch_vk_id_json",
            return_value={
                "user": {
                    "user_id": "22222",
                    "first_name": "Reader",
                }
            },
        ):
            with self.assertRaisesMessage(ValueError, "vk auth mismatch"):
                user_service._authenticate_vk_payload(
                    {
                        "access_token": "access-token",
                        "id_token": "id-token",
                    }
                )

    def test_vk_id_public_info_fallback_accepts_id_token_without_local_jwks(self):
        with (
            patch("users.service._parse_vk_id_token", return_value=None),
            patch(
                "users.service._fetch_vk_id_json",
                return_value={
                    "user": {
                        "user_id": "12345",
                        "first_name": "Reader",
                        "last_name": "One",
                    }
                },
            ),
        ):
            vk_user = user_service._authenticate_vk_payload({"id_token": "id-token"})

        self.assertEqual(vk_user["vk_id"], 12345)
        self.assertEqual(vk_user["first_name"], "Reader")
        self.assertEqual(vk_user["last_name"], "One")
