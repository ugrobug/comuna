from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Event
from unittest.mock import Mock

from django.db import connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from feeds.models import Author, Post
from telegram_integration.models import TelegramApprovalDelivery
from telegram_integration.moderation import TelegramApprovalPrompt


@override_settings(TELEGRAM_USE_POLLING=False, TELEGRAM_BOT_TOKEN='')
class ApprovalDeliveryTests(TestCase):
    def setUp(self):
        self.author = Author.objects.create(username='delivery', admin_chat_id=123, auto_publish=False)
        self.post = Post.objects.create(author=self.author, message_id=1, title='Example', is_pending=True)

    def test_failed_send_is_durable_and_does_not_raise_or_publish(self):
        send = Mock(side_effect=TimeoutError)
        TelegramApprovalPrompt(send).deliver(self.post, self.author)
        delivery = TelegramApprovalDelivery.objects.get(post=self.post)
        self.assertEqual(delivery.attempts, 1)
        self.assertIsNone(delivery.sent_at)
        self.assertGreater(delivery.next_attempt_at, timezone.now())
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_pending)
        # Immediate replays do not hammer Telegram.
        TelegramApprovalPrompt(send).deliver(self.post, self.author)
        self.assertEqual(send.call_count, 1)

    def test_new_worker_retries_after_lease_expiry_and_does_not_repeat_sent_prompt(self):
        delivery = TelegramApprovalDelivery.objects.create(post=self.post, chat_id=123,
            lease_token='abandoned', next_attempt_at=timezone.now() - timedelta(seconds=1))
        send = Mock(return_value={'ok': True, 'result': {'message_id': 99}})
        TelegramApprovalPrompt(send).drain()
        TelegramApprovalPrompt(send).deliver(self.post, self.author)
        self.assertEqual(send.call_count, 1)
        delivery.refresh_from_db()
        self.assertIsNotNone(delivery.sent_at)

    def test_attempts_are_bounded_and_failure_is_visible_without_publication(self):
        send = Mock(return_value=None)
        service = TelegramApprovalPrompt(send)
        service.deliver(self.post, self.author)
        for _ in range(12):
            TelegramApprovalDelivery.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
            service.drain()
        self.assertEqual(send.call_count, 8)
        self.assertIsNotNone(TelegramApprovalDelivery.objects.get().failed_at)
        self.post.refresh_from_db()
        self.assertTrue(self.post.is_pending)

    def test_empty_due_scan_is_one_query_even_with_sent_history(self):
        TelegramApprovalDelivery.objects.create(post=self.post, chat_id=123, sent_at=timezone.now())
        with self.assertNumQueries(1):
            self.assertEqual(TelegramApprovalPrompt(Mock()).drain(), 0)

    def test_post_decided_before_retry_is_never_prompted_again(self):
        TelegramApprovalDelivery.objects.create(post=self.post, chat_id=123)
        Post.objects.filter(pk=self.post.pk).update(is_pending=False)
        send = Mock()
        TelegramApprovalPrompt(send).drain()
        send.assert_not_called()


@override_settings(TELEGRAM_USE_POLLING=False, TELEGRAM_BOT_TOKEN='')
class ConcurrentApprovalDeliveryTests(TransactionTestCase):
    def test_two_workers_claim_only_one_send_without_holding_lock_during_network(self):
        author = Author.objects.create(username='concurrent-delivery', admin_chat_id=123)
        post = Post.objects.create(author=author, message_id=1, title='Example', is_pending=True)
        TelegramApprovalDelivery.objects.create(post=post, chat_id=123)
        sending, release = Event(), Event()
        def send(*args):
            sending.set()
            if not release.wait(5):
                raise TimeoutError()
            return {'ok': True, 'result': {'message_id': 99}}
        sender = Mock(side_effect=send)
        def run():
            try:
                return TelegramApprovalPrompt(sender).drain()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run)
            try:
                self.assertTrue(sending.wait(5))
                self.assertEqual(pool.submit(run).result(timeout=3), 0)
            finally:
                release.set()
            first.result(timeout=5)
        self.assertEqual(sender.call_count, 1)
