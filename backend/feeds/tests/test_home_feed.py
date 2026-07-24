import json

from django.test import TestCase
from django.urls import reverse

from communities.models import Comun
from feeds.models import Author, Post, PostTranslation, PublicFeedItem
from ratings.models import RatingSettings


class HomeFeedTests(TestCase):
    def test_original_english_post_is_only_in_english_feed_until_russian_translation_exists(self):
        author = Author.objects.create(username="english-source")
        post = Post.objects.create(
            author=author,
            message_id=1000,
            title="An original English article",
            content="<p>This post was written and published in English.</p>",
            original_language="en",
            rating=2,
            is_pending=False,
            is_blocked=False,
        )
        PublicFeedItem.objects.create(
            feed=PublicFeedItem.FEED_HOME,
            post=post,
            rank=1,
            score=2,
            post_created_at=post.created_at,
            author_id_snapshot=author.id,
        )

        english_response = self.client.get(
            reverse("home-feed"),
            {"card": "1", "limit": "10", "lang": "en"},
        )
        russian_response = self.client.get(
            reverse("home-feed"),
            {"card": "1", "limit": "10", "lang": "ru"},
        )

        self.assertEqual([item["id"] for item in english_response.json()["posts"]], [post.id])
        self.assertEqual(english_response.json()["posts"][0]["title"], post.title)
        self.assertEqual(russian_response.json()["posts"], [])

        PostTranslation.objects.create(
            post=post,
            language="ru",
            title="Перевод английской статьи",
            content="<p>Этот пост был переведен на русский язык.</p>",
            preview_content="<p>Этот пост был переведен на русский язык.</p>",
            status="translated",
        )
        russian_response = self.client.get(
            reverse("home-feed"),
            {"card": "1", "limit": "10", "lang": "ru"},
        )

        self.assertEqual([item["id"] for item in russian_response.json()["posts"]], [post.id])
        self.assertEqual(russian_response.json()["posts"][0]["title"], "Перевод английской статьи")
        self.assertTrue(russian_response.json()["posts"][0]["is_translated"])

    def test_english_feed_only_returns_translated_posts_with_localized_cards(self):
        author = Author.objects.create(username="localized-author")
        translated_post = Post.objects.create(
            author=author,
            message_id=1001,
            title="Русский заголовок",
            content="<p>Русский текст</p>",
            rating=2,
            is_pending=False,
            is_blocked=False,
        )
        untranslated_post = Post.objects.create(
            author=author,
            message_id=1002,
            title="Только русский",
            content="<p>Без перевода</p>",
            rating=2,
            is_pending=False,
            is_blocked=False,
        )
        PostTranslation.objects.create(
            post=translated_post,
            language="en",
            title="English title",
            content="<p>English text</p>",
            preview_content="<p>English preview</p>",
            status="translated",
        )
        for rank, post in enumerate((translated_post, untranslated_post), start=1):
            PublicFeedItem.objects.create(
                feed=PublicFeedItem.FEED_HOME,
                post=post,
                rank=rank,
                score=2,
                post_created_at=post.created_at,
                author_id_snapshot=author.id,
            )

        response = self.client.get(
            reverse("home-feed"),
            {"card": "1", "limit": "10", "lang": "en"},
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        posts = response.json()["posts"]
        self.assertEqual([post["id"] for post in posts], [translated_post.id])
        self.assertEqual(posts[0]["title"], "English title")
        self.assertEqual(posts[0]["content"], "<p>English preview</p>")
        self.assertEqual(posts[0]["language"], "en")

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
