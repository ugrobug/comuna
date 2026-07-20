from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from feeds.models import Author, Post, PostComment, PostDailyView
from my_feed.models import ComunSubscriptionEvent
from users.service import _issue_token


User = get_user_model()


class ComunAnalyticsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="analytics-owner", password="secret")
        self.moderator = User.objects.create_user(username="analytics-moderator", password="secret")
        self.outsider = User.objects.create_user(username="analytics-outsider", password="secret")
        self.author = Author.objects.create(username="analytics-author")
        self.comun = Comun.objects.create(
            name="Analytics Community",
            slug="analytics-community",
            creator=self.owner,
            subscribers_count=12,
            analytics_tracking_started_at=timezone.now() - timedelta(days=30),
        )
        self.comun.moderators.add(self.moderator)
        self.owner_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.owner)}"}
        self.moderator_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.moderator)}"}
        self.outsider_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.outsider)}"}
        self.post = Post.objects.create(
            author=self.author,
            message_id=1,
            title="Community post",
            real_views_count=41,
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
        )
        self.url = reverse("comun-analytics", kwargs={"slug": self.comun.slug})

    def _at_date(self, date):
        return timezone.make_aware(datetime.combine(date, time(hour=12)))

    def test_analytics_requires_community_management_access(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

        self.assertEqual(self.client.get(self.url, **self.outsider_headers).status_code, 403)

        self.assertEqual(self.client.get(self.url, **self.moderator_headers).status_code, 200)

    def test_analytics_returns_period_totals_and_daily_series(self):
        today = timezone.localdate()
        PostDailyView.objects.create(post=self.post, date=today, views_count=5)
        PostDailyView.objects.create(post=self.post, date=today - timedelta(days=3), views_count=7)
        PostDailyView.objects.create(post=self.post, date=today - timedelta(days=12), views_count=11)

        comments = [
            PostComment.objects.create(post=self.post, user=self.owner, body="Today"),
            PostComment.objects.create(post=self.post, user=self.owner, body="Week"),
            PostComment.objects.create(post=self.post, user=self.owner, body="Month"),
        ]
        comment_dates = [today, today - timedelta(days=3), today - timedelta(days=12)]
        for comment, date in zip(comments, comment_dates, strict=True):
            PostComment.objects.filter(id=comment.id).update(created_at=self._at_date(date))

        subscription = ComunSubscriptionEvent.objects.create(
            user=self.outsider,
            comun=self.comun,
            comun_slug=self.comun.slug,
        )
        ComunSubscriptionEvent.objects.filter(id=subscription.id).update(
            created_at=self._at_date(today - timedelta(days=3))
        )
        unsubscribe = ComunSubscriptionEvent.objects.create(
            user=self.outsider,
            comun=self.comun,
            comun_slug=self.comun.slug,
            action=ComunSubscriptionEvent.ACTION_UNSUBSCRIBE,
        )
        ComunSubscriptionEvent.objects.filter(id=unsubscribe.id).update(
            created_at=self._at_date(today)
        )

        other_comun = Comun.objects.create(name="Other", slug="other")
        other_post = Post.objects.create(
            author=self.author,
            message_id=2,
            raw_data={"source": "manual_comun", "comun_slug": other_comun.slug},
        )
        PostDailyView.objects.create(post=other_post, date=today, views_count=100)

        response = self.client.get(self.url, **self.owner_headers)

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(payload["comun"]["subscribers_count"], 12)
        self.assertEqual(payload["periods"]["all_time"]["views"], 41)
        self.assertEqual(payload["periods"]["all_time"]["comments"], 3)
        self.assertEqual(payload["periods"]["day"]["views"], 5)
        self.assertEqual(payload["periods"]["week"]["views"], 12)
        self.assertEqual(payload["periods"]["month"]["views"], 23)
        self.assertEqual(payload["periods"]["day"]["comments"], 1)
        self.assertEqual(payload["periods"]["week"]["comments"], 2)
        self.assertEqual(payload["periods"]["month"]["comments"], 3)
        self.assertEqual(payload["periods"]["day"]["subscribers_net"], -1)
        self.assertEqual(payload["periods"]["week"]["subscribers_net"], 0)
        self.assertEqual(len(payload["series"]), 30)

    def test_post_view_updates_daily_aggregate(self):
        response = self.client.post(reverse("post-view", kwargs={"post_id": self.post.id}))

        self.assertEqual(response.status_code, 200, response.content.decode())
        metric = PostDailyView.objects.get(post=self.post, date=timezone.localdate())
        self.assertEqual(metric.views_count, 1)
