from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from my_feed.models import UserFeedSettings
from users import service as user_service


User = get_user_model()


class AuthBootstrapApiTests(TestCase):
    def test_requires_authentication(self):
        response = self.client.get(reverse("auth-bootstrap"))

        self.assertEqual(response.status_code, 401)

    def test_returns_user_and_first_paint_settings(self):
        user = User.objects.create_user(username="bootstrap-reader")
        UserFeedSettings.objects.create(
            user=user,
            home_feed="mine",
            interface_language="en",
            interface_language_manual=True,
        )
        token = user_service._issue_token(user)

        response = self.client.get(
            reverse("auth-bootstrap"),
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(payload["user"]["id"], user.id)
        self.assertEqual(payload["settings"]["home_feed"], "mine")
        self.assertEqual(payload["settings"]["interface_language"], "en")
        self.assertTrue(payload["settings"]["interface_language_manual"])
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")
