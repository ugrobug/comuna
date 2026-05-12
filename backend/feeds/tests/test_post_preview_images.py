import json

from django.test import SimpleTestCase, override_settings

from feeds.models import Post
from feeds.views import _extract_post_preview_image_urls


@override_settings(SITE_BASE_URL="https://tambur.pub", MEDIA_URL="/media/")
class PostPreviewImageTests(SimpleTestCase):
    def test_extracts_local_webp_variants_from_html_image(self) -> None:
        post = Post(
            content='<p>Текст</p><img src="https://tambur.pub/media/uploads/post/foo-1920.webp" alt="">'
        )

        preview_url, thumbnail_url = _extract_post_preview_image_urls(None, post)

        self.assertEqual(preview_url, "https://tambur.pub/media/uploads/post/foo-1280.webp")
        self.assertEqual(thumbnail_url, "https://tambur.pub/media/uploads/post/foo-640.webp")

    def test_extracts_editor_gallery_relative_image(self) -> None:
        post = Post(
            content=json.dumps(
                {
                    "blocks": [
                        {
                            "type": "gallery",
                            "data": {
                                "images": [
                                    {"url": "/media/uploads/post/gallery-960.webp"},
                                ],
                            },
                        }
                    ],
                }
            )
        )

        preview_url, thumbnail_url = _extract_post_preview_image_urls(None, post)

        self.assertEqual(preview_url, "https://tambur.pub/media/uploads/post/gallery-960.webp")
        self.assertEqual(thumbnail_url, "https://tambur.pub/media/uploads/post/gallery-640.webp")

    def test_rejects_private_telegram_file_urls(self) -> None:
        post = Post(
            content='<img src="https://api.telegram.org/file/botSECRET/photos/file_1.jpg" alt="">'
        )

        preview_url, thumbnail_url = _extract_post_preview_image_urls(None, post)

        self.assertIsNone(preview_url)
        self.assertIsNone(thumbnail_url)
