import json
import base64
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from feeds.models import Post
from feeds.preview import build_post_preview
from feeds.views import _extract_post_preview_image_urls


@override_settings(SITE_BASE_URL="https://tambur.pub", MEDIA_URL="/media/", MEDIA_PUBLIC_URL_MODE="legacy")
class PostPreviewImageTests(SimpleTestCase):
    def test_extracts_local_webp_variants_from_html_image(self) -> None:
        post = Post(
            content='<p>Текст</p><img src="https://tambur.pub/media/uploads/post/foo-1920.webp" alt="">'
        )

        preview_url, thumbnail_url = _extract_post_preview_image_urls(None, post)

        self.assertEqual(preview_url, "https://tambur.pub/media/uploads/post/foo-1280.webp")
        self.assertEqual(thumbnail_url, "https://tambur.pub/media/uploads/post/foo-640.webp")

    @override_settings(MEDIA_PUBLIC_URL_MODE="s3", AWS_S3_CUSTOM_DOMAIN="media.tambur.pub")
    def test_extracts_s3_webp_variants_when_public_media_mode_is_s3(self) -> None:
        post = Post(
            content='<p>Текст</p><img src="https://tambur.pub/media/uploads/post/foo-1920.webp" alt="">'
        )

        preview_url, thumbnail_url = _extract_post_preview_image_urls(None, post)

        self.assertEqual(preview_url, "https://media.tambur.pub/uploads/post/foo-1280.webp")
        self.assertEqual(thumbnail_url, "https://media.tambur.pub/uploads/post/foo-640.webp")

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

    def test_uses_stored_preview_image_before_parsing_content(self) -> None:
        post = Post(
            preview_image_url="/media/uploads/post/stored-1280.webp",
            content='<img src="/media/uploads/post/content-1280.webp" alt="">',
        )

        preview_url, thumbnail_url = _extract_post_preview_image_urls(None, post)

        self.assertEqual(preview_url, "https://tambur.pub/media/uploads/post/stored-1280.webp")
        self.assertEqual(thumbnail_url, "https://tambur.pub/media/uploads/post/stored-640.webp")

    def test_builds_small_preview_from_base64_editor_content(self) -> None:
        payload = {
            "time": 1778574260918,
            "blocks": [
                {"type": "paragraph", "data": {"text": "Первая <b>строка</b> поста"}},
                {
                    "type": "gallery",
                    "data": {"images": [{"url": "/media/uploads/post/gallery-960.webp"}]},
                },
            ],
        }
        raw = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")

        preview = build_post_preview(raw, {})

        self.assertEqual(preview["preview_content"], "<p>Первая <b>строка</b> поста</p>")
        self.assertEqual(preview["preview_image_url"], "/media/uploads/post/gallery-960.webp")

    def test_builds_formatted_preview_from_editor_paragraph(self) -> None:
        payload = {
            "blocks": [
                {
                    "type": "paragraph",
                    "data": {"text": "Первая строка<br>Вторая <b>строка</b>"},
                },
            ],
        }

        preview = build_post_preview(json.dumps(payload), {})

        self.assertEqual(
            preview["preview_content"],
            "<p>Первая строка<br>Вторая <b>строка</b></p>",
        )

    def test_builds_text_preview_from_html_after_gallery(self) -> None:
        content = (
            '<div class="post-gallery">'
            '<img src="/media/uploads/post/one.webp" alt="" />'
            '<img src="/media/uploads/post/two.webp" alt="" />'
            "</div><br><br>Так вот почему он так долго не может вернуться домой"
        )

        preview = build_post_preview(content, {})

        self.assertEqual(
            preview["preview_content"],
            "<p>Так вот почему он так долго не может вернуться домой</p>",
        )
        self.assertEqual(preview["preview_image_url"], "/media/uploads/post/one.webp")

    def test_builds_text_preview_after_corrupted_gallery_tail(self) -> None:
        content = (
            '<div class="post-gallery">'
            '<img src="/media/uploads/post/one.webp" alt="" /> alt="" /> alt="" />'
            "</div><br><br>Так вот почему он так долго не может вернуться домой"
        )

        preview = build_post_preview(content, {})

        self.assertEqual(
            preview["preview_content"],
            "<p>Так вот почему он так долго не может вернуться домой</p>",
        )

    def test_prefers_image_before_gallery_for_preview_image(self) -> None:
        content = json.dumps(
            {
                "blocks": [
                    {"type": "image", "data": {"file": {"url": "/media/uploads/post/first.jpg"}}},
                    {
                        "type": "gallery",
                        "data": {"images": [{"url": "/media/uploads/post/gallery.jpg"}]},
                    },
                ],
            }
        )

        preview = build_post_preview(content, {})

        self.assertEqual(preview["preview_image_url"], "/media/uploads/post/first.jpg")

    def test_bug_report_preview_uses_platforms_and_browsers(self) -> None:
        with patch(
            "feeds.preview.editor_service._normalize_post_template_payload",
            return_value=(
                {
                    "type": "bug_report",
                    "data": {
                        "status": "in_progress",
                        "platforms": ["windows", "android"],
                        "browsers": ["chrome", "yandex_browser"],
                    },
                },
                None,
            ),
        ):
            preview = build_post_preview(
                "<p>Обычное тело поста</p>",
                {
                    "template": {
                        "type": "bug_report",
                        "data": {
                            "status": "in_progress",
                            "platforms": ["windows", "android"],
                            "browsers": ["chrome", "yandex_browser"],
                        },
                    }
                },
            )

        self.assertEqual(
            preview["preview_content"],
            "<p>Платформы: Windows, Android<br>Браузеры: Chrome, Яндекс Браузер</p>",
        )
