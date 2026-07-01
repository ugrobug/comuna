from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from users import chat_service
from users.models import SiteChatMessage
from users.service import _issue_token

User = get_user_model()


class SiteChatApiTests(TestCase):
    def setUp(self):
        self.sender = User.objects.create_user(
            username="sender",
            email="sender@example.com",
            password="password",
        )
        self.recipient = User.objects.create_user(
            username="recipient",
            email="recipient@example.com",
            password="password",
        )
        self.sender_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.sender)}"}
        self.recipient_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.recipient)}"}

    def test_message_delivery_and_read_statuses_are_serialized(self):
        chat, _created = chat_service.get_or_create_chat_for_users(self.sender, self.recipient)

        response = self.client.post(
            reverse("auth-chat-messages", args=[chat.id]),
            data='{"body": "hello"}',
            content_type="application/json",
            **self.sender_headers,
        )

        self.assertEqual(response.status_code, 200)
        sent_payload = response.json()["message"]
        self.assertIsNotNone(sent_payload["delivered_at"])
        self.assertIsNone(sent_payload["read_at"])

        message = SiteChatMessage.objects.get(id=sent_payload["id"])
        self.assertIsNotNone(message.delivered_at)
        self.assertIsNone(message.read_at)

        response = self.client.get(reverse("auth-chat-detail", args=[chat.id]), **self.recipient_headers)

        self.assertEqual(response.status_code, 200)
        recipient_message = response.json()["messages"][0]
        self.assertEqual(recipient_message["id"], message.id)
        self.assertIsNotNone(recipient_message["delivered_at"])
        self.assertIsNotNone(recipient_message["read_at"])

        message.refresh_from_db()
        self.assertIsNotNone(message.read_at)

        response = self.client.get(reverse("auth-chat-detail", args=[chat.id]), **self.sender_headers)

        self.assertEqual(response.status_code, 200)
        sender_message = response.json()["messages"][0]
        self.assertEqual(sender_message["id"], message.id)
        self.assertIsNotNone(sender_message["delivered_at"])
        self.assertIsNotNone(sender_message["read_at"])
