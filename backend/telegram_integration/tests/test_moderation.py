import io
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from django.db import connection, connections
from django.test import TestCase, SimpleTestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from communities.models import Comun
from feeds import views
from feeds.models import Author, Post, PublicFeedItem
from telegram_integration import bot, polling
from telegram_integration.models import BotSession
from telegram_integration.channel_posts import TelegramChannelPostWriter
from telegram_integration.moderation import (
    TelegramPostModeration, TelegramModerationReceipt,
    TelegramModerationReceiptUnavailable, ModerationResult,
)


@override_settings(TELEGRAM_USE_POLLING=False, TELEGRAM_BOT_TOKEN='test-token',
                   CACHES={'default': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'}})
class ModerationTests(TestCase):
    def setUp(self):
        self.author = Author.objects.create(username='consent-channel', auto_publish=False, admin_chat_id=123)
        self.comun = Comun.objects.create(name='Consent', slug='consent', telegram_source_author=self.author)
        self.service = TelegramPostModeration()
        for target in ['feeds.views._maybe_notify_new_author', 'telegram_integration.bot._answer_callback_query']:
            patcher = patch(target)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, number=1, *, force=False):
        return TelegramChannelPostWriter(views).save(
            author=self.author,
            message={'message_id':number, 'chat': {'username': self.author.username}},
            formatted_text='Короткая запись', raw_text='Короткая запись', explicit_tags=[],
            photo_file_id=None, image_url=None, embed_html='', embed_label='',
            poll_html='', poll_label='', force_publish=force)[0]

    def callback(self, post, *, actor=123, approve=True):
        return {'id':'callback', 'from': {'id':actor},
                'data':f'{"approve" if approve else "reject"}:{post.pk}',
                'message': {'message_id':99, 'chat': {'id':123, 'type':'private'}}}

    def test_import_edit_and_missing_admin_never_bypass_consent(self):
        post = self.write()
        self.write()
        post.refresh_from_db()
        self.assertTrue(post.is_pending)
        self.author.admin_chat_id = None
        self.author.save(update_fields=['admin_chat_id'])
        self.assertTrue(self.write(2).is_pending)
        self.author.auto_publish = True
        self.assertFalse(self.write(3).is_pending)

    def test_forward_does_not_overwrite_channel_consent_with_old_session_default(self):
        BotSession.objects.create(telegram_user_id=123, selected_author=self.author, auto_publish=True)
        message = {'chat': {'id':123,'type':'private'}, 'text':'Короткая запись',
                   'forward_origin': {'type':'channel', 'message_id':1,
                                      'chat': {'id':-100123,'type':'channel','username':self.author.username}}}
        with patch.object(bot, '_is_bot_admin', return_value=True), \
             patch.object(bot, '_refresh_author_from_telegram'), \
             patch.object(bot, '_send_bot_message') as send, \
             patch.object(bot, '_send_bot_message_with_keyboard') as prompt, \
             patch('feeds.views._extract_photo_url', return_value=None), \
             patch('communities.service._ensure_telegram_channel_comun_for_author', return_value=self.comun):
            bot._handle_private_message(message)
        self.author.refresh_from_db()
        self.assertFalse(self.author.auto_publish)
        self.assertTrue(Post.objects.get(author=self.author).is_pending)
        self.assertIn('пока не опубликован', send.call_args.args[1])
        prompt.assert_called_once()

    def test_repeated_membership_event_preserves_channel_mode(self):
        BotSession.objects.create(telegram_user_id=123, auto_publish=True)
        with patch.object(bot, '_refresh_author_from_telegram'), \
             patch.object(bot, '_send_bot_message'), \
             patch('communities.service._ensure_telegram_channel_comun_for_author', return_value=self.comun):
            bot._handle_my_chat_member({
                'chat': {'id':-100123, 'type':'channel', 'username':self.author.username},
                'from': {'id':123}, 'new_chat_member': {'status':'administrator'},
            })
        self.author.refresh_from_db()
        self.assertFalse(self.author.auto_publish)

    def test_pending_hidden_in_detail_author_community_and_stale_materialized_feed(self):
        post = self.write()
        PublicFeedItem.objects.create(feed=PublicFeedItem.FEED_HOME, post=post, rank=1, score=10,
                                     post_created_at=post.created_at, author_id_snapshot=self.author.pk)
        self.assertEqual(self.client.get(reverse('post-detail', args=[post.pk])).status_code, 404)
        for url in [reverse('author-posts', args=[self.author.username]),
                    reverse('comun-posts', args=[self.comun.slug]), reverse('home-feed')]:
            response = self.client.get(url, {'card':1, 'limit':10})
            self.assertEqual(response.status_code, 200, response.content)
            self.assertNotIn(post.pk, [row['id'] for row in response.json()['posts']])

    def test_only_current_admin_can_decide_and_replay_preserves_audit(self):
        post = self.write()
        for actor, chat in [(999,123), (999,999), (None,123), (123,-100)]:
            self.assertFalse(self.service.decide(post.pk, actor_id=actor, chat_id=chat, approve=True).changed)
        post.refresh_from_db()
        self.assertTrue(post.is_pending)
        result = self.service.decide(post.pk, actor_id=123, chat_id=123, approve=True)
        self.assertTrue(result.changed)
        decision = result.post.raw_data['telegram_moderation']
        self.assertEqual(decision['state'], 'approved')
        self.assertFalse(self.service.decide(post.pk, actor_id=123, chat_id=123, approve=False).changed)
        self.write()
        post.refresh_from_db()
        self.assertFalse(post.is_pending)
        self.assertFalse(post.is_blocked)
        self.assertEqual(post.raw_data['telegram_moderation'], decision)

    def test_rejection_cannot_be_reversed_by_old_button_or_telegram_edit(self):
        post = self.write()
        self.service.decide(post.pk, actor_id=123, chat_id=123, approve=False)
        self.assertFalse(self.service.decide(post.pk, actor_id=123, chat_id=123, approve=True).changed)
        self.write()
        post.refresh_from_db()
        self.assertTrue(post.is_blocked)
        self.assertEqual(post.raw_data['telegram_moderation']['state'], 'rejected')

    def test_approval_preserves_delay(self):
        self.author.publish_delay_days = 3
        post = self.write()
        result = self.service.decide(post.pk, actor_id=123, chat_id=123, approve=True)
        self.assertEqual(result.post.publish_at, post.publish_at)
        self.assertIn('ожидает', result.text)
        self.assertEqual(self.client.get(reverse('post-detail', args=[post.pk])).status_code, 404)

    def test_receipt_failure_retries_without_republishing(self):
        post = self.write()
        processor = polling.TelegramUpdateProcessor()
        update = {'update_id':100, 'callback_query':self.callback(post)}
        with patch.object(TelegramModerationReceipt, 'deliver', side_effect=[TelegramModerationReceiptUnavailable(), None]) as receipt:
            with self.assertRaises(TelegramModerationReceiptUnavailable):
                processor.process([update])
            self.assertIsNone(processor.offset)
            post.refresh_from_db()
            decided_at = post.raw_data['telegram_moderation']['decided_at']
            self.assertFalse(post.is_pending)
            processor.process([update])
            self.assertEqual(processor.offset, 101)
            self.assertEqual(receipt.call_count, 2)
        post.refresh_from_db()
        self.assertEqual(post.raw_data['telegram_moderation']['decided_at'], decided_at)

    def test_receipt_is_outside_decision_lock_and_no_import_api_is_needed(self):
        post = self.write()
        with patch.object(TelegramModerationReceipt, 'deliver') as receipt, \
             patch.object(bot, '_is_bot_admin', side_effect=AssertionError('Network permission check')), \
             CaptureQueriesContext(connection) as queries:
            bot._handle_callback_query(self.callback(post))
        receipt.assert_called_once()
        self.assertFalse(receipt.call_args.args[0].post.is_pending)
        self.assertLessEqual(len(queries), 25)


class PriorityDecisionTests(SimpleTestCase):
    def test_decision_runs_despite_earlier_import_failure_without_skipping_offset(self):
        processor = polling.TelegramUpdateProcessor()
        processor.offset = 10
        updates = [{'update_id':10,'channel_post':{}},
                   {'update_id':11,'callback_query':{'data':'approve:1'}}]
        with patch.object(polling, '_handle_channel_post', side_effect=RuntimeError()), \
             patch.object(polling, '_handle_callback_query') as decision:
            for _ in range(2):
                with self.assertRaises(RuntimeError): processor.process(updates)
            decision.assert_called_once()
            self.assertEqual(processor.offset, 10)
        with patch.object(polling, '_handle_channel_post'), patch.object(polling, '_handle_callback_query') as decision:
            processor.process(updates)
            decision.assert_not_called()
            self.assertEqual(processor.offset, 12)
            self.assertEqual(processor._completed_decisions, set())

    def test_other_callbacks_keep_original_order(self):
        with patch.object(polling, '_handle_channel_post', side_effect=RuntimeError()), \
             patch.object(polling, '_handle_callback_query') as callback:
            with self.assertRaises(RuntimeError):
                polling.TelegramUpdateProcessor().process([
                    {'update_id':1,'channel_post':{}},
                    {'update_id':2,'callback_query':{'data':'mode:auto'}}])
            callback.assert_not_called()


class ReceiptTests(SimpleTestCase):
    def result(self):
        return ModerationResult('Пост опубликован', Mock(pk=7))

    def test_receipt_removes_buttons_without_sending_new_message(self):
        opener = Mock(return_value=io.BytesIO(b'{"ok":true}'))
        TelegramModerationReceipt('secret', 'https://example.test', opener=opener).deliver(
            self.result(), chat_id=1, message_id=2)
        self.assertIn('/editMessageText', opener.call_args.args[0])
        from urllib.parse import parse_qs
        data = parse_qs(opener.call_args.kwargs['data'].decode())
        self.assertEqual(json.loads(data['reply_markup'][0]), {'inline_keyboard':[]})
        self.assertIn('/b/post/7', data['text'][0])
        self.assertEqual(opener.call_args.kwargs['timeout'], 5)

    def test_idempotent_api_error_is_success_but_timeout_is_retryable_and_sanitized(self):
        error = HTTPError('https://api.test',400,'bad',{},io.BytesIO(json.dumps({
            'ok':False,'error_code':400,'description':'Bad Request: message is not modified'}).encode()))
        TelegramModerationReceipt('secret','https://example.test',opener=Mock(side_effect=error)).deliver(
            self.result(), chat_id=1,message_id=2)
        with self.assertRaises(TelegramModerationReceiptUnavailable) as caught:
            TelegramModerationReceipt('secret','https://example.test',opener=Mock(side_effect=TimeoutError('secret'))).deliver(
                self.result(), chat_id=1,message_id=2)
        self.assertNotIn('secret', str(caught.exception))


@override_settings(TELEGRAM_USE_POLLING=False)
@skipUnlessDBFeature('has_select_for_update')
class ConcurrentModerationTests(TransactionTestCase):
    def test_concurrent_opposite_decisions_commit_only_one_transition(self):
        author = Author.objects.create(username='concurrent-consent', admin_chat_id=123, auto_publish=False)
        post = Post.objects.create(author=author, message_id=1, title='Тест', content='Тест', is_pending=True)
        barrier = Barrier(2)

        def decide(approve):
            connections.close_all()
            try:
                barrier.wait(timeout=10)
                return TelegramPostModeration().decide(post.pk, actor_id=123, chat_id=123, approve=approve).changed
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(decide, [True, False]))
        self.assertEqual(sum(results), 1)
        post.refresh_from_db()
        self.assertFalse(post.is_pending)
        self.assertEqual(post.raw_data['telegram_moderation']['state'], 'rejected' if post.is_blocked else 'approved')
