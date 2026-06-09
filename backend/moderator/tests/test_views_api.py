from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from feeds.models import Author, Post, PostComment, PostCommentLike, PostLike
from users import chat_service
from users.models import SiteChat, SiteChatMessage, SiteChatParticipantState, SiteChatReport
from users.service import _issue_token

User = get_user_model()


class ModeratorAnalyticsApiTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="password",
            is_staff=True,
        )
        self.user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="password",
        )
        self.staff_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.staff)}"}
        self.user_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.user)}"}

    def test_requires_staff_user(self):
        response = self.client.get(reverse("moderator-analytics"))
        self.assertEqual(response.status_code, 401)

        response = self.client.get(reverse("moderator-analytics"), **self.user_headers)
        self.assertEqual(response.status_code, 403)

        response = self.client.get(reverse("moderator-post-view-settings"))
        self.assertEqual(response.status_code, 401)

        response = self.client.get(reverse("moderator-post-view-settings"), **self.user_headers)
        self.assertEqual(response.status_code, 403)

        response = self.client.patch(
            reverse("moderator-post-view-setting-update", args=[1]),
            data='{"display_views_target": 10}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 401)

        response = self.client.patch(
            reverse("moderator-post-view-setting-update", args=[1]),
            data='{"display_views_target": 10}',
            content_type="application/json",
            **self.user_headers,
        )
        self.assertEqual(response.status_code, 403)

    def test_returns_period_analytics_for_staff(self):
        author = Author.objects.create(
            username="channel",
            channel_id=-1001,
            channel_url="https://t.me/channel",
        )
        site_author = Author.objects.create(username="site-author")
        comun = Comun.objects.create(name="Community", slug="community", creator=self.staff)
        telegram_post = Post.objects.create(
            author=author,
            message_id=1,
            title="Telegram post",
            source_url="",
            channel_url="https://t.me/channel",
            raw_data={
                "message_id": 1,
                "chat": {"id": -1001, "type": "channel", "username": "channel"},
            },
        )
        site_post = Post.objects.create(
            author=author,
            message_id=2,
            title="Site post",
            source_url="https://t.me/channel",
            channel_url="https://t.me/channel",
            raw_data={"source": "manual"},
        )
        manual_comun_post = Post.objects.create(
            author=site_author,
            message_id=3,
            title="Site comun post",
            raw_data={"source": "manual_comun", "comun_slug": comun.slug},
        )
        comment = PostComment.objects.create(post=telegram_post, user=self.user, body="Comment")
        PostLike.objects.create(post=telegram_post, user=self.user, value=1)
        PostCommentLike.objects.create(comment=comment, user=self.staff)
        Post.objects.filter(id=telegram_post.id).update(real_views_count=10)
        Post.objects.filter(id=site_post.id).update(real_views_count=5)
        Post.objects.filter(id=manual_comun_post.id).update(real_views_count=0)

        older = timezone.now() - timedelta(days=10)
        Post.objects.filter(id=site_post.id).update(created_at=older)
        Post.objects.filter(id=telegram_post.id).update(created_at=older)
        Post.objects.filter(id=manual_comun_post.id).update(created_at=older)
        Author.objects.filter(id__in=[author.id, site_author.id]).update(created_at=older)
        Comun.objects.filter(id=comun.id).update(created_at=older)
        PostComment.objects.filter(id=comment.id).update(created_at=older)
        PostLike.objects.update(created_at=older)
        PostCommentLike.objects.update(created_at=older)

        start = (older - timedelta(days=1)).date().isoformat()
        end = (older + timedelta(days=1)).date().isoformat()
        response = self.client.get(
            f"{reverse('moderator-analytics')}?from={start}&to={end}",
            **self.staff_headers,
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(
            data["totals"],
            {
                "communities": 1,
                "authors": 2,
                "comments": 1,
                "likes": 2,
                "posts_telegram": 1,
                "posts_site": 2,
                "post_real_views": 15,
                "average_real_views_per_post": 5.0,
            },
        )
        self.assertEqual(data["breakdown"]["post_likes"], 1)
        self.assertEqual(data["breakdown"]["comment_likes"], 1)

    def test_view_settings_can_be_listed_and_updated_by_staff(self):
        author = Author.objects.create(username="channel")
        post = Post.objects.create(
            author=author,
            message_id=10,
            title="Managed post",
            real_views_count=12,
        )
        post.set_display_views_target(40, save=True)

        response = self.client.get(reverse("moderator-post-view-settings"), **self.staff_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["posts"][0]["id"], post.id)
        self.assertEqual(data["posts"][0]["real_views_count"], 12)
        self.assertEqual(data["posts"][0]["display_views_target"], 40)

        response = self.client.patch(
            reverse("moderator-post-view-setting-update", args=[post.id]),
            data='{"display_views_target": 125}',
            content_type="application/json",
            **self.staff_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["post"]["display_views_target"], 125)
        post.refresh_from_db()
        self.assertEqual(post.display_views_target, 125)

    def test_chat_report_block_hides_chat_and_moderator_can_review_it(self):
        reported_user = User.objects.create_user(
            username="reported",
            email="reported@example.com",
            password="password",
        )
        reported_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(reported_user)}"}
        chat, _created = chat_service.get_or_create_chat_for_users(self.user, reported_user)
        message = SiteChatMessage.objects.create(
            chat=chat,
            sender=reported_user,
            body="spam message",
        )
        SiteChat.objects.filter(id=chat.id).update(
            last_message=message,
            last_message_at=message.created_at,
            updated_at=message.created_at,
        )

        response = self.client.post(
            reverse("auth-chat-report-block", args=[chat.id]),
            **self.user_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertTrue(data["blocked"])
        self.assertEqual(data["report"]["message"]["body"], "spam message")

        self.assertTrue(
            SiteChatParticipantState.objects.filter(
                chat=chat,
                user=self.user,
                is_blocked=True,
                hidden_at__isnull=False,
            ).exists()
        )
        self.assertEqual(SiteChatReport.objects.filter(chat=chat).count(), 1)

        response = self.client.get(reverse("auth-chat-detail", args=[chat.id]), **self.user_headers)
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse("auth-chat-messages", args=[chat.id]),
            data='{"body": "still here"}',
            content_type="application/json",
            **reported_headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"], "chat is blocked")

        response = self.client.get(reverse("moderator-chat-reports"), **self.staff_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["open_count"], 1)
        self.assertEqual(data["reports"][0]["message"]["body"], "spam message")

        report_id = data["reports"][0]["id"]
        response = self.client.patch(
            reverse("moderator-chat-report-update", args=[report_id]),
            data='{"status": "reviewed"}',
            content_type="application/json",
            **self.staff_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["report"]["status"], SiteChatReport.STATUS_REVIEWED)
        self.assertEqual(data["open_count"], 0)
