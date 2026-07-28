from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from communities.models import Comun, ComunGlossaryTerm, ComunKnowledgeBaseItem, ComunTelegramSubmission
from feeds.models import Author, Post
from notifications.models import SiteNotification
from telegram_integration import bot as telegram_bot
from telegram_integration.models import BotSession, TelegramAccount
from users import service as user_service

User = get_user_model()


class TelegramGroupCommandParsingTests(SimpleTestCase):
    def test_inline_result_text_is_not_treated_as_submission_command(self):
        self.assertEqual(
            telegram_bot._submission_type_from_text(
                "Как использовать глоссарий?\n\n"
                "Каждое сообщество может включить глоссарий и базу знаний."
            ),
            "",
        )

    def test_explicit_submission_phrases_are_supported(self):
        self.assertEqual(
            telegram_bot._submission_type_from_text("добавить в глоссарий"),
            ComunTelegramSubmission.TYPE_GLOSSARY,
        )
        self.assertEqual(
            telegram_bot._submission_type_from_text("в базу знаний"),
            ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE,
        )


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

    def test_group_chat_cannot_be_linked_to_second_comun(self):
        self.comun.telegram_chat_id = -1001
        self.comun.telegram_chat_title = "Chat"
        self.comun.save(update_fields=["telegram_chat_id", "telegram_chat_title", "updated_at"])
        second_comun = Comun.objects.create(
            name="Second Community",
            slug="second-community",
            creator=self.owner,
        )
        message = {
            "message_id": 10,
            "chat": {"id": -1001, "type": "supergroup", "title": "Chat"},
            "from": {"id": 111, "username": "owner_tg"},
            "text": "/link_comun second-community",
        }

        with patch.object(telegram_bot, "_send_bot_message") as send_mock:
            telegram_bot._handle_message(message)

        second_comun.refresh_from_db()
        self.assertIsNone(second_comun.telegram_chat_id)
        self.assertIn("уже привязан", send_mock.call_args.args[1])

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

    def test_group_search_remembers_comun_and_opens_inline_search(self):
        self.comun.telegram_chat_id = -1001
        self.comun.telegram_chat_title = "Chat"
        self.comun.save(update_fields=["telegram_chat_id", "telegram_chat_title", "updated_at"])
        message = {
            "message_id": 12,
            "chat": {"id": -1001, "type": "supergroup", "title": "Chat"},
            "from": {"id": 111, "username": "owner_tg"},
            "text": "/search полезный ответ",
        }

        with patch.object(telegram_bot, "_send_bot_message_with_keyboard") as send_mock:
            telegram_bot._handle_message(message)

        session = BotSession.objects.get(telegram_user_id=111)
        self.assertEqual(session.selected_comun, self.comun)
        keyboard = send_mock.call_args.args[2]
        self.assertEqual(
            keyboard["inline_keyboard"][0][0]["switch_inline_query_current_chat"],
            "полезный ответ",
        )

    def test_inline_search_returns_glossary_and_knowledge_base_results(self):
        self.comun.telegram_chat_id = -1001
        self.comun.telegram_chat_title = "Chat"
        self.comun.save(update_fields=["telegram_chat_id", "telegram_chat_title", "updated_at"])
        BotSession.objects.create(telegram_user_id=111, selected_comun=self.comun)
        ComunGlossaryTerm.objects.create(
            comun=self.comun,
            term="API",
            slug="api",
            definition="Интерфейс программирования приложения",
        )
        author = Author.objects.create(username="knowledge-author")
        post = Post.objects.create(
            author=author,
            message_id=501,
            title="Как работать с API",
            content="<p>Полезный материал об API сообщества.</p>",
            is_pending=False,
            is_blocked=False,
        )
        ComunKnowledgeBaseItem.objects.create(
            comun=self.comun,
            post=post,
            item_type=ComunKnowledgeBaseItem.TYPE_POST,
            title=post.title,
        )

        with patch.object(telegram_bot, "_answer_inline_query") as answer_mock:
            telegram_bot._handle_inline_query(
                {
                    "id": "inline-1",
                    "from": {"id": 111, "username": "owner_tg"},
                    "query": "API",
                    "chat_type": "supergroup",
                }
            )

        results = answer_mock.call_args.args[1]
        self.assertEqual({item["id"].split("-", 1)[0] for item in results}, {"glossary", "knowledge"})
        knowledge_result = next(item for item in results if item["id"].startswith("knowledge-"))
        self.assertIn("/b/post/", knowledge_result["input_message_content"]["message_text"])

    def test_forwarded_messages_are_collected_into_one_knowledge_base_submission(self):
        self.comun.telegram_chat_id = -1001
        self.comun.telegram_chat_title = "Chat"
        self.comun.save(update_fields=["telegram_chat_id", "telegram_chat_title", "updated_at"])
        first = {
            "message_id": 30,
            "chat": {"id": 222, "type": "private"},
            "from": {"id": 222, "username": "member"},
            "text": "Первое полезное сообщение",
            "forward_origin": {
                "type": "chat",
                "sender_chat": {"id": -1001, "type": "supergroup", "title": "Chat"},
            },
        }
        second = {
            "message_id": 31,
            "chat": {"id": 222, "type": "private"},
            "from": {"id": 222, "username": "member"},
            "text": "Второе полезное сообщение",
            "forward_origin": {
                "type": "chat",
                "sender_chat": {"id": -1001, "type": "supergroup", "title": "Chat"},
            },
        }

        with (
            patch.object(
                telegram_bot,
                "_send_bot_message_with_keyboard",
                return_value={"ok": True, "result": {"message_id": 90}},
            ),
            patch.object(telegram_bot, "_edit_bot_message_with_keyboard"),
        ):
            telegram_bot._handle_message(first)
            telegram_bot._handle_message(second)

        session = BotSession.objects.get(telegram_user_id=222)
        self.assertEqual(len(session.pending_forward_messages), 2)

        callback = {
            "id": "callback-1",
            "data": "tgforward:kb:30",
            "message": {"message_id": 90, "chat": {"id": 222, "type": "private"}},
        }
        with (
            patch.object(telegram_bot, "_answer_callback_query"),
            patch.object(telegram_bot, "_edit_bot_message_with_keyboard"),
            patch("notifications.service.send_site_notification_to_push"),
        ):
            telegram_bot._handle_callback_query(callback)

        submission = ComunTelegramSubmission.objects.get()
        self.assertEqual(submission.request_type, ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE)
        self.assertIn("Первое полезное сообщение", submission.source_text)
        self.assertIn("Второе полезное сообщение", submission.source_text)
        session.refresh_from_db()
        self.assertEqual(session.pending_forward_messages, [])

    def test_ai_summary_action_is_available_only_when_enabled(self):
        self.comun.telegram_chat_id = -1001
        self.comun.telegram_chat_title = "Chat"
        self.comun.save(update_fields=["telegram_chat_id", "telegram_chat_title", "updated_at"])
        disabled_keyboard = telegram_bot._forward_batch_keyboard(self.comun, 40)
        self.assertFalse(
            any(
                button["callback_data"].startswith("tgforward:sum:")
                for row in disabled_keyboard["inline_keyboard"]
                for button in row
            )
        )

        self.comun.telegram_ai_summary_enabled = True
        self.comun.save(update_fields=["telegram_ai_summary_enabled", "updated_at"])
        enabled_keyboard = telegram_bot._forward_batch_keyboard(self.comun, 40)
        self.assertTrue(
            any(
                button["callback_data"] == "tgforward:sum:40"
                for row in enabled_keyboard["inline_keyboard"]
                for button in row
            )
        )

    def test_ai_summary_creates_pending_knowledge_base_submission(self):
        self.comun.telegram_chat_id = -1001
        self.comun.telegram_chat_title = "Chat"
        self.comun.telegram_ai_summary_enabled = True
        self.comun.save(
            update_fields=[
                "telegram_chat_id",
                "telegram_chat_title",
                "telegram_ai_summary_enabled",
                "updated_at",
            ]
        )
        BotSession.objects.create(
            telegram_user_id=222,
            selected_comun=self.comun,
            pending_forward_comun=self.comun,
            pending_forward_messages=[
                {
                    "private_message_id": 40,
                    "source_message_id": 77,
                    "source_chat_username": "community_chat",
                    "source_author_name": "Участник",
                    "telegram_username": "@member",
                    "text": "Длинное обсуждение решения",
                }
            ],
            pending_forward_action_message_id=91,
            pending_forward_started_at=telegram_bot.timezone.now(),
        )
        callback = {
            "id": "callback-ai",
            "data": "tgforward:sum:40",
            "message": {"message_id": 91, "chat": {"id": 222, "type": "private"}},
        }

        with (
            patch.object(telegram_bot, "_answer_callback_query"),
            patch.object(telegram_bot, "_edit_bot_message_with_keyboard"),
            patch(
                "telegram_integration.ai.summarize_telegram_messages",
                return_value=("Итоги обсуждения", "Команда приняла полезное решение."),
            ),
            patch("notifications.service.send_site_notification_to_push"),
        ):
            telegram_bot._handle_callback_query(callback)

        submission = ComunTelegramSubmission.objects.get()
        self.assertEqual(submission.request_type, ComunTelegramSubmission.TYPE_KNOWLEDGE_BASE)
        self.assertEqual(submission.title, "Итоги обсуждения")
        self.assertEqual(submission.source_text, "Команда приняла полезное решение.")
        self.assertTrue(submission.source_payload["ai_summary"])
