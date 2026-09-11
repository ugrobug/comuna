import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from editor.management.commands.publish_scheduled_posts import publish_due_posts
from feeds.models import Post
from users.service import _issue_token


class ScheduledPublicationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="scheduled-author", password="secret")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {_issue_token(self.user)}"
        self.comun = Comun.objects.create(name="Scheduled", slug="scheduled", creator=self.user)
        self.due = timezone.now() + timedelta(hours=2)
        self.payload = {
            "title": "Отложенный пост", "content": "Текст поста", "author_source": "site",
            "comun_slug": self.comun.slug, "publish_at": self.due.isoformat(),
        }

    def create(self, **changes):
        response = self.client.post(reverse("auth-posts"), data=json.dumps({**self.payload, **changes}), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content.decode())
        return Post.objects.get(id=response.json()["post"]["id"])

    def update(self, post, **changes):
        return self.client.patch(reverse("auth-post-update", args=[post.id]), data=json.dumps(changes), content_type="application/json")

    def test_scheduled_post_is_private_until_due_and_published_once(self):
        with patch("communities.service._maybe_notify_post_published_to_subscribers") as notify:
            post = self.create()
            self.assertTrue(post.is_pending)
            self.assertEqual(post.publish_at, self.due)
            notify.assert_not_called()
            self.assertEqual(self.client.get(reverse("post-detail", args=[post.id])).status_code, 404)
            self.assertEqual(publish_due_posts(now=self.due - timedelta(microseconds=1)), 0)
            with patch("django.utils.timezone.now", return_value=self.due):
                self.assertEqual(publish_due_posts(now=self.due), 1)
                self.assertEqual(publish_due_posts(now=self.due), 0)
                self.assertEqual(self.client.get(reverse("post-detail", args=[post.id])).status_code, 200)
            notify.assert_called_once()
            post.refresh_from_db()
            self.assertFalse(post.is_pending)
            self.assertNotIn("scheduled_publication", post.raw_data)
            self.assertEqual(post.created_at, self.due)

    def test_community_endpoint_supports_schedule(self):
        response = self.client.post(reverse("comun-posts", args=[self.comun.slug]), data=json.dumps(self.payload), content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertTrue(response.json()["post"]["is_scheduled"])
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.authors_count, 0)

    def test_draft_saves_date_without_arming_publication(self):
        post = self.create(is_draft=True)
        self.assertEqual(post.publish_at, self.due)
        self.assertEqual(publish_due_posts(now=self.due + timedelta(days=1)), 0)
        response = self.update(post, is_draft=False)
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertTrue(response.json()["post"]["is_scheduled"])

    def test_omitted_date_publishes_immediately(self):
        del self.payload["publish_at"]
        post = self.create()
        self.assertFalse(post.is_pending)
        self.assertIsNone(post.publish_at)

    def test_null_date_publishes_immediately(self):
        post = self.create(publish_at=None)
        self.assertFalse(post.is_pending)

    def test_invalid_and_past_dates_are_rejected_on_both_endpoints(self):
        for url in (reverse("auth-posts"), reverse("comun-posts", args=[self.comun.slug])):
            for value in ("bad", "2026-99-01T00:00:00Z", 123, {}, "2035-01-01T10:00:00", (timezone.now() - timedelta(seconds=1)).isoformat()):
                with self.subTest(url=url, value=value):
                    response = self.client.post(url, data=json.dumps({**self.payload, "publish_at": value}), content_type="application/json")
                    self.assertEqual(response.status_code, 400)
        self.assertEqual(Post.objects.count(), 0)

    def test_offset_is_converted_to_same_instant(self):
        from datetime import timezone as dt_timezone
        post = self.create(publish_at=self.due.astimezone(dt_timezone(timedelta(hours=3))).isoformat())
        self.assertEqual(post.publish_at, self.due)

    def test_reschedule_edit_and_cancel_to_draft(self):
        post = self.create()
        later = self.due + timedelta(days=1)
        response = self.update(post, publish_at=later.isoformat())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.update(post, title="Обновлённый заголовок").status_code, 200)
        self.assertEqual(publish_due_posts(now=self.due), 0)
        response = self.update(post, is_draft=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["post"]["is_draft"])
        self.assertFalse(response.json()["post"]["is_scheduled"])
        self.assertEqual(publish_due_posts(now=later + timedelta(seconds=1)), 0)

    def test_removing_date_publishes_scheduled_post_now(self):
        post = self.create()
        with patch("feeds.views._maybe_notify_post_published_to_subscribers") as notify:
            response = self.update(post, publish_at=None)
            self.assertEqual(response.status_code, 200, response.content.decode())
            self.assertFalse(response.json()["post"]["is_pending"])
            notify.assert_called_once()
        self.assertEqual(publish_due_posts(now=self.due), 0)

    def test_cannot_reschedule_already_published_post(self):
        post = self.create(publish_at=None)
        self.assertEqual(self.update(post, publish_at=self.due.isoformat()).status_code, 400)

    def test_overdue_draft_requires_new_time_before_publication(self):
        post = self.create(is_draft=True)
        with patch("django.utils.timezone.now", return_value=self.due + timedelta(seconds=1)):
            self.assertEqual(self.update(post, is_draft=False).status_code, 400)
            self.assertEqual(self.update(post, is_draft=False, publish_at=None).status_code, 200)

    def test_worker_catches_up_after_downtime_but_skips_deleted_posts(self):
        deleted = self.create()
        post = self.create(title="После простоя")
        self.client.delete(reverse("auth-post-update", args=[deleted.id]))
        self.assertEqual(publish_due_posts(now=self.due + timedelta(days=2)), 1)
        deleted.refresh_from_db()
        post.refresh_from_db()
        self.assertTrue(deleted.is_pending)
        self.assertFalse(post.is_pending)

    def test_other_user_cannot_read_edit_or_cancel_scheduled_post(self):
        post = self.create()
        other = get_user_model().objects.create_user(username="other", password="secret")
        self.client.defaults["HTTP_AUTHORIZATION"] = f"Bearer {_issue_token(other)}"
        self.assertEqual(self.update(post, publish_at=None).status_code, 403)
        self.assertEqual(self.client.get(reverse("auth-post-update", args=[post.id])).status_code, 403)
        self.assertEqual(self.client.delete(reverse("auth-post-update", args=[post.id])).status_code, 403)

    def test_owner_listing_includes_schedule_when_requested(self):
        post = self.create()
        self.assertEqual(self.client.get(reverse("auth-posts"), {"drafts_only": "1"}).json()["total"], 0)
        response = self.client.get(reverse("auth-posts"), {"drafts_only": "1", "include_scheduled": "1"})
        self.assertEqual(response.json()["posts"][0]["id"], post.id)
        self.assertTrue(response.json()["posts"][0]["is_scheduled"])

    def test_failed_post_does_not_block_other_posts_and_can_be_retried(self):
        failed = self.create()
        other = self.create(title="Следующий пост")

        def notify(post, **kwargs):
            if post.id == failed.id:
                raise RuntimeError("Temporary notification failure")

        with patch("communities.service._maybe_notify_post_published_to_subscribers", side_effect=notify):
            with self.assertLogs("editor.management.commands.publish_scheduled_posts", level="ERROR"):
                self.assertEqual(publish_due_posts(now=self.due, continue_on_error=True), 1)
        failed.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(failed.is_pending)
        self.assertFalse(other.is_pending)
        self.assertEqual(publish_due_posts(now=self.due), 1)

    @patch("editor.management.commands.publish_scheduled_posts.close_old_connections")
    def test_management_command_publishes_due_posts_and_rebuilds_feed(self, _close_connections):
        from django.core.management import call_command
        from io import StringIO
        post = self.create()
        with patch("django.utils.timezone.now", return_value=self.due):
            with patch("editor.management.commands.publish_scheduled_posts.call_command") as rebuild:
                call_command("publish_scheduled_posts", stdout=StringIO())
        rebuild.assert_called_once()
        self.assertEqual(rebuild.call_args.args[0], "rebuild_public_feed")
        post.refresh_from_db()
        self.assertFalse(post.is_pending)
