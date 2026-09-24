from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings

from telegram_integration import bot, polling
from telegram_integration.models import BotSession
from users.models import AuthorAdmin, AuthorVerificationCode
from feeds.models import Author
from communities.models import Comun


User = get_user_model()


@override_settings(TELEGRAM_BOT_TOKEN="")
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

    @patch("telegram_integration.bot._send_bot_message")
    def test_verified_user_is_attached_when_channel_connects(
        self,
        send_message,
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
        self.assertFalse(Comun.objects.exists())
        send_message.assert_called_once()
        self.assertIn("сначала создайте сообщество на сайте", send_message.call_args.args[1])


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


class TelegramUpdateProcessorTests(SimpleTestCase):
    @patch("telegram_integration.polling._handle_channel_post")
    def test_failure_keeps_cursor_at_failed_update(self, handler):
        processor = polling.TelegramUpdateProcessor()
        updates = [{"update_id": i, "channel_post": {"message_id": i}} for i in (10, 11, 12)]
        handler.side_effect = [None, RuntimeError("temporary")]
        with self.assertRaises(RuntimeError):
            processor.process(updates)
        self.assertEqual(processor.offset, 11)
        handler.reset_mock(side_effect=True)
        processor.process(updates)
        self.assertEqual([c.args[0]["message_id"] for c in handler.call_args_list], [11, 12])
        self.assertEqual(processor.offset, 13)

    @patch("telegram_integration.polling.time.sleep", side_effect=KeyboardInterrupt)
    @patch("telegram_integration.polling._fetch_telegram_json", return_value=None)
    def test_startup_preserves_pending_updates(self, fetch, sleep):
        with self.assertRaises(KeyboardInterrupt):
            polling._polling_loop("test-token")
        self.assertEqual(fetch.call_args_list[0].args, (
            "deleteWebhook", "test-token", {"drop_pending_updates": False}))
        self.assertFalse(polling._polling_started)
