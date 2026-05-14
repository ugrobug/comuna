from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from feeds.models import Author, Post, PostComment, PostCommentLike, PostLike
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

    def test_returns_period_analytics_for_staff(self):
        author = Author.objects.create(username="channel", channel_url="https://t.me/channel")
        site_author = Author.objects.create(username="site-author")
        comun = Comun.objects.create(name="Community", slug="community", creator=self.staff)
        telegram_post = Post.objects.create(
            author=author,
            message_id=1,
            title="Telegram post",
            source_url="https://t.me/channel/1",
            channel_url="https://t.me/channel",
            raw_data={"message_id": 1},
        )
        site_post = Post.objects.create(
            author=site_author,
            message_id=2,
            title="Site post",
            raw_data={"source": "manual"},
        )
        comment = PostComment.objects.create(post=telegram_post, user=self.user, body="Comment")
        PostLike.objects.create(post=telegram_post, user=self.user, value=1)
        PostCommentLike.objects.create(comment=comment, user=self.staff)

        older = timezone.now() - timedelta(days=10)
        Post.objects.filter(id=site_post.id).update(created_at=older)
        Post.objects.filter(id=telegram_post.id).update(created_at=older)
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
                "posts_site": 1,
            },
        )
        self.assertEqual(data["breakdown"]["post_likes"], 1)
        self.assertEqual(data["breakdown"]["comment_likes"], 1)
