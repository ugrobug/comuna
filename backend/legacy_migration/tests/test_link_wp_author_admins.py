from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from feeds.models import Author
from legacy_migration.models import LegacyWpUserMap
from legacy_migration.wp_import import ensure_author_admin_for_legacy_map
from users.models import AuthorAdmin

User = get_user_model()


class LinkWpAuthorAdminsTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(username="legacy-user", password="x")
        self.author = Author.objects.create(
            username="legacy-user-wp266",
            title="Legacy User",
            channel_url="",
            channel_id=None,
        )
        self.map_row = LegacyWpUserMap.objects.create(
            wp_user_id=266,
            wp_login="legacy-user",
            author=self.author,
            user=self.user,
            imported_at=timezone.now(),
        )

    def test_creates_verified_author_admin(self) -> None:
        result = ensure_author_admin_for_legacy_map(self.map_row)
        self.assertEqual(result, "created")
        link = AuthorAdmin.objects.get(user=self.user, author=self.author)
        self.assertIsNotNone(link.verified_at)

    def test_idempotent_second_run(self) -> None:
        ensure_author_admin_for_legacy_map(self.map_row)
        result = ensure_author_admin_for_legacy_map(self.map_row)
        self.assertEqual(result, "exists")
        self.assertEqual(AuthorAdmin.objects.filter(user=self.user, author=self.author).count(), 1)

    def test_verifies_existing_unverified_link(self) -> None:
        AuthorAdmin.objects.create(user=self.user, author=self.author, verified_at=None)
        result = ensure_author_admin_for_legacy_map(self.map_row)
        self.assertEqual(result, "verified")
        link = AuthorAdmin.objects.get(user=self.user, author=self.author)
        self.assertIsNotNone(link.verified_at)

    def test_conflict_when_author_linked_to_other_user(self) -> None:
        other = User.objects.create_user(username="other", password="x")
        AuthorAdmin.objects.create(user=other, author=self.author, verified_at=timezone.now())
        result = ensure_author_admin_for_legacy_map(self.map_row)
        self.assertEqual(result, "conflict")
        self.assertFalse(AuthorAdmin.objects.filter(user=self.user, author=self.author).exists())
