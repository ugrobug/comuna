from django.test import SimpleTestCase, override_settings

from rabotaem_backend.media_urls import (
    media_storage_path_from_url,
    public_url,
    rewrite_public_media_payload,
    rewrite_public_media_urls,
)


@override_settings(
    SITE_BASE_URL="https://tambur.pub",
    MEDIA_URL="/media/",
    MEDIA_LEGACY_URL="/media/",
    AWS_S3_CUSTOM_DOMAIN="media.tambur.pub",
)
class MediaUrlRewriteTests(SimpleTestCase):
    @override_settings(MEDIA_PUBLIC_URL_MODE="legacy")
    def test_legacy_mode_keeps_public_media_on_site_domain(self) -> None:
        self.assertEqual(
            public_url("/media/uploads/post/image.jpg"),
            "https://tambur.pub/media/uploads/post/image.jpg",
        )
        self.assertEqual(
            public_url("https://media.tambur.pub/uploads/post/image.jpg"),
            "https://media.tambur.pub/uploads/post/image.jpg",
        )

    @override_settings(MEDIA_PUBLIC_URL_MODE="s3")
    def test_s3_mode_rewrites_site_media_urls(self) -> None:
        self.assertEqual(
            public_url("https://tambur.pub/media/uploads/post/image.jpg"),
            "https://media.tambur.pub/uploads/post/image.jpg",
        )
        self.assertEqual(
            public_url("/media/uploads/post/image with spaces.jpg"),
            "https://media.tambur.pub/uploads/post/image%20with%20spaces.jpg",
        )

    @override_settings(MEDIA_PUBLIC_URL_MODE="s3")
    def test_s3_mode_does_not_rewrite_external_media_urls(self) -> None:
        self.assertEqual(
            public_url("https://example.com/media/uploads/post/image.jpg"),
            "https://example.com/media/uploads/post/image.jpg",
        )

    @override_settings(MEDIA_PUBLIC_URL_MODE="s3")
    def test_rewrites_public_media_inside_strings_and_payloads(self) -> None:
        html = '<img src="/media/uploads/post/a.jpg"><a href="https://example.com/media/b.jpg">'

        self.assertEqual(
            rewrite_public_media_urls(html),
            '<img src="https://media.tambur.pub/uploads/post/a.jpg"><a href="https://example.com/media/b.jpg">',
        )
        self.assertEqual(
            rewrite_public_media_payload({"image": "/media/uploads/post/a.jpg"}),
            {"image": "https://media.tambur.pub/uploads/post/a.jpg"},
        )

    @override_settings(MEDIA_PUBLIC_URL_MODE="s3")
    def test_extracts_storage_path_from_s3_public_url(self) -> None:
        self.assertEqual(
            media_storage_path_from_url("https://media.tambur.pub/uploads/post/a.jpg"),
            "uploads/post/a.jpg",
        )
