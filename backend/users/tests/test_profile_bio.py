import json

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from users.models import SiteUserProfile
from users.serializers import _serialize_public_site_user_profile
from users.service import _delete_site_user_account, _issue_token, _merge_site_profiles

User = get_user_model()


class ProfileBioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="bio_owner")
        self.profile = SiteUserProfile.objects.create(user=self.user, display_name="Reader")
        self.token = _issue_token(self.user)
        self.url = f"/api/site-users/{self.user.id}/profile/"

    def update(self, payload):
        return self.client.patch(
            "/api/auth/me/", data=json.dumps(payload), content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    def test_save_read_and_clear_with_paragraphs(self):
        response = self.update({"bio": "  О себе\r\n\r\nЛюблю кино 👋  "})
        self.assertEqual(response.status_code, 200)
        expected = "О себе\n\nЛюблю кино 👋"
        self.assertEqual(response.json()["user"]["bio"], expected)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, expected)
        self.assertEqual(self.client.get(self.url).json()["user"]["bio"], expected)
        me = self.client.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(me.json()["user"]["bio"], expected)
        self.assertEqual(self.update({"bio": "\n "}).status_code, 200)
        self.assertIsNone(self.client.get(self.url).json()["user"]["bio"])

    def test_public_profile_cannot_cache_personal_bio_after_edit_or_deletion(self):
        for bio in ("", "Public biography", ""):
            self.assertEqual(self.update({"bio": bio}).status_code, 200)
            response = self.client.get(self.url)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertIn("private", response["Cache-Control"])
            self.assertEqual(response.json()["user"]["bio"], bio or None)

    def test_omitted_bio_preserves_value_for_old_clients(self):
        self.update({"bio": "Keep me"})
        self.assertEqual(self.update({"display_name": "New name"}).status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "Keep me")

    def test_limits_and_types_are_validated_before_writes(self):
        self.assertEqual(self.update({"bio": "я" * 2000}).status_code, 200)
        for invalid in ("x" * 2001, 123, [], {}, True, "bad\x00text"):
            with self.subTest(value_type=type(invalid).__name__):
                response = self.update({"bio": invalid, "display_name": "Invalid change"})
                self.assertEqual(response.status_code, 400)
                self.profile.refresh_from_db()
                self.assertEqual(self.profile.bio, "я" * 2000)
                self.assertEqual(self.profile.display_name, "Reader")

    def test_guest_cannot_write_and_owner_cannot_change_another_profile(self):
        self.assertEqual(self.client.patch("/api/auth/me/", data='{"bio":"hack"}', content_type="application/json").status_code, 401)
        other = User.objects.create_user(username="bio_other")
        profile = SiteUserProfile.objects.create(user=other, bio="Private edit")
        response = self.update({"bio": "Mine", "user_id": other.id})
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.bio, "Private edit")

    def test_deleted_and_inactive_user_bio_is_not_public(self):
        self.profile.bio = "Personal details"
        self.profile.save()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertIsNone(self.client.get(self.url).json()["user"]["bio"])
        self.user.is_active = True
        self.user.save(update_fields=["is_active"])
        _delete_site_user_account(self.user)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "")
        self.assertIsNone(self.client.get(self.url).json()["user"]["bio"])

    def test_merge_preserves_target_bio_or_uses_source_when_empty(self):
        source = User.objects.create_user(username="bio_source")
        SiteUserProfile.objects.create(user=source, bio="Source bio")
        _merge_site_profiles(self.user, source)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "Source bio")
        SiteUserProfile.objects.create(user=source, bio="Other bio")
        _merge_site_profiles(self.user, source)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, "Source bio")

    def test_bio_adds_no_queries_or_extra_payload_collections(self):
        self.client.get(self.url)
        with CaptureQueriesContext(connection) as empty_queries:
            empty = self.client.get(self.url).json()
        self.update({"bio": "я" * 2000})
        with CaptureQueriesContext(connection) as full_queries:
            full = self.client.get(self.url).json()
        self.assertEqual(len(full_queries), len(empty_queries))
        self.assertLessEqual(len(full_queries), 5)
        self.assertEqual(full["user"]["bio"], "я" * 2000)
        full["user"]["bio"] = None
        self.assertEqual(full, empty)
        user = User.objects.select_related("site_profile", "telegram_account", "vk_account").get(pk=self.user.pk)
        with self.assertNumQueries(0):
            self.assertEqual(_serialize_public_site_user_profile(None, user)["bio"], "я" * 2000)
