from unittest.mock import patch

from django.test import SimpleTestCase

from feeds.cache_signals import invalidate_post_detail_cache


class PostDetailCacheInvalidationTests(SimpleTestCase):
    @patch("feeds.cache_signals.bump_public_cache_prefix")
    def test_content_update_invalidates_cached_post_detail(self, bump_cache):
        invalidate_post_detail_cache(
            sender=None,
            instance=None,
            created=False,
            update_fields=frozenset({"content", "updated_at"}),
        )

        bump_cache.assert_called_once_with("post-detail")

    @patch("feeds.cache_signals.bump_public_cache_prefix")
    def test_new_post_invalidates_cached_post_detail(self, bump_cache):
        invalidate_post_detail_cache(
            sender=None,
            instance=None,
            created=True,
            update_fields=None,
        )

        bump_cache.assert_called_once_with("post-detail")

    @patch("feeds.cache_signals.bump_public_cache_prefix")
    def test_view_counter_update_does_not_invalidate_cached_post_detail(self, bump_cache):
        invalidate_post_detail_cache(
            sender=None,
            instance=None,
            created=False,
            update_fields=frozenset({"real_views_count", "updated_at"}),
        )

        bump_cache.assert_not_called()
