from datetime import timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.utils import timezone
from django.db import connection
from django.test.utils import CaptureQueriesContext
from feeds.models import Post
from feeds import views
from telegram_integration import bot
from telegram_integration.media_queue import TelegramMediaWorker
from telegram_integration.models import TelegramMediaJob
from telegram_integration.tests.test_album_import import AlbumFixture, AlbumImportTests


@override_settings(TELEGRAM_BOT_TOKEN='test-token', TELEGRAM_USE_POLLING=False)
class MediaQueueTests(AlbumFixture, TestCase):
    setUp = AlbumImportTests.setUp

    def test_existing_tag_with_changed_lemma_does_not_block_photo_receipt(self):
        from feeds.models import Tag
        tag = Tag.objects.create(name='фильмы', lemma='фильм')
        with patch('feeds.views._lemmatize_tag', return_value=''):
            post = bot._handle_channel_post(self.make_message(1, caption='Text #фильмы'))
            next_post = bot._handle_channel_post(self.make_message(2, group='next', caption='Next text'))
        self.assertIsNotNone(post)
        self.assertIsNotNone(next_post)
        self.assertEqual(list(post.tags.values_list('pk', flat=True)), [tag.pk])
        self.assertEqual(self.worker().drain()['processed'], 2)
        post.refresh_from_db()
        self.assertIn('<img', post.content)
        self.assertTrue(post.preview_image_url)

    def worker(self, download=None):
        return TelegramMediaWorker(download=download or (lambda msg: f"https://media.test/{msg['message_id']}.webp"),
            content=views, prompt=Mock())

    def test_text_published_while_photo_only_waits_and_queue_survives_failure(self):
        self.author.auto_publish = True
        self.author.save()
        photo_only = self.make_message(1, group='first')
        self.assertIsNone(bot._handle_channel_post(photo_only))
        post = bot._handle_channel_post(self.make_message(2, group='second', caption='Useful text'))
        self.assertFalse(post.is_pending)
        self.assertIn('Useful text', post.content)
        self.assertEqual(Post.objects.count(), 1)
        failed = self.worker(Mock(side_effect=ConnectionError('unavailable'))).drain()
        self.assertEqual(failed['failed'], 1)
        self.assertEqual(TelegramMediaJob.objects.filter(state='pending').count(), 2)
        TelegramMediaJob.objects.update(next_attempt_at=timezone.now())
        self.worker().drain()
        self.assertEqual(Post.objects.count(), 2)
        post.refresh_from_db()
        self.assertIn('<img', post.content)
        self.assertIn('Useful text', post.content)

    def test_repeated_update_and_worker_do_not_duplicate_album_and_preserve_approval(self):
        self.author.publish_delay_days = 3
        self.author.save()
        for n in (3, 2, 1, 2):
            bot._handle_channel_post(self.make_message(n, caption='Caption' if n == 1 else ''))
        post = Post.objects.get()
        due = post.publish_at
        post.is_pending = False
        post.save(update_fields=['is_pending'])
        self.worker().drain()
        self.worker().drain()
        post.refresh_from_db()
        self.assertEqual(post.raw_data['gallery_message_ids'], [1, 2, 3])
        self.assertEqual(post.content.count('<img '), 3)
        self.assertFalse(post.is_pending)
        self.assertEqual(post.publish_at, due)
        self.assertEqual(TelegramMediaJob.objects.count(), 3)

    def test_edit_invalidates_inflight_lease(self):
        message = self.make_message(1, caption='First')
        post = bot._handle_channel_post(message)
        worker = self.worker()
        claimed = worker.claim()
        message = self.make_message(1, caption='Changed')
        message['edit_date'] = 20
        message['photo'][0]['file_id'] = 'replacement'
        bot._handle_channel_post(message)
        self.assertIsNone(worker.complete(claimed, 'https://media.test/stale.webp'))
        worker.drain()
        post.refresh_from_db()
        self.assertIn('Changed', post.content)
        self.assertNotIn('stale.webp', post.content)

    def test_manual_edit_is_not_overwritten(self):
        post = bot._handle_channel_post(self.make_message(1, caption='First'))
        Post.objects.filter(pk=post.pk).update(content='Manual website edit')
        self.worker().drain()
        post.refresh_from_db()
        self.assertEqual(post.content, 'Manual website edit')
        self.assertEqual(TelegramMediaJob.objects.get().state, 'cancelled')

    def test_deleted_post_is_not_recreated(self):
        post = bot._handle_channel_post(self.make_message(1, caption='First'))
        worker = self.worker()
        claimed = worker.claim()
        post.delete()
        self.assertIsNone(worker.complete(claimed, 'https://media.test/1.webp'))
        self.assertFalse(Post.objects.exists())

    def test_rejected_post_stays_hidden(self):
        post = bot._handle_channel_post(self.make_message(1, caption='First'))
        Post.objects.filter(pk=post.pk).update(is_pending=False, is_blocked=True)
        self.worker().drain()
        post.refresh_from_db()
        self.assertTrue(post.is_blocked)
        self.assertEqual(TelegramMediaJob.objects.get().state, 'cancelled')

    def test_expired_lease_can_be_recovered_and_old_worker_cannot_finish(self):
        bot._handle_channel_post(self.make_message(1))
        worker = self.worker()
        first = worker.claim()
        TelegramMediaJob.objects.update(next_attempt_at=timezone.now() - timedelta(seconds=1))
        second = worker.claim()
        self.assertNotEqual(first.lease_token, second.lease_token)
        self.assertIsNone(worker.complete(first, 'https://media.test/old.webp'))
        self.assertIsNotNone(worker.complete(second, 'https://media.test/new.webp'))

    def test_enqueue_is_atomic_with_post_and_network_free(self):
        with patch('feeds.views._extract_photo_url', side_effect=AssertionError('network')):
            with patch('telegram_integration.media_queue.TelegramMediaQueue.bind', side_effect=RuntimeError):
                with self.assertRaises(RuntimeError):
                    bot._handle_channel_post(self.make_message(1, caption='Caption'))
        self.assertFalse(Post.objects.exists())
        self.assertFalse(TelegramMediaJob.objects.exists())

    def test_queue_query_budget_does_not_grow_with_album(self):
        counts = []
        for n in range(1, 11):
            with CaptureQueriesContext(connection) as queries:
                bot._handle_channel_post(self.make_message(n, caption='Caption' if n == 1 else ''))
            counts.append(len(queries))
        self.assertEqual(counts[1], counts[-1])
        self.assertLessEqual(counts[-1], 25)

    def test_textless_single_photo_waits_for_consent_after_download(self):
        bot._handle_channel_post(self.make_message(1, group=''))
        worker = self.worker()
        worker.drain()
        post = Post.objects.get()
        self.assertTrue(post.is_pending)
        self.assertEqual(post.title, 'Фото')
        worker.prompt.deliver.assert_called_once()

    def test_removing_photo_from_telegram_invalidates_inflight_upload(self):
        post = bot._handle_channel_post(self.make_message(1, caption='First'))
        worker = self.worker()
        claimed = worker.claim()
        message = self.make_message(1, caption='Now text only')
        message.pop('photo')
        message['edit_date'] = 123
        bot._handle_channel_post(message)
        self.assertIsNone(worker.complete(claimed, 'https://media.test/removed.webp'))
        post.refresh_from_db()
        self.assertIn('Now text only', post.content)
        self.assertNotIn('<img', post.content)

    def test_consent_changed_during_download_controls_photo_only_post(self):
        self.author.auto_publish = True
        self.author.save()
        bot._handle_channel_post(self.make_message(1))
        worker = self.worker()
        claimed = worker.claim()
        self.author.auto_publish = False
        self.author.publish_delay_days = 2
        self.author.save()
        post = worker.complete(claimed, 'https://media.test/1.webp')
        self.assertTrue(post.is_pending)
        self.assertGreater(post.publish_at, timezone.now() + timedelta(days=1))

    def test_capacity_keeps_receipt_unacknowledged_without_empty_post(self):
        bot._handle_channel_post(self.make_message(1))
        with patch('telegram_integration.media_queue.TelegramMediaQueue.max_pending_per_author', 1):
            with self.assertRaises(RuntimeError):
                bot._handle_channel_post(self.make_message(2, caption='Caption'))
        self.assertEqual(TelegramMediaJob.objects.count(), 1)
        self.assertFalse(Post.objects.exists())

    def test_terminal_error_retains_payload_for_manual_retry(self):
        bot._handle_channel_post(self.make_message(1))
        TelegramMediaJob.objects.update(attempts=99)
        self.worker(Mock(return_value=None)).drain()
        job = TelegramMediaJob.objects.get()
        self.assertEqual(job.state, 'failed')
        self.assertTrue(job.payload['message']['photo'])

    def test_empty_worker_uses_one_indexed_query(self):
        with CaptureQueriesContext(connection) as queries:
            self.worker().drain()
        selects = [q for q in queries if q['sql'].lstrip().startswith('SELECT')]
        self.assertEqual(len(selects), 1)
