from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from communities.models import Comun
from feeds.models import Author, Post
from telegram_integration import bot
from telegram_integration.models import BotSession, TelegramApprovalDelivery
from telegram_integration.moderation import TelegramApprovalPrompt
from users.models import AuthorVerificationCode
from telegram_integration.channel_identity import TelegramChannelIdentity
from telegram_integration.verification import TelegramChannelVerification


@override_settings(TELEGRAM_USE_POLLING=False, TELEGRAM_BOT_TOKEN='test-token')
class ChannelReliabilityTests(TestCase):
    def setUp(self):
        self.author = Author.objects.create(username='reliable', channel_id=-100123, admin_chat_id=123)
        self.comun = Comun.objects.create(name='Reliable', slug='reliable', telegram_source_author=self.author)
        self.chat = {'id': -100123, 'type': 'channel', 'username': 'reliable'}
        for target, kwargs in [
            ('telegram_integration.bot._is_bot_admin', {'return_value': True}),
            ('telegram_integration.bot._refresh_author_from_telegram', {}),
            ('telegram_integration.bot._send_bot_message', {}),
            ('telegram_integration.bot._answer_callback_query', {}),
            ('feeds.views._maybe_notify_new_author', {}),
        ]:
            p = patch(target, **kwargs)
            p.start()
            self.addCleanup(p.stop)

    def forward(self, actor=123):
        return {'chat': {'id': actor, 'type': 'private'}, 'from': {'id': actor},
                'text': 'Example', 'forward_origin': {'type': 'channel', 'chat': self.chat, 'message_id': 1}}

    def callback(self, data, actor=123):
        return {'id': 'callback', 'from': {'id': actor}, 'data': data,
                'message': {'message_id': 20, 'chat': {'id': actor, 'type': 'private'}}}

    def test_channel_rename_keeps_original_author_and_community(self):
        renamed = {**self.chat, 'username': 'renamed_channel'}
        post = bot._handle_channel_post({'chat': renamed, 'message_id': 1, 'text': 'Example'})
        self.assertIsNotNone(post)
        self.assertEqual(post.author_id, self.author.pk)
        self.assertEqual(Author.objects.count(), 1)

    def test_foreign_forward_cannot_claim_channel_or_import(self):
        BotSession.objects.create(telegram_user_id=999)
        with patch('telegram_integration.bot.TelegramChannelAccessVerifier') as access:
            access.return_value.is_admin.return_value = False
            bot._handle_private_message(self.forward(999))
        self.assertFalse(Post.objects.exists())
        self.author.refresh_from_db()
        self.assertEqual(self.author.admin_chat_id, 123)

    def test_consent_enabled_during_media_preparation_is_applied_to_new_post(self):
        def prepare(*args):
            Author.objects.filter(pk=self.author.pk).update(auto_publish=False, publish_delay_days=3)
            return None
        with patch('feeds.views._extract_photo_url', side_effect=prepare), \
                patch.object(bot, '_send_bot_message_with_keyboard', return_value={'ok': True, 'result': {'message_id': 99}}):
            post = bot._handle_channel_post({'chat': self.chat, 'message_id': 1, 'text': 'Example'})
        self.assertTrue(post.is_pending)
        self.assertGreater(post.publish_at, timezone.now() + timedelta(days=2))

    def test_blocking_channel_during_preparation_prevents_post_creation(self):
        def prepare(*args):
            Author.objects.filter(pk=self.author.pk).update(is_blocked=True)
            return None
        with patch('feeds.views._extract_photo_url', side_effect=prepare):
            post = bot._handle_channel_post({'chat': self.chat, 'message_id': 1, 'text': 'Example'})
        self.assertIsNone(post)
        self.assertFalse(Post.objects.exists())

    def test_stale_selected_channel_cannot_change_mode_after_owner_change(self):
        BotSession.objects.create(telegram_user_id=999, selected_author=self.author)
        bot._handle_callback_query(self.callback(f'mode:approval:{self.author.pk}', 999))
        self.author.refresh_from_db()
        self.assertTrue(self.author.auto_publish)

    def test_old_button_for_first_channel_never_changes_currently_selected_second_channel(self):
        second = Author.objects.create(username='second', admin_chat_id=123)
        BotSession.objects.create(telegram_user_id=123, selected_author=second)
        bot._handle_callback_query(self.callback(f'mode:approval:{self.author.pk}'))
        self.author.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(self.author.auto_publish)
        self.assertTrue(second.auto_publish)

    def test_legacy_unbound_settings_button_requires_new_selection(self):
        BotSession.objects.create(telegram_user_id=123, selected_author=self.author)
        bot._handle_callback_query(self.callback('mode:approval'))
        self.author.refresh_from_db()
        self.assertTrue(self.author.auto_publish)

    def test_other_actor_cannot_use_private_settings_callback(self):
        callback = self.callback(f'mode:approval:{self.author.pk}')
        callback['from']['id'] = 999
        bot._handle_callback_query(callback)
        self.author.refresh_from_db()
        self.assertTrue(self.author.auto_publish)

    def test_setup_mode_without_selected_channel_remains_available(self):
        bot._handle_callback_query(self.callback('mode:approval'))
        self.assertFalse(BotSession.objects.get(telegram_user_id=123).auto_publish)

    def test_reused_username_cannot_take_over_existing_source(self):
        author = TelegramChannelIdentity().resolve({**self.chat, 'id': -100999})
        self.assertIsNone(author)
        self.author.refresh_from_db()
        self.assertEqual(self.author.channel_id, -100123)

    def test_duplicate_chat_ids_are_not_resolved_arbitrarily(self):
        other = Author.objects.create(username='duplicate', channel_id=-100123)
        Comun.objects.create(name='Other', slug='other', telegram_source_author=other)
        self.assertIsNone(TelegramChannelIdentity().resolve({**self.chat, 'username': 'renamed'}))

    def test_legacy_duplicates_preserve_existing_exact_route(self):
        other = Author.objects.create(username='duplicate', channel_id=-100123)
        Comun.objects.create(name='Other', slug='other', telegram_source_author=other)
        self.assertEqual(TelegramChannelIdentity().resolve(self.chat).pk, self.author.pk)

    def test_renamed_source_prefers_unique_existing_community_over_unlinked_alias(self):
        Author.objects.create(username='duplicate', channel_id=-100123)
        self.assertEqual(TelegramChannelIdentity().resolve({**self.chat, 'username': 'renamed'}).pk, self.author.pk)

    def test_expired_verification_code_is_not_accepted(self):
        user = get_user_model().objects.create_user(username='expired-code-owner')
        code = AuthorVerificationCode.objects.create(user=user, code='COMUNA-EXPIRED')
        AuthorVerificationCode.objects.filter(pk=code.pk).update(created_at=timezone.now() - timedelta(days=2))
        bot._handle_verification_code(123, code.code)
        self.assertFalse(BotSession.objects.filter(telegram_user_id=123, verified_user_id=user.pk).exists())

    def test_failed_approval_prompt_is_retried_for_existing_post(self):
        self.author.auto_publish = False
        self.author.save(update_fields=['auto_publish'])
        message = {'chat': self.chat, 'message_id': 1, 'text': 'Example'}
        with patch.object(bot, '_send_bot_message_with_keyboard', side_effect=[None, {'ok': True, 'result': {'message_id': 99}}]) as send:
            try:
                bot._handle_channel_post(message)
            except RuntimeError:
                pass
            TelegramApprovalDelivery.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
            TelegramApprovalPrompt(send).drain()
            self.assertEqual(send.call_count, 2)
        self.assertEqual(Post.objects.count(), 1)
        self.assertTrue(Post.objects.get().is_pending)

    def test_delivered_prompt_survives_replay_edit_and_album_extension(self):
        self.author.auto_publish = False
        self.author.save(update_fields=['auto_publish'])
        message = {'chat': self.chat, 'message_id': 1, 'text': 'Example'}
        with patch.object(bot, '_send_bot_message_with_keyboard', return_value={'ok': True, 'result': {'message_id': 99}}) as send:
            bot._handle_channel_post(message)
            bot._handle_channel_post({**message, 'text': 'Edited'})
            self.assertEqual(send.call_count, 1)
        post = Post.objects.get()
        self.assertIn('Edited', post.content)
        self.assertEqual(post.telegram_approval_delivery.message_id, 99)

    def test_deleted_post_update_button_does_not_recreate_or_force_publish(self):
        BotSession.objects.create(telegram_user_id=123, pending_update_post_id=777,
            pending_update_message={'chat': self.chat, 'message_id': 1, 'text': 'Example'})
        with patch.object(bot, '_handle_channel_post') as receive:
            bot._handle_callback_query(self.callback('update:777'))
        receive.assert_not_called()

    def test_expired_owner_cannot_submit_waiting_invite(self):
        BotSession.objects.create(telegram_user_id=999, selected_author=self.author, invite_waiting=True)
        bot._handle_private_message({'chat': {'id': 999, 'type': 'private'}, 'text': 'https://t.me/+example'})
        self.author.refresh_from_db()
        self.assertEqual(self.author.invite_url, '')

    def test_membership_event_by_another_admin_does_not_silently_replace_recipient(self):
        bot._handle_my_chat_member({'chat': self.chat, 'from': {'id': 999},
                                   'new_chat_member': {'status': 'administrator'}})
        self.author.refresh_from_db()
        self.assertEqual(self.author.admin_chat_id, 123)


@override_settings(TELEGRAM_USE_POLLING=False, TELEGRAM_BOT_TOKEN='')
class ConcurrentVerificationTests(TransactionTestCase):
    def test_code_can_be_consumed_by_only_one_telegram_account(self):
        user = get_user_model().objects.create_user(username='single-use')
        code = AuthorVerificationCode.objects.create(user=user, code='COMUNA-ONCE')
        barrier = Barrier(2)
        def consume(actor):
            try:
                barrier.wait(timeout=5)
                return TelegramChannelVerification().consume(actor, code.code) is not None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(consume, (123, 456)))
        self.assertEqual(sum(results), 1)
        self.assertEqual(BotSession.objects.filter(verified_user_id=user.pk).count(), 1)
