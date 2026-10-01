import json
import base64
from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from feeds.models import Post
from feeds.preview import build_post_preview
from feeds.views import _extract_post_preview_image_urls, _serialize_post_preview_image_fields


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

    def test_social_image_uses_jpeg_proxy_endpoint(self) -> None:
        updated_at = datetime(2026, 7, 3, 10, 28, 2, tzinfo=dt_timezone.utc)
        post = Post(
            id=20026,
            preview_image_url="/media/uploads/post/stored-1280.webp",
            updated_at=updated_at,
        )

        preview = _serialize_post_preview_image_fields(None, post)

        self.assertEqual(
            preview["social_image_url"],
            "https://tambur.pub/api/posts/20026/social-image.jpg",
        )

    @patch("django.core.files.storage.default_storage.exists")
    def test_unknown_image_filename_does_not_probe_remote_storage(self, storage_exists) -> None:
        post = Post(preview_image_url="/media/uploads/post/original.jpg")

        preview_url, thumbnail_url = _extract_post_preview_image_urls(None, post)

        self.assertEqual(preview_url, "https://tambur.pub/media/uploads/post/original.jpg")
        self.assertEqual(thumbnail_url, "https://tambur.pub/media/uploads/post/original.jpg")
        storage_exists.assert_not_called()

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


class PostPreviewGalleryTests(SimpleTestCase):
    def preview(self, blocks, additional=None):
        return build_post_preview(json.dumps({"blocks": blocks, "additional": additional or {}}))

    def gallery(self, prefix="gallery"):
        return {"type": "gallery", "data": {"images": [
            {"url": f"/media/{prefix}-{i}.webp", "alt": f"Photo {i}"} for i in range(3)
        ]}}

    def test_leading_gallery_survives_preview_without_full_body(self):
        preview = self.preview([{"type": "paragraph", "data": {"text": "Hello"}}, self.gallery(), self.gallery("second")])
        self.assertEqual(preview["preview_content"], "<p>Hello</p>")
        self.assertEqual(preview["preview_gallery"], self.gallery()["data"]["images"])

    def test_image_before_gallery_and_explicit_cover_remain_single_images(self):
        self.assertEqual(self.preview([
            {"type": "image", "data": {"file": {"url": "/media/first.webp"}}}, self.gallery()
        ])["preview_gallery"], [])
        self.assertEqual(self.preview([self.gallery()], {"previewImage": "/media/cover.webp"})["preview_gallery"], [])

    def test_html_gallery_only_uses_first_group_and_preserves_entities(self):
        html = '<p>Hello</p><div class="post-gallery"><div><img src="/media/a.webp" alt="A &amp; B"></div><img src="/media/b.webp" /></div><div class="post-gallery"><img src="/media/c.webp"></div>'
        preview = build_post_preview(html)
        self.assertEqual(preview["preview_gallery"], [
            {"url": "/media/a.webp", "alt": "A & B"}, {"url": "/media/b.webp", "alt": ""}
        ])
        self.assertEqual(build_post_preview('<img src="/media/first.webp">' + html)["preview_gallery"], [])

    def test_single_image_duplicate_and_empty_galleries_do_not_create_navigation(self):
        gallery = {"type": "gallery", "data": {"images": [{"url": "/media/a.webp"}] * 3}}
        self.assertEqual(self.preview([gallery])["preview_gallery"], [])
        self.assertEqual(self.preview([{"type": "gallery", "data": {"images": []}}])["preview_gallery"], [])

    @override_settings(SITE_BASE_URL="https://tambur.pub", MEDIA_URL="/media/", MEDIA_PUBLIC_URL_MODE="legacy")
    @patch("django.core.files.storage.default_storage.exists")
    def test_serialization_uses_stored_gallery_and_does_not_probe_storage(self, exists):
        post = Post(preview_image_url="/media/a-1920.webp", preview_gallery=[
            {"url": "/media/a-1920.webp", "alt": "A"},
            {"url": "https://api.telegram.org/file/botSECRET/b.webp"},
            {"url": "/media/b-1920.webp", "alt": "B"},
        ])
        result = _serialize_post_preview_image_fields(None, post)
        self.assertEqual([item["url"] for item in result["preview_gallery"]], [
            "https://tambur.pub/media/a-1920.webp", "https://tambur.pub/media/b-1920.webp"
        ])
        self.assertEqual(result["preview_gallery"][0]["preview_url"], "https://tambur.pub/media/a-640.webp")
        exists.assert_not_called()

    def test_html_gallery_preserves_images_with_escaped_query_parameters(self):
        preview = build_post_preview('<div class="post-gallery"><img src="/media/a.webp?v=1&amp;x=2"><img src="/media/b.webp"></div>')
        self.assertEqual(len(preview["preview_gallery"]), 2)
        self.assertEqual(preview["preview_gallery"][0]["url"], "/media/a.webp?v=1&x=2")
