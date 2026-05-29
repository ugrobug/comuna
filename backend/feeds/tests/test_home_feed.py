import json

from django.test import TestCase
from django.urls import reverse

from communities.models import Comun
from feeds.models import Author, Post, PublicFeedItem
from ratings.models import RatingSettings


class HomeFeedTests(TestCase):
    def test_materialized_home_feed_hides_current_negative_rating_posts(self):
        negative_author = Author.objects.create(username="negative-author")
        positive_author = Author.objects.create(username="positive-author")
        negative_post = Post.objects.create(
            author=negative_author,
            message_id=1,
            title="Negative",
            rating=-5,
            content="{}",
            is_pending=False,
            is_blocked=False,
        )
        positive_post = Post.objects.create(
            author=positive_author,
            message_id=2,
            title="Positive",
            rating=2,
            content="{}",
            is_pending=False,
            is_blocked=False,
        )
        PublicFeedItem.objects.create(
            feed=PublicFeedItem.FEED_HOME,
            post=negative_post,
            rank=1,
            score=10,
            post_created_at=negative_post.created_at,
            author_id_snapshot=negative_author.id,
        )
        PublicFeedItem.objects.create(
            feed=PublicFeedItem.FEED_HOME,
            post=positive_post,
            rank=2,
            score=2,
            post_created_at=positive_post.created_at,
            author_id_snapshot=positive_author.id,
        )

        response = self.client.get(reverse("home-feed"), {"card": "1", "limit": "10"})

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = json.loads(response.content)
        self.assertTrue(payload["materialized"])
        self.assertEqual([post["id"] for post in payload["posts"]], [positive_post.id])

    def test_materialized_home_feed_limits_posts_per_community_per_day(self):
        RatingSettings.objects.update_or_create(
            pk=1,
            defaults={"home_posts_per_community_per_day": 3},
        )
        author = Author.objects.create(username="community-author")
        comun = Comun.objects.create(name="Daily Limit", slug="daily-limit")
        posts = [
            Post.objects.create(
                author=author,
                message_id=index + 10,
                title=f"Post {index}",
                rating=2,
                content="{}",
                raw_data={"source": "manual_comun", "comun_slug": comun.slug},
                is_pending=False,
                is_blocked=False,
            )
            for index in range(4)
        ]
        for index, post in enumerate(posts, start=1):
            PublicFeedItem.objects.create(
                feed=PublicFeedItem.FEED_HOME,
                post=post,
                rank=index,
                score=2,
                post_created_at=post.created_at,
                author_id_snapshot=author.id,
            )

        response = self.client.get(reverse("home-feed"), {"card": "1", "limit": "10"})

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = json.loads(response.content)
        self.assertEqual(
            [post["id"] for post in payload["posts"]],
            [post.id for post in posts[:3]],
        )
