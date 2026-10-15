import io
import json
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase, TestCase, override_settings

from communities.models import Comun
from feeds.models import Author, Post
from telegram_integration import bot, polling
from telegram_integration.channel_access import (
    TelegramAccessCheckUnavailable,
    TelegramChannelAccessVerifier,
)


def response(payload):
    return io.BytesIO(json.dumps(payload).encode())


class ChannelAccessTests(SimpleTestCase):
    def verifier(self, opener, identity=lambda: 123):
        return TelegramChannelAccessVerifier("secret-test-token", identity, opener=opener)

    def test_transient_errors_are_retryable_and_do_not_expose_token(self):
        for error in [URLError("timeout"), TimeoutError(), ValueError("invalid JSON")]:
            with self.subTest(error=type(error).__name__):
                with self.assertRaises(TelegramAccessCheckUnavailable) as raised:
                    self.verifier(Mock(side_effect=error)).is_admin(-100123)
                self.assertNotIn("secret-test-token", str(raised.exception))

    def test_http_denial_is_distinct_from_rate_limit_and_server_errors(self):
        for code in [400, 403, 429, 500, 502]:
            with self.subTest(code=code):
                error = HTTPError("https://api.test", code, "error", {},
                                  response({"ok": False, "error_code": code}))
                verifier = self.verifier(Mock(side_effect=error))
                if code in {400, 403}:
                    self.assertFalse(verifier.is_admin(-100123))
                else:
                    with self.assertRaises(TelegramAccessCheckUnavailable):
                        verifier.is_admin(-100123)

    def test_membership_status_controls_access_without_requiring_write_permission(self):
        for status in ["administrator", "creator", "member", "left", "kicked", "restricted"]:
            with self.subTest(status=status):
                opener = Mock(return_value=response({"ok": True, "result": {
                    "status": status, "can_post_messages": False}}))
                self.assertEqual(self.verifier(opener).is_admin(-100123),
                                 status in {"administrator", "creator"})
                self.assertEqual(opener.call_count, 1)
                self.assertEqual(opener.call_args.kwargs["timeout"], 5)

    def test_missing_identity_does_not_request_membership(self):
        opener = Mock()
        with self.assertRaises(TelegramAccessCheckUnavailable):
            self.verifier(opener, identity=lambda: None).is_admin(-100123)
        opener.assert_not_called()

    def test_incomplete_response_is_not_acknowledged(self):
        for payload in [None, [], {}, {"ok": True}, {"ok": True, "result": {}}]:
            with self.subTest(payload=payload):
                with self.assertRaises(TelegramAccessCheckUnavailable):
                    self.verifier(Mock(return_value=response(payload))).is_admin(-100123)


@override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_USE_POLLING=False)
class ChannelAccessDeliveryTests(TestCase):
    def test_permission_timeout_is_replayed_and_published_once(self):
        author = Author.objects.create(username="access-retry")
        comun = Comun.objects.create(name="Access retry", slug="access-retry", telegram_source_author=author)
        message = {"chat": {"id": -100123, "username": author.username},
                   "message_id": 235, "text": "Public channel post"}
        updates = [{"update_id": 100, "channel_post": message}]
        processor = polling.TelegramUpdateProcessor()
        processor.offset = 100
        opener = Mock(side_effect=[URLError("timeout"),
                                   response({"ok": True, "result": {"status": "administrator"}})])
        verifier = TelegramChannelAccessVerifier("test-token", lambda: 123, opener=opener)
        with patch.object(bot, "TelegramChannelAccessVerifier", return_value=verifier), \
                patch.object(bot, "_refresh_author_from_telegram"), \
                patch("communities.service._ensure_telegram_channel_comun_for_author", return_value=comun), \
                patch("feeds.views._maybe_notify_new_author"), \
                patch("feeds.views._extract_photo_url", return_value=None):
            with self.assertRaises(TelegramAccessCheckUnavailable):
                processor.process(updates)
            self.assertEqual(processor.offset, 100)
            self.assertFalse(Post.objects.filter(author=author).exists())
            processor.process(updates)
            processor.process(updates)
        self.assertEqual(processor.offset, 101)
        self.assertEqual(Post.objects.filter(author=author, message_id=235).count(), 1)
        self.assertEqual(opener.call_count, 2)

    def test_confirmed_removal_does_not_block_following_updates(self):
        author = Author.objects.create(username="access-removed")
        opener = Mock(return_value=response({"ok": True, "result": {"status": "left"}}))
        verifier = TelegramChannelAccessVerifier("test-token", lambda: 123, opener=opener)
        processor = polling.TelegramUpdateProcessor()
        with patch.object(bot, "TelegramChannelAccessVerifier", return_value=verifier):
            processor.process([{"update_id": 100, "channel_post": {
                "chat": {"id": -100123, "username": author.username},
                "message_id": 235, "text": "Public channel post"}}])
        self.assertEqual(processor.offset, 101)
        self.assertFalse(Post.objects.filter(author=author).exists())


@override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_USE_POLLING=False)
class ForwardedChannelAccessTests(SimpleTestCase):
    """Permission failures must never be presented as a confirmed removal."""

    def forward(self):
        return {
            "chat": {"id": 321, "type": "private"},
            "forward_origin": {"type": "channel", "message_id": 7,
                               "chat": {"id": -100123, "type": "channel", "username": "test_channel"}},
            "text": "Forwarded post",
        }

    def test_identity_transport_failure_is_sanitized(self):
        for error in (TimeoutError("secret-test-token"), URLError("secret-test-token")):
            with self.subTest(error=type(error).__name__):
                opener = Mock()
                verifier = TelegramChannelAccessVerifier(
                    "secret-test-token", Mock(side_effect=error), opener=opener,
                )
                with self.assertRaises(TelegramAccessCheckUnavailable) as raised:
                    verifier.is_admin(-100123)
                self.assertNotIn("secret-test-token", str(raised.exception))
                opener.assert_not_called()

    def test_temporary_failure_does_not_claim_bot_is_not_admin_or_import_post(self):
        errors = [URLError("timeout"), TimeoutError(),
                  HTTPError("https://api.test", 429, "limited", {},
                            response({"ok": False, "error_code": 429})),
                  HTTPError("https://api.test", 503, "unavailable", {},
                            response({"ok": False, "error_code": 503}))]
        for error in errors:
            with self.subTest(error=type(error).__name__):
                opener = Mock(side_effect=error)
                verifier = TelegramChannelAccessVerifier("test-token", lambda: 123, opener=opener)
                with patch.object(bot, "TelegramChannelAccessVerifier", return_value=verifier), \
                        patch.object(bot, "_send_bot_message") as send, \
                        patch.object(bot, "_handle_channel_post") as publish:
                    bot._handle_private_message(self.forward())
                publish.assert_not_called()
                send.assert_called_once()
                self.assertIn("Не удалось связаться с Telegram", send.call_args.args[1])
                self.assertNotIn("Бот не является админом", send.call_args.args[1])
                self.assertNotIn("Пост добавлен", send.call_args.args[1])
                self.assertEqual(opener.call_count, 1)

    def test_confirmed_non_admin_has_different_message_and_no_import(self):
        verifier = TelegramChannelAccessVerifier("test-token", lambda: 123,
            opener=Mock(return_value=response({"ok": True, "result": {"status": "left"}})))
        with patch.object(bot, "TelegramChannelAccessVerifier", return_value=verifier), \
                patch.object(bot, "_send_bot_message") as send, \
                patch.object(bot, "_handle_channel_post") as publish:
            bot._handle_private_message(self.forward())
        publish.assert_not_called()
        send.assert_called_once()
        self.assertIn("не подтвердил права администратора", send.call_args.args[1])
        self.assertNotIn("Не удалось связаться", send.call_args.args[1])

    def test_bot_adapter_uses_verified_membership_even_for_forwarded_post(self):
        with patch.object(bot, "_get_bot_id", return_value=123), \
                patch.object(bot, "TelegramChannelAccessVerifier") as verifier:
            verifier.return_value.is_admin.side_effect = TelegramAccessCheckUnavailable("temporary")
            with self.assertRaises(TelegramAccessCheckUnavailable):
                bot._is_bot_admin(-100123, "test-token")
            self.assertEqual(verifier.call_args.args[1](), 123)
            verifier.return_value.is_admin.assert_called_once_with(-100123)


@override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_USE_POLLING=False)
class ForwardedChannelImportTests(TestCase):
    def test_confirmed_admin_can_import_and_repeat_does_not_duplicate_post(self):
        author = Author.objects.create(username="forward-admin", channel_id=-100123)
        comun = Comun.objects.create(name="Forward admin", slug="forward-admin", telegram_source_author=author)
        message = {
            "chat": {"id": 321, "type": "private"},
            "forward_origin": {"type": "channel", "message_id": 7,
                               "chat": {"id": -100123, "type": "channel", "username": author.username}},
            "text": "Forwarded post",
        }
        opener = Mock(side_effect=lambda *a, **kw: response({
            "ok": True, "result": {"status": "administrator", "can_post_messages": False}}))
        verifier = TelegramChannelAccessVerifier("test-token", lambda: 123, opener=opener)
        with patch.object(bot, "TelegramChannelAccessVerifier", return_value=verifier), \
                patch.object(bot, "_refresh_author_from_telegram"), \
                patch.object(bot, "_send_bot_message") as send, \
                patch.object(bot, "_send_bot_message_with_keyboard") as confirm_update, \
                patch("communities.service._ensure_telegram_channel_comun_for_author", return_value=comun), \
                patch("feeds.views._maybe_notify_new_author"), \
                patch("feeds.views._extract_photo_url", return_value=None):
            bot._handle_private_message(message)
            self.assertEqual(opener.call_count, 2)  # Forward check and existing import check.
            self.assertEqual(send.call_args.args[1], "Пост добавлен на сайт.")
            bot._handle_private_message(message)
        self.assertEqual(opener.call_count, 3)
        confirm_update.assert_called_once()
        self.assertEqual(Post.objects.filter(author=author, message_id=7).count(), 1)
