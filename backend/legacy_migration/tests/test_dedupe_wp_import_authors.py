from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from feeds.models import Author, Post
from legacy_migration.models import LegacyWpUserMap
from legacy_migration.wp_import import dedupe_wp_import_authors_for_user


class DedupeWpImportAuthorsTests(TestCase):
    @patch("legacy_migration.wp_import.WpUsers")
    def test_merges_suffix_duplicates_keeps_channel_jeckmod(self, wp_users_model) -> None:
        wp_users_model.objects.filter.return_value.first.return_value = SimpleNamespace(
            id=266,
            user_login="jeckmod",
            user_nicename="jeckmod",
            display_name="Channel",
        )
        channel = Author.objects.create(
            username="jeckmod",
            title="Channel",
            channel_url="https://t.me/jeckmod",
        )
        a1 = Author.objects.create(username="jeckmod-wp266", title="WP")
        a2 = Author.objects.create(username="jeckmod-wp266-2", title="WP dup")
        Post.objects.create(
            author=a2,
            title="t",
            content="{}",
            message_id=1,
        )
        LegacyWpUserMap.objects.create(
            wp_user_id=266,
            wp_login="jeckmod",
            author=a2,
        )

        result = dedupe_wp_import_authors_for_user(266, dry_run=False)
        self.assertEqual(result["status"], "merged")
        self.assertEqual(result["merged"], 2)
        self.assertTrue(Author.objects.filter(pk=channel.id).exists())
        self.assertFalse(Author.objects.filter(pk=a2.id).exists())
        self.assertFalse(Author.objects.filter(pk=a1.id).exists())
        self.assertEqual(Post.objects.get(message_id=1).author_id, channel.id)
        map_row = LegacyWpUserMap.objects.get(wp_user_id=266)
        self.assertEqual(map_row.author_id, channel.id)
