import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import resolve
from django.utils import timezone

from editor import views as editor_views
from feeds.models import Author, Post, PostDraftAccess
from notifications.models import SiteNotification
from users.models import AuthorAdmin
from users.service import _issue_token

User = get_user_model()


class EditorViewsRoutingTests(SimpleTestCase):
    def test_editor_routes_resolve_to_editor_app(self):
        self.assertIs(resolve("/api/auth/post-templates/movie-review/autofill/").func, editor_views.auth_movie_review_autofill)
        self.assertIs(resolve("/api/auth/posts/").func, editor_views.user_posts)
        self.assertIs(resolve("/api/auth/posts/1/").func, editor_views.user_post_update)
        self.assertIs(resolve("/api/auth/drafts/1/access/").func, editor_views.draft_access)
        self.assertIs(resolve("/api/auth/drafts/shared/token/").func, editor_views.shared_draft_detail)
        self.assertIs(resolve("/api/auth/uploads/").func, editor_views.user_upload)
        self.assertIs(resolve("/api/posts/1/poll-vote/").func, editor_views.post_poll_vote)
        self.assertIs(resolve("/api/posts/1/rating-vote/").func, editor_views.post_rating_vote)
        self.assertIs(
            resolve("/api/posts/1/bug-report-confirmation/").func,
            editor_views.bug_report_confirmation_update,
        )


class DraftAccessApiTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="draft-owner", password="password")
        self.recipient = User.objects.create_user(username="draft-reader", password="password")
        self.outsider = User.objects.create_user(username="draft-outsider", password="password")
        self.author = Author.objects.create(username="draft-author")
        AuthorAdmin.objects.create(
            user=self.owner,
            author=self.author,
            verified_at=timezone.now(),
        )
        self.post = Post.objects.create(
            author=self.author,
            message_id=91001,
            title="Shared draft",
            content="Draft body",
            is_pending=True,
            raw_data={"draft": True, "draft_share_token": "shared-draft-token"},
        )
        self.owner_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.owner)}"
        }
        self.recipient_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.recipient)}"
        }
        self.outsider_headers = {
            "HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.outsider)}"
        }

    def _access_json(self, method: str, user_id: int, **headers):
        return getattr(self.client, method)(
            f"/api/auth/drafts/{self.post.id}/access/",
            data=json.dumps({"user_id": user_id}),
            content_type="application/json",
            **headers,
        )

    def test_owner_can_grant_and_revoke_draft_access(self):
        shared_url = "/api/auth/drafts/shared/shared-draft-token/"
        response = self.client.get(shared_url, **self.recipient_headers)
        self.assertEqual(response.status_code, 403)

        response = self._access_json(
            "post",
            self.recipient.id,
            **self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["created"])
        self.assertTrue(
            PostDraftAccess.objects.filter(post=self.post, user=self.recipient).exists()
        )
        notification = SiteNotification.objects.get(
            user=self.recipient,
            event_key="draft_shared",
        )
        self.assertEqual(notification.link_url, "/drafts/shared-draft-token")

        response = self.client.get(shared_url, **self.recipient_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["post"]["id"], self.post.id)

        response = self._access_json(
            "delete",
            self.recipient.id,
            **self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["deleted"])
        self.assertFalse(
            PostDraftAccess.objects.filter(post=self.post, user=self.recipient).exists()
        )
        response = self.client.get(shared_url, **self.recipient_headers)
        self.assertEqual(response.status_code, 403)

    def test_only_owner_can_manage_access_and_search_users(self):
        response = self.client.get(
            f"/api/auth/drafts/{self.post.id}/access/?q=draft-reader",
            **self.owner_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["users"][0]["id"], self.recipient.id)

        response = self._access_json(
            "post",
            self.recipient.id,
            **self.outsider_headers,
        )
        self.assertEqual(response.status_code, 403)
