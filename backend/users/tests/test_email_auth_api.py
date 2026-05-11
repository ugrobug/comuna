import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import SiteUserProfile, VkAccount


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
