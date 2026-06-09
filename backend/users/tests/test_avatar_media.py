from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from communities import service as community_service
from users import service as user_service
from users.avatar_media import AVATAR_VARIANT_WIDTHS, cache_external_avatar_for_user
from users.models import SiteUserProfile, TelegramAccount

User = get_user_model()


@override_settings(
    AWS_S3_CUSTOM_DOMAIN="media.tambur.pub",
    MEDIA_PUBLIC_URL_MODE="s3",
)
class UserAvatarMediaTests(TestCase):
    def test_site_user_avatar_url_does_not_return_external_telegram_avatar(self):
        user = User.objects.create_user(username="reader")
        TelegramAccount.objects.create(
            user=user,
            telegram_id=12345,
            username="reader_tg",
            avatar_url="https://t.me/i/userpic/320/avatar.jpg",
        )

        self.assertIsNone(community_service._site_user_avatar_url(None, user))

    def test_site_user_avatar_url_returns_cached_profile_avatar(self):
        user = User.objects.create_user(username="reader")
        SiteUserProfile.objects.create(
            user=user,
            avatar_url="https://media.tambur.pub/avatars/users/1/avatar-320.webp",
        )

        self.assertEqual(
            community_service._site_user_avatar_url(None, user),
            "https://media.tambur.pub/avatars/users/1/avatar-320.webp",
        )

    def test_site_user_avatar_url_does_not_return_external_profile_avatar(self):
        user = User.objects.create_user(username="reader")
        SiteUserProfile.objects.create(
            user=user,
            avatar_url="https://example.test/avatar.jpg",
        )

        self.assertIsNone(community_service._site_user_avatar_url(None, user))

    def test_cache_external_avatar_saves_variants_to_profile(self):
        user = User.objects.create_user(username="reader")
        saved = SimpleNamespace(
            default_url="https://media.tambur.pub/avatars/users/1/avatar-320.webp"
        )

        with patch(
            "users.avatar_media._download_external_avatar",
            return_value=(b"image-bytes", ".jpg"),
        ), patch("users.avatar_media.save_image_with_variants", return_value=saved) as save_mock:
            cached_url = cache_external_avatar_for_user(
                user,
                "https://example.test/avatar.jpg",
                source="telegram",
            )

        self.assertEqual(cached_url, saved.default_url)
        self.assertEqual(user.site_profile.avatar_url, saved.default_url)
        save_mock.assert_called_once()
        self.assertEqual(save_mock.call_args.kwargs["variant_widths"], AVATAR_VARIANT_WIDTHS)
        self.assertFalse(save_mock.call_args.kwargs["keep_original"])

    def test_update_site_profile_caches_external_avatar_url(self):
        user = User.objects.create_user(username="reader")
        cached_url = "https://media.tambur.pub/avatars/users/1/avatar-320.webp"

        with patch(
            "users.avatar_media.cache_external_avatar_for_user",
            return_value=cached_url,
        ) as cache_avatar:
            user_service._update_site_profile(user, avatar_url="https://example.test/avatar.jpg")

        self.assertEqual(user.site_profile.avatar_url, cached_url)
        cache_avatar.assert_called_once()
        self.assertEqual(cache_avatar.call_args.args[1], "https://example.test/avatar.jpg")
        self.assertEqual(cache_avatar.call_args.kwargs["source"], "profile")
        self.assertTrue(cache_avatar.call_args.kwargs["force"])
