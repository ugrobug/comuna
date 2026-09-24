from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.test.utils import CaptureQueriesContext

from communities.models import Comun
from feeds.models import Author, Post
from feeds import views
from telegram_integration import bot, polling
from telegram_integration.channel_posts import TelegramChannelPostWriter, TelegramMediaDownloadError


class AlbumFixture:
    def make_message(self, number, group="album", caption=""):
        return {"chat": {"id": -100123, "type": "channel", "username": self.author.username},
                "message_id": number, "media_group_id": group, "caption": caption,
                "photo": [{"file_id": f"photo-{number}", "width": 100, "height": 100}]}

    def write(self, number, group="album", caption=""):
        return TelegramChannelPostWriter(views).save(
            author=self.author, message=self.make_message(number, group, caption),
            formatted_text=caption, raw_text=caption, explicit_tags=[],
            photo_file_id=f"photo-{number}", image_url=f"https://media.test/{number}.webp",
            embed_html="", embed_label="", poll_html="", poll_label="", force_publish=False)


@override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_USE_POLLING=False)
class AlbumImportTests(AlbumFixture, TestCase):
    def setUp(self):
        self.author = Author.objects.create(username="album-channel", auto_publish=False, admin_chat_id=123)
        self.comun = Comun.objects.create(name="Album", slug="album", telegram_source_author=self.author)
        for target, kwargs in [
            ("telegram_integration.bot._is_bot_admin", {"return_value": True}),
            ("telegram_integration.bot._refresh_author_from_telegram", {}),
            ("telegram_integration.bot._send_bot_message_with_keyboard", {}),
            ("feeds.views._maybe_notify_new_author", {}),
            ("communities.service._ensure_telegram_channel_comun_for_author", {"return_value": self.comun}),
        ]:
            patcher = patch(target, **kwargs)
            self.addCleanup(patcher.stop)
            patcher.start()

    def test_four_photos_and_replayed_update_make_one_complete_post(self):
        with patch("feeds.views._extract_photo_url", side_effect=lambda message, token: f"https://media.test/{message['message_id']}.webp"):
            for number in (242, 243, 244, 245, 243):
                bot._handle_channel_post(self.make_message(number, caption="Caption" if number == 242 else ""))
        post = Post.objects.get(author=self.author)
        self.assertEqual(post.content.count("<img "), 4)
        self.assertEqual(len(post.raw_data["gallery_file_ids"]), 4)
        self.assertIn("Caption", post.content)
        self.assertTrue(post.is_pending)

    def test_download_failure_does_not_acknowledge_or_publish_partial_message(self):
        processor = polling.TelegramUpdateProcessor()
        processor.offset = 100
        updates = [{"update_id": 100 + n, "channel_post": self.make_message(242 + n)} for n in range(4)]
        with patch("feeds.views._extract_photo_url", return_value=None):
            with self.assertRaises(TelegramMediaDownloadError):
                processor.process(updates)
        self.assertEqual(processor.offset, 100)
        self.assertFalse(Post.objects.filter(author=self.author).exists())
        with patch("feeds.views._extract_photo_url", side_effect=lambda message, token: f"https://media.test/{message['message_id']}.webp"):
            processor.process(updates)
        self.assertEqual(processor.offset, 104)
        self.assertEqual(Post.objects.get(author=self.author).content.count("<img "), 4)

    def test_caption_does_not_hide_failed_photo_download(self):
        with patch("feeds.views._extract_photo_url", return_value=None):
            with self.assertRaises(TelegramMediaDownloadError):
                bot._handle_channel_post(self.make_message(242, caption="Caption"))
        self.assertFalse(Post.objects.exists())

    def test_album_updates_preserve_approval_and_delay(self):
        self.author.publish_delay_days = 3
        post, _ = self.write(242, caption="Caption")
        publish_at = post.publish_at
        post.is_pending = False
        post.save(update_fields=["is_pending"])
        self.write(243)
        post.refresh_from_db()
        self.assertEqual(post.publish_at, publish_at)
        self.assertFalse(post.is_pending)
        self.assertEqual(post.content.count("<img "), 2)

    def test_album_query_count_does_not_grow_with_gallery(self):
        self.write(1)
        with CaptureQueriesContext(connection) as first:
            self.write(2)
        for number in range(3, 10):
            self.write(number)
        with CaptureQueriesContext(connection) as last:
            self.write(10)
        self.assertEqual(len(first), len(last))
        self.assertLessEqual(len(last), 30)
        self.assertEqual(Post.objects.get(author=self.author).content.count("<img "), 10)

    def test_out_of_order_photos_keep_telegram_order(self):
        for number in (245, 243, 244, 242):
            self.write(number)
        post = Post.objects.get(author=self.author)
        self.assertEqual(post.raw_data["gallery_message_ids"], [242, 243, 244, 245])
        self.assertEqual(post.raw_data["gallery_file_ids"], [f"photo-{n}" for n in range(242, 246)])
        self.assertEqual(post.raw_data["gallery_urls"], [f"https://media.test/{n}.webp" for n in range(242, 246)])

    def test_recovered_gallery_survives_replay_without_all_bot_file_ids(self):
        post, _ = self.write(245)
        post.raw_data.update(gallery_message_ids=[242, 243, 244, 245],
            gallery_urls=[f"https://media.test/{n}.webp" for n in range(242, 246)],
            gallery_file_ids=[], gallery_file_ids_complete=False)
        post.save(update_fields=["raw_data"])
        self.write(245)
        post.refresh_from_db()
        self.assertEqual(post.content.count("<img "), 4)
        self.assertEqual(post.raw_data["gallery_file_ids"], [])


@override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_USE_POLLING=False)
class ConcurrentAlbumTests(AlbumFixture, TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_first_photos_create_one_album(self):
        self.author = Author.objects.create(username="concurrent-album", auto_publish=False, admin_chat_id=123)
        barrier = Barrier(4)

        def receive(number):
            try:
                barrier.wait(timeout=10)
                return self.write(number)[0].pk
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(receive, range(1, 5)))
        self.assertEqual(len(set(ids)), 1)
        post = Post.objects.get(author=self.author)
        self.assertEqual(post.content.count("<img "), 4)
        self.assertEqual(set(post.raw_data["gallery_file_ids"]), {f"photo-{n}" for n in range(1, 5)})
