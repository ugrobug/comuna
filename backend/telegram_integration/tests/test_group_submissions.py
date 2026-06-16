from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from communities.models import Comun, ComunGlossaryTerm, ComunKnowledgeBaseItem, ComunTelegramSubmission
from feeds.models import Post
from notifications.models import SiteNotification
from telegram_integration import bot as telegram_bot
from telegram_integration.models import TelegramAccount
from users import service as user_service

User = get_user_model()


class TelegramGroupSubmissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner")
        self.comun = Comun.objects.create(
            name="Test Community",
            slug="test-community",
            creator=self.owner,
            glossary_enabled=True,
            knowledge_base_enabled=True,
        )
        TelegramAccount.objects.create(
            user=self.owner,
            telegram_id=111,
            username="owner_tg",
        )

    def test_group_moderator_can_link_chat_to_comun(self):
        message = {
            "message_id": 10,
            "chat": {"id": -1001, "type": "supergroup", "title": "Chat"},
            "from": {"id": 111, "username": "owner_tg"},
            "text": "/link_comun test-community",
        }

        with patch.object(telegram_bot, "_send_bot_message") as send_mock:
            telegram_bot._handle_message(message)

        self.comun.refresh_from_db()
        self.assertEqual(self.comun.telegram_chat_id, -1001)
        self.assertEqual(self.comun.telegram_chat_title, "Chat")
        self.assertTrue(send_mock.called)

    def test_reply_command_creates_glossary_submission_and_notifies_team(self):
        self.comun.telegram_chat_id = -1001
        self.comun.telegram_chat_title = "Chat"
        self.comun.save(update_fields=["telegram_chat_id", "telegram_chat_title", "updated_at"])
        message = {
            "message_id": 11,
            "chat": {"id": -1001, "type": "supergroup", "title": "Chat"},
            "from": {"id": 111, "username": "owner_tg"},
            "text": "в гласарий",
            "reply_to_message": {
                "message_id": 77,
                "from": {"id": 222, "first_name": "User"},
                "text": "Термин — Значение термина",
            },
        }

        with (
            patch.object(telegram_bot, "_send_bot_message") as send_mock,
            patch("notifications.service.send_site_notification_to_push"),
        ):
            telegram_bot._handle_message(message)

        submission = ComunTelegramSubmission.objects.get()
        self.assertEqual(submission.comun, self.comun)
        self.assertEqual(submission.request_type, ComunTelegramSubmission.TYPE_GLOSSARY)
        self.assertEqual(submission.glossary_term, "Термин")
        self.assertEqual(submission.glossary_definition, "Значение термина")
        self.assertEqual(submission.telegram_source_message_id, 77)
        self.assertTrue(send_mock.called)
        self.assertTrue(
            SiteNotification.objects.filter(
                user=self.owner,
                event_key="comun_telegram_submission",
                payload__submission_id=submission.id,
            ).exists()
        )

    def test_moderator_can_approve_glossary_submission(self):
        submission = ComunTelegramSubmission.objects.create(
            comun=self.comun,
            request_type=ComunTelegramSubmission.TYPE_GLOSSARY,
            telegram_chat_id=-1001,
            telegram_source_message_id=77,
            source_text="Термин — Значение",
            glossary_term="Термин",
            glossary_definition="Значение",
        )
        token = user_service._issue_token(self.owner)

        response = self.client.patch(
            reverse(
                "comun-telegram-submission-detail",
                kwargs={"slug": self.comun.slug, "submission_id": submission.id},
            ),
            data={"action": "approve"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        submission.refresh_from_db()
        self.assertEqual(submission.status, ComunTelegramSubmission.STATUS_APPROVED)
        self.assertTrue(
            ComunGlossaryTerm.objects.filter(
                comun=self.comun,
                term="Термин",
                definition="Значение",
            ).exists()
        )

    def test_moderator_can_approve_knowledge_base_submission(self):
        submission = ComunTelegramSubmission.objects.create(
            comun=self.comun,
            request_type=ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE,
            telegram_chat_id=-1001,
            telegram_source_message_id=88,
            source_text="Полезный ответ\nВторая строка",
            title="Полезный ответ",
        )
        token = user_service._issue_token(self.owner)

        response = self.client.patch(
            reverse(
                "comun-telegram-submission-detail",
                kwargs={"slug": self.comun.slug, "submission_id": submission.id},
            ),
            data={"action": "approve", "title": "FAQ из чата"},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200)
        submission.refresh_from_db()
        self.assertEqual(submission.status, ComunTelegramSubmission.STATUS_APPROVED)
        self.assertIsNotNone(submission.created_post_id)
        self.assertTrue(
            Post.objects.filter(
                id=submission.created_post_id,
                raw_data__source="manual_comun",
                raw_data__comun_slug=self.comun.slug,
            ).exists()
        )
        self.assertTrue(
            ComunKnowledgeBaseItem.objects.filter(
                comun=self.comun,
                post_id=submission.created_post_id,
                title="FAQ из чата",
            ).exists()
        )
