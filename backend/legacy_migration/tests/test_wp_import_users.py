from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from legacy_migration.models import LegacyWpUserMap
from legacy_migration.wp_import import upsert_django_user_for_wp_user

User = get_user_model()


def _wp_user(**kwargs):
    defaults = {
        "id": 266,
        "user_login": "legacy-author",
        "user_nicename": "legacy-author",
        "user_email": "author@example.com",
        "user_pass": "$P$BTC5k/OBMyL.g415E3OJ78ulgf5pND/",
        "display_name": "Legacy Author",
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class UpsertDjangoUserForWpUserTests(TestCase):
    def test_links_existing_user_by_email_without_changing_password(self) -> None:
        live = User.objects.create_user(
            username="live-user",
            email="author@example.com",
            password="tambur-secret",
        )
        old_password = live.password

        user, created, password_updated, linked = upsert_django_user_for_wp_user(_wp_user())

        self.assertFalse(created)
        self.assertTrue(linked)
        self.assertFalse(password_updated)
        self.assertEqual(user.pk, live.pk)
        self.assertEqual(user.password, old_password)
        self.assertTrue(
            LegacyWpUserMap.objects.filter(wp_user_id=266, user_id=live.pk).exists()
        )

    def test_creates_new_user_when_email_not_found(self) -> None:
        user, created, password_updated, linked = upsert_django_user_for_wp_user(
            _wp_user(user_email="new@example.com")
        )

        self.assertTrue(created)
        self.assertFalse(linked)
        self.assertTrue(password_updated)
        self.assertEqual(user.email, "new@example.com")

    def test_force_password_updates_linked_user(self) -> None:
        live = User.objects.create_user(
            username="live-user",
            email="author@example.com",
            password="tambur-secret",
        )

        user, created, password_updated, linked = upsert_django_user_for_wp_user(
            _wp_user(),
            force_password=True,
        )

        self.assertFalse(created)
        self.assertTrue(linked)
        self.assertTrue(password_updated)
        self.assertEqual(user.pk, live.pk)
        self.assertNotEqual(user.password, live.password)
        self.assertTrue(user.password.startswith("wordpress$"))
