from django.test import SimpleTestCase, override_settings

from feeds.management.commands.rehydrate_post_images import Command


class RehydratePostImagesUrlTests(SimpleTestCase):
    @override_settings(
        MEDIA_PUBLIC_URL_MODE="s3",
        AWS_S3_CUSTOM_DOMAIN="media.tambur.pub",
        AWS_LOCATION="",
    )
    def test_s3_public_url_is_already_local(self) -> None:
        self.assertTrue(
            Command._is_local_url(
                "https://media.tambur.pub/posts/telegram/photo-1280.webp"
            )
        )

    @override_settings(
        SITE_BASE_URL="https://tambur.pub",
        MEDIA_URL="/media/",
    )
    def test_legacy_media_url_is_already_local(self) -> None:
        self.assertTrue(
            Command._is_local_url("https://tambur.pub/media/posts/telegram/photo.jpg")
        )

    def test_external_url_is_not_local(self) -> None:
        self.assertFalse(Command._is_local_url("https://example.com/photo.jpg"))
