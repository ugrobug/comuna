from __future__ import annotations

from django.test import SimpleTestCase

from telegram_integration.bot import _merge_media_group_image


class TelegramMediaGroupDedupTests(SimpleTestCase):
    def test_repeated_media_group_photo_does_not_duplicate_gallery_url(self) -> None:
        raw_data = _merge_media_group_image(
            {},
            image_url="https://tambur.pub/media/posts/telegram/first.webp",
            photo_file_id="same-photo",
            media_group_id="group-1",
        )

        raw_data = _merge_media_group_image(
            raw_data,
            image_url="https://tambur.pub/media/posts/telegram/second.webp",
            photo_file_id="same-photo",
            media_group_id="group-1",
        )

        self.assertEqual(raw_data["gallery_file_ids"], ["same-photo"])
        self.assertEqual(raw_data["gallery_urls"], ["https://tambur.pub/media/posts/telegram/first.webp"])
