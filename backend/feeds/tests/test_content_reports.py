from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from feeds.models import Author, ContentReport, Post, PostComment
from users.service import _issue_token

User = get_user_model()


class ContentReportsApiTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user(
            username="reporter",
            email="reporter@example.com",
            password="password",
        )
        self.comment_author = User.objects.create_user(
            username="comment-author",
            email="comment-author@example.com",
            password="password",
        )
        self.staff = User.objects.create_user(
            username="staff-reporter",
            email="staff-reporter@example.com",
            password="password",
            is_staff=True,
        )
        self.reporter_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.reporter)}"
        }
        self.staff_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.staff)}"}
        self.author = Author.objects.create(username="reported-channel")
        self.post = Post.objects.create(
            author=self.author,
            message_id=101,
            title="Reported post",
            content="Reported post body",
        )
        self.comment = PostComment.objects.create(
            post=self.post,
            user=self.comment_author,
            body="Reported comment body",
        )

    def _post_json(self, url: str, payload: dict, **headers):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            **headers,
        )

    def test_post_report_requires_auth_and_valid_reason_and_is_idempotent(self):
        url = reverse("post-report", args=[self.post.id])

        response = self._post_json(url, {"reason": "spam_fraud"})
        self.assertEqual(response.status_code, 401)

        response = self._post_json(url, {"reason": "unknown"}, **self.reporter_headers)
        self.assertEqual(response.status_code, 400)

        response = self._post_json(url, {"reason": "spam_fraud"}, **self.reporter_headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["created"])

        duplicate = self._post_json(url, {"reason": "other"}, **self.reporter_headers)
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(duplicate.json()["created"])
        self.assertEqual(ContentReport.objects.filter(post=self.post).count(), 1)
        report = ContentReport.objects.get(post=self.post)
        self.assertEqual(report.reason, ContentReport.REASON_SPAM_FRAUD)
        self.assertEqual(report.title_snapshot, "Reported post")

    def test_comment_report_appears_in_moderation_and_can_be_reviewed(self):
        response = self._post_json(
            reverse("comment-report", args=[self.comment.id]),
            {"reason": "harassment"},
            **self.reporter_headers,
        )
        self.assertEqual(response.status_code, 200)
        report = ContentReport.objects.get(comment=self.comment)
        self.assertEqual(report.content_snapshot, "Reported comment body")

        response = self.client.get(reverse("moderator-content-reports"))
        self.assertEqual(response.status_code, 401)

        response = self.client.get(
            reverse("moderator-content-reports"),
            **self.staff_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["open_count"], 1)
        self.assertEqual(data["reports"][0]["target_type"], "comment")
        self.assertEqual(data["reports"][0]["reason_label"], "Травля")
        self.assertIn(f"#site-comment-{self.comment.id}", data["reports"][0]["target"]["url"])

        response = self.client.patch(
            reverse("moderator-content-report-update", args=[report.id]),
            data=json.dumps({"status": "reviewed"}),
            content_type="application/json",
            **self.staff_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["report"]["status"], ContentReport.STATUS_REVIEWED)
        self.assertEqual(data["open_count"], 0)
        report.refresh_from_db()
        self.assertEqual(report.reviewed_by, self.staff)
        self.assertIsNotNone(report.reviewed_at)
