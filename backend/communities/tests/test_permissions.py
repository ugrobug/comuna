import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from communities.models import Comun
from my_feed.models import ComunSubscriptionEvent, UserFeedSettings
from users import service as user_service


User = get_user_model()


class ComunManagementPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="community-owner", password="secret")
        self.moderator = User.objects.create_user(username="community-moderator", password="secret")
        self.staff = User.objects.create_user(
            username="site-admin",
            password="secret",
            is_staff=True,
        )
        self.outsider = User.objects.create_user(username="outsider", password="secret")
        self.comun = Comun.objects.create(
            name="Owner Community",
            slug="owner-community",
            creator=self.owner,
        )
        self.comun.moderators.add(self.moderator)
        self.url = reverse("comun-detail-manage", kwargs={"slug": self.comun.slug})

    def _authenticate(self, user):
        token = user_service._issue_token(user)
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {token}"

    def test_site_staff_is_not_community_moderator_by_default(self):
        self._authenticate(self.staff)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertFalse(payload["comun"]["can_moderate"])
        self.assertFalse(payload["comun"]["can_manage_moderators"])

    def test_site_staff_cannot_patch_unowned_community(self):
        self._authenticate(self.staff)

        response = self.client.patch(
            self.url,
            data=json.dumps({"product_description": "Staff edit"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403, response.content.decode())
        self.comun.refresh_from_db()
        self.assertNotEqual(self.comun.product_description, "Staff edit")

    def test_community_moderator_can_patch_community(self):
        self._authenticate(self.moderator)

        response = self.client.patch(
            self.url,
            data=json.dumps({"product_description": "Moderator edit"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.product_description, "Moderator edit")

    def test_ai_summary_prompt_is_visible_only_to_owner_when_ai_features_are_enabled(self):
        self.comun.telegram_ai_summary_enabled = True
        self.comun.telegram_ai_summary_prompt = "Выделяй решения и ответственных."
        self.comun.save(
            update_fields=[
                "telegram_ai_summary_enabled",
                "telegram_ai_summary_prompt",
                "updated_at",
            ]
        )

        self._authenticate(self.owner)
        response = self.client.get(f"{self.url}?include_settings=1")

        self.assertEqual(response.status_code, 200, response.content.decode())
        owner_payload = response.json()["comun"]
        self.assertTrue(owner_payload["telegram_ai_summary_enabled"])
        self.assertEqual(
            owner_payload["telegram_ai_summary_prompt"],
            "Выделяй решения и ответственных.",
        )

        self._authenticate(self.moderator)
        response = self.client.get(f"{self.url}?include_settings=1")

        self.assertEqual(response.status_code, 200, response.content.decode())
        moderator_payload = response.json()["comun"]
        self.assertTrue(moderator_payload["telegram_ai_summary_enabled"])
        self.assertNotIn("telegram_ai_summary_prompt", moderator_payload)

    def test_only_owner_of_ai_enabled_community_can_update_summary_prompt(self):
        self.comun.telegram_ai_summary_enabled = True
        self.comun.save(update_fields=["telegram_ai_summary_enabled", "updated_at"])

        self._authenticate(self.moderator)
        response = self.client.patch(
            self.url,
            data=json.dumps({"telegram_ai_summary_prompt": "Промт модератора"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403, response.content.decode())
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.telegram_ai_summary_prompt, "")

        self._authenticate(self.owner)
        response = self.client.patch(
            self.url,
            data=json.dumps({"telegram_ai_summary_prompt": "  Выделяй следующие шаги.  "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.telegram_ai_summary_prompt, "Выделяй следующие шаги.")

        self.comun.telegram_ai_summary_enabled = False
        self.comun.save(update_fields=["telegram_ai_summary_enabled", "updated_at"])
        response = self.client.patch(
            self.url,
            data=json.dumps({"telegram_ai_summary_prompt": "Новый промт"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403, response.content.decode())
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.telegram_ai_summary_prompt, "Выделяй следующие шаги.")

    def test_ai_summary_prompt_rejects_more_than_3000_characters(self):
        self.comun.telegram_ai_summary_enabled = True
        self.comun.save(update_fields=["telegram_ai_summary_enabled", "updated_at"])
        self._authenticate(self.owner)

        response = self.client.patch(
            self.url,
            data=json.dumps({"telegram_ai_summary_prompt": "x" * 3001}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400, response.content.decode())
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.telegram_ai_summary_prompt, "")

    def test_only_creator_can_manage_moderators(self):
        moderator_payload = {"moderator_ids": [self.moderator.id, self.outsider.id]}

        self._authenticate(self.moderator)

        response = self.client.patch(
            self.url,
            data=json.dumps(moderator_payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403, response.content.decode())
        self.assertFalse(self.comun.moderators.filter(id=self.outsider.id).exists())

        self._authenticate(self.owner)
        response = self.client.patch(
            self.url,
            data=json.dumps(moderator_payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertTrue(self.comun.moderators.filter(id=self.outsider.id).exists())
        moderator_settings = UserFeedSettings.objects.get(user=self.outsider)
        self.assertIn(self.comun.slug, moderator_settings.my_feed_comuns)
        existing_moderator_settings = UserFeedSettings.objects.get(user=self.moderator)
        self.assertIn(self.comun.slug, existing_moderator_settings.my_feed_comuns)
        owner_settings = UserFeedSettings.objects.get(user=self.owner)
        self.assertIn(self.comun.slug, owner_settings.my_feed_comuns)
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.subscribers_count, 3)
        self.assertEqual(
            ComunSubscriptionEvent.objects.filter(
                comun=self.comun,
                source=ComunSubscriptionEvent.SOURCE_MODERATOR_SYNC,
            ).count(),
            3,
        )

        response = self.client.patch(
            self.url,
            data=json.dumps(moderator_payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        moderator_settings.refresh_from_db()
        self.assertEqual(moderator_settings.my_feed_comuns.count(self.comun.slug), 1)
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.subscribers_count, 3)
        self.assertEqual(
            ComunSubscriptionEvent.objects.filter(
                comun=self.comun,
                source=ComunSubscriptionEvent.SOURCE_MODERATOR_SYNC,
            ).count(),
            3,
        )
