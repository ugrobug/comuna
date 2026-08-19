import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from editor.service import _normalize_post_template_payload
from feeds.models import Author, Post, PostEventAttendance
from notifications.event_reminders import send_event_reminders_due
from notifications.models import SiteNotification
from users.service import _issue_token


User = get_user_model()


class EventTemplateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="event_guest", password="password")
        self.author = Author.objects.create(username="event_author", title="Event author")
        self.starts_at = timezone.now() + timedelta(hours=23)
        self.post = Post.objects.create(
            author=self.author,
            message_id=3001,
            title="Tambur meetup",
            content="Event body",
            event_starts_at=self.starts_at,
            raw_data={
                "template": {
                    "type": "event",
                    "version": 1,
                    "data": {"starts_at": self.starts_at.isoformat()},
                }
            },
        )

    def headers_for(self, user):
        return {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(user)}"}

    def test_event_template_datetime_is_normalized_to_utc(self):
        template, error = _normalize_post_template_payload(
            {
                "type": "event",
                "data": {"starts_at": "2026-08-20T18:30:00+03:00"},
            }
        )

        self.assertIsNone(error)
        self.assertEqual(template["data"]["starts_at"], "2026-08-20T15:30:00Z")

    def test_user_can_join_and_leave_future_event(self):
        join_response = self.client.post(
            f"/api/posts/{self.post.id}/event-attendance/",
            data=json.dumps({"attending": True}),
            content_type="application/json",
            **self.headers_for(self.user),
        )

        self.assertEqual(join_response.status_code, 200)
        self.assertTrue(join_response.json()["event_attendance"]["is_attending"])
        self.assertTrue(PostEventAttendance.objects.filter(post=self.post, user=self.user).exists())

        leave_response = self.client.post(
            f"/api/posts/{self.post.id}/event-attendance/",
            data=json.dumps({"attending": False}),
            content_type="application/json",
            **self.headers_for(self.user),
        )

        self.assertEqual(leave_response.status_code, 200)
        self.assertFalse(leave_response.json()["event_attendance"]["is_attending"])
        self.assertFalse(PostEventAttendance.objects.filter(post=self.post, user=self.user).exists())

    def test_reminder_is_sent_only_once(self):
        attendance = PostEventAttendance.objects.create(post=self.post, user=self.user)

        self.assertEqual(send_event_reminders_due(), 1)
        self.assertEqual(send_event_reminders_due(), 0)

        attendance.refresh_from_db()
        self.assertIsNotNone(attendance.reminder_sent_at)
        notifications = SiteNotification.objects.filter(
            user=self.user,
            event_key="event_reminder",
        )
        self.assertEqual(notifications.count(), 1)
        self.assertIn(self.post.title, notifications.get().message)
