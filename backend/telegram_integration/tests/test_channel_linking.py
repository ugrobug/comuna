import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from communities import service as community_service
from communities.models import Comun
from feeds.models import Author, Post
from telegram_integration import bot
from telegram_integration.models import BotSession
from users.models import AuthorAdmin, AuthorVerificationCode
from users.service import _issue_token


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_USE_POLLING=False)
class WebsiteFirstChannelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="channel-owner")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {_issue_token(self.user)}"
        self.channel = {"id": -100123, "type": "channel", "username": "existing_channel", "title": "Existing channel"}

    def connect_channel(self):
        bot._handle_my_chat_member({
            "chat": self.channel,
            "from": {"id": 123456},
            "new_chat_member": {"status": "administrator"},
        })

    @patch("telegram_integration.bot._send_bot_message")
    def test_old_or_missing_bot_session_never_creates_community(self, send_message):
        for flow in [None, "", "create_comun", "link_existing"]:
            with self.subTest(flow=flow):
                if flow is not None:
                    BotSession.objects.update_or_create(telegram_user_id=123456, defaults={"channel_flow": flow})
                self.connect_channel()
                self.assertFalse(Comun.objects.exists())
                self.assertIn("https://tambur.pub/comuns?create=1", send_message.call_args.args[1])

    def test_channel_posts_wait_for_community(self):
        bot._handle_channel_post({"chat": self.channel, "message_id": 1, "text": "Первый пост"})
        self.assertFalse(Comun.objects.exists())
        self.assertFalse(Post.objects.exists())

    @patch("telegram_integration.bot._send_bot_message")
    def test_forwarded_post_does_not_create_community_or_claim_success(self, send_message):
        bot._handle_private_message({
            "chat": {"id": 123456, "type": "private"},
            "forward_origin": {"type": "channel", "chat": self.channel, "message_id": 1},
            "text": "Пересланный пост",
        })
        self.assertFalse(Comun.objects.exists())
        self.assertFalse(Post.objects.exists())
        self.assertIn("ещё не привязан", send_message.call_args.args[1])

    @patch("telegram_integration.bot._edit_bot_message_with_keyboard")
    @patch("telegram_integration.bot._answer_callback_query")
    def test_stale_create_button_redirects_to_website(self, answer, edit_message):
        session = BotSession.objects.create(telegram_user_id=123456, channel_flow="create_comun")
        bot._handle_callback_query({
            "id": "callback", "data": "channel_flow:create",
            "message": {"chat": {"id": 123456}, "message_id": 9},
        })
        session.refresh_from_db()
        self.assertEqual(session.channel_flow, bot.CHANNEL_FLOW_EXISTING)
        buttons = [button for row in edit_message.call_args.args[3]["inline_keyboard"] for button in row]
        self.assertTrue(any(button.get("url") == "https://tambur.pub/comuns?create=1" for button in buttons))
        self.assertFalse(any(button.get("callback_data") == "channel_flow:create" for button in buttons))
        self.assertFalse(Comun.objects.exists())

    @patch("telegram_integration.bot._send_bot_message")
    def test_old_session_gets_website_first_instructions(self, send_message):
        BotSession.objects.create(telegram_user_id=123456, channel_flow="create_comun", mode_selected=True)
        bot._maybe_send_setup_instructions(123456)
        self.assertIn("1) Создайте сообщество на сайте", send_message.call_args.args[1])
        self.assertNotIn("будет создано одноименное", send_message.call_args.args[1])

    @patch("feeds.views._maybe_notify_new_author")
    @patch("telegram_integration.bot._send_bot_message")
    def test_create_on_site_then_verify_link_and_import(self, send_message, notify_author):
        response = self.client.post(reverse("comuns-list-create"),
            data=json.dumps({"name": "Сообщество на сайте"}), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        comun = Comun.objects.get(slug=response.json()["comun"]["slug"])
        response = self.client.patch(reverse("comun-detail-manage", kwargs={"slug": comun.slug}),
            data=json.dumps({"telegram_channel_username": self.channel["username"]}), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        code = AuthorVerificationCode.objects.create(user=self.user, code="COMUNA-WEBSITE-FIRST")
        bot._handle_verification_code(123456, code.code)
        self.connect_channel()
        comun.refresh_from_db()
        author = Author.objects.get(username=self.channel["username"])
        self.assertEqual(comun.telegram_source_author_id, author.pk)
        self.assertEqual(comun.creator_id, self.user.pk)
        self.assertEqual(Comun.objects.count(), 1)
        self.assertIn("привязан к сообществу", send_message.call_args.args[1])
        bot._handle_channel_post({"chat": self.channel, "message_id": 1, "text": "Первый пост в сообществе"})
        post = Post.objects.get(author=author, message_id=1)
        self.assertTrue(community_service._post_belongs_to_comun(comun, post))
        self.assertEqual(Comun.objects.count(), 1)

    def test_pending_link_requires_verified_community_team_member(self):
        stranger = get_user_model().objects.create_user(username="stranger")
        author = Author.objects.create(username=self.channel["username"], channel_id=-100123)
        comun = Comun.objects.create(name="Чужое сообщество", slug="other", creator=stranger,
            telegram_channel_username=author.username)
        AuthorAdmin.objects.create(user=self.user, author=author, verified_at=timezone.now())
        self.assertIsNone(community_service._ensure_telegram_channel_comun_for_author(author))
        comun.refresh_from_db()
        self.assertIsNone(comun.telegram_source_author_id)
        self.assertEqual(comun.creator_id, stranger.pk)
        self.assertEqual(Comun.objects.count(), 1)
