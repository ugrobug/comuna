from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from telegram_integration import bot, polling
from telegram_integration.models import BotSession
from users.models import AuthorAdmin, AuthorVerificationCode
from feeds.models import Author


User = get_user_model()


class TelegramBotVerificationTests(TestCase):
    @patch("telegram_integration.bot._send_bot_message")
    def test_verification_code_can_be_saved_before_channel_is_connected(self, send_message):
        user = User.objects.create_user(username="reader")
        record = AuthorVerificationCode.objects.create(user=user, code="COMUNA-TEST")

        bot._handle_verification_code(123456, "COMUNA-TEST")

        session = BotSession.objects.get(telegram_user_id=123456)
        record.refresh_from_db()

        self.assertEqual(session.verified_user_id, user.id)
        self.assertIsNotNone(record.used_at)
        send_message.assert_called_once()
        self.assertIn("Код подтверждения принят", send_message.call_args.args[1])

    @patch("telegram_integration.bot.community_service._ensure_telegram_channel_comun_for_author")
    @patch("telegram_integration.bot._send_bot_message")
    def test_verified_user_is_attached_when_channel_connects(
        self,
        send_message,
        ensure_comun,
    ):
        user = User.objects.create_user(username="reader")
        BotSession.objects.create(
            telegram_user_id=123456,
            verified_user_id=user.id,
            channel_flow=bot.CHANNEL_FLOW_EXISTING,
            auto_publish=True,
        )

        bot._handle_my_chat_member(
            {
                "chat": {
                    "id": -100123,
                    "type": "channel",
                    "username": "unit_channel",
                    "title": "Unit channel",
                },
                "from": {"id": 123456},
                "new_chat_member": {"status": "administrator"},
            }
        )

        author = Author.objects.get(username="unit_channel")
        link = AuthorAdmin.objects.get(user=user, author=author)

        self.assertEqual(author.admin_chat_id, 123456)
        self.assertEqual(link.telegram_user_id, 123456)
        self.assertIsNotNone(link.verified_at)
        ensure_comun.assert_called_once_with(author)
        send_message.assert_called_once()
        self.assertIn("настройки нужного сообщества", send_message.call_args.args[1])


@override_settings(TELEGRAM_BOT_TOKEN="token")
class TelegramPollingTests(TestCase):
    def tearDown(self):
        polling._polling_started = False
        polling._polling_lock_handle = None
        super().tearDown()

    @patch("telegram_integration.polling.threading.Thread")
    @patch("telegram_integration.polling._acquire_polling_lock", return_value=False)
    def test_start_polling_thread_skips_when_lock_not_acquired(self, acquire_lock, thread_cls):
        polling._polling_started = False

        polling.start_polling_thread()

        acquire_lock.assert_called_once()
        thread_cls.assert_not_called()
        self.assertFalse(polling._polling_started)
