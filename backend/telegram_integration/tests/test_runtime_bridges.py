from django.test import SimpleTestCase

from telegram_integration import bot as telegram_bot
from telegram_integration import serializers as telegram_serializers
from telegram_integration import service as telegram_service
from telegram_integration import views as telegram_views
from users import service as user_service
from users import views as user_views


class TelegramIntegrationRuntimeBridgeTests(SimpleTestCase):
    def test_users_runtime_bridges_telegram_auth(self):
        self.assertIs(user_views.telegram_auth, telegram_views.telegram_auth)
        self.assertIs(user_service._validate_telegram_login, telegram_service.validate_telegram_login)
        self.assertIs(user_service._upsert_telegram_account, telegram_service.upsert_telegram_account)
        self.assertIs(
            user_service._build_telegram_login_redirect_html,
            telegram_service.build_telegram_login_redirect_html,
        )

    def test_telegram_views_use_telegram_bot_runtime(self):
        self.assertIs(telegram_views._handle_channel_post, telegram_bot._handle_channel_post)
        self.assertIs(telegram_views._handle_message, telegram_bot._handle_message)
        self.assertIs(telegram_views._handle_callback_query, telegram_bot._handle_callback_query)
        self.assertIs(telegram_views._handle_my_chat_member, telegram_bot._handle_my_chat_member)

    def test_telegram_views_use_telegram_serializers(self):
        payload = telegram_serializers._serialize_telegram_auth_response.__name__
        self.assertEqual(payload, "_serialize_telegram_auth_response")
