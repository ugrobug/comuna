import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse
from django.utils import timezone

from my_feed.views import (
    auth_feed_settings,
    my_feed,
)
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from feeds.models import Author, Post, PostRead
from my_feed.models import FeedSourcePost, UserFeedSettings
from users.service import _issue_token

User = get_user_model()


class MyFeedViewsApiTests(SimpleTestCase):
    def test_my_feed_urls_resolve_to_my_feed_app_views(self):
        self.assertIs(resolve("/api/home/my/").func, my_feed)
        self.assertIs(resolve("/api/auth/feed-settings/").func, auth_feed_settings)


class MyFeedComunCategoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="secret")
        self.comun = Comun.objects.create(name="Unit Game", slug="unit-game", creator=self.user)
        self.records = ComunCategory.objects.create(
            comun=self.comun,
            name="Рекорды",
            slug="rekordy",
        )
        self.news = ComunCategory.objects.create(
            comun=self.comun,
            name="Новости",
            slug="novosti",
        )
        self.comun.categories.add(self.records, self.news)
        self.author = Author.objects.create(username="site-author", title="Site Author")
        self.record_post = Post.objects.create(
            author=self.author,
            message_id=101,
            title="Новый рекорд",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        self.news_post = Post.objects.create(
            author=self.author,
            message_id=102,
            title="Новость",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        ComunPostCategoryAssignment.objects.create(
            comun=self.comun,
            post=self.record_post,
            category=self.records,
            assigned_by=self.user,
        )
        ComunPostCategoryAssignment.objects.create(
            comun=self.comun,
            post=self.news_post,
            category=self.news,
            assigned_by=self.user,
        )

    def test_my_feed_comun_selection_includes_manual_comun_posts(self):
        response = self.client.get(
            reverse("my-feed"),
            {"comuns": self.comun.slug, "limit": "10"},
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        post_ids = {post["id"] for post in response.json()["posts"]}
        self.assertEqual(post_ids, {self.record_post.id, self.news_post.id})

    def test_feed_source_index_tracks_comun_and_category_membership(self):
        self.assertTrue(
            FeedSourcePost.objects.filter(
                source_type=FeedSourcePost.SOURCE_COMUN,
                source_id=self.comun.id,
                post=self.record_post,
            ).exists()
        )
        self.assertTrue(
            FeedSourcePost.objects.filter(
                source_type=FeedSourcePost.SOURCE_COMUN_CATEGORY,
                source_id=self.records.id,
                post=self.record_post,
            ).exists()
        )

    def test_my_feed_comun_category_selection_filters_selected_categories(self):
        response = self.client.get(
            reverse("my-feed"),
            {
                "comuns": self.comun.slug,
                "comun_categories": json.dumps({self.comun.slug: [self.records.slug]}),
                "limit": "10",
            },
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        posts = response.json()["posts"]
        self.assertEqual([post["id"] for post in posts], [self.record_post.id])

    def test_my_feed_all_category_selection_behaves_like_full_comun_subscription(self):
        telegram_author = Author.objects.create(
            username="unit-game-channel",
            title="Unit Game Channel",
            channel_id=987654,
        )
        self.comun.telegram_source_author = telegram_author
        self.comun.save(update_fields=["telegram_source_author"])
        uncategorized_post = Post.objects.create(
            author=self.author,
            message_id=103,
            title="Общее обновление",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        telegram_post = Post.objects.create(
            author=telegram_author,
            message_id=104,
            title="Пост из канала",
            content="{}",
            is_pending=False,
            is_blocked=False,
        )

        response = self.client.get(
            reverse("my-feed"),
            {
                "comuns": self.comun.slug,
                "comun_categories": json.dumps(
                    {self.comun.slug: [self.records.slug, self.news.slug]}
                ),
                "limit": "10",
            },
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        post_ids = {post["id"] for post in response.json()["posts"]}
        self.assertEqual(
            post_ids,
            {self.record_post.id, self.news_post.id, uncategorized_post.id, telegram_post.id},
        )


class UserFeedSettingsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="feed-user", password="secret")
        self.comun = Comun.objects.create(
            name="Subscribed Comun",
            slug="subscribed",
            creator=self.user,
        )
        self.other_comun = Comun.objects.create(
            name="Other Comun",
            slug="other",
            creator=self.user,
        )
        self.author = Author.objects.create(username="chosen-author", title="Chosen Author")
        self.post = Post.objects.create(
            author=self.author,
            message_id=301,
            title="Chosen post",
            content="{}",
            is_pending=False,
            is_blocked=False,
        )
        self.comun_post = Post.objects.create(
            author=self.author,
            message_id=302,
            title="Subscribed comun post",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        self.other_comun_post = Post.objects.create(
            author=self.author,
            message_id=303,
            title="Other comun post",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": self.other_comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        self.auth_headers = {"HTTP_AUTHORIZATION": f"Bearer {_issue_token(self.user)}"}

    def test_auth_feed_settings_roundtrip(self):
        response = self.client.patch(
            reverse("auth-feed-settings"),
            data=json.dumps(
                {
                    "home_feed": "mine",
                    "my_feed_authors": ["chosen-author", "chosen-author"],
                    "my_feed_hide_negative": False,
                    "tag_rules": {"noise": "hide", "nsfw": "blur", "bad": "drop"},
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(payload["settings"]["home_feed"], "mine")
        self.assertEqual(payload["settings"]["my_feed_authors"], ["chosen-author"])
        self.assertFalse(payload["settings"]["my_feed_hide_negative"])
        self.assertEqual(payload["settings"]["tag_rules"], {"noise": "hide", "nsfw": "blur"})

        response = self.client.get(reverse("auth-feed-settings"), **self.auth_headers)
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertTrue(response.json()["has_customizations"])

    def test_auth_feed_settings_updates_cached_comun_subscribers_count(self):
        response = self.client.patch(
            reverse("auth-feed-settings"),
            data=json.dumps(
                {
                    "my_feed_comuns": [self.comun.slug],
                    "my_feed_comun_categories": {self.comun.slug: ["general"]},
                }
            ),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.subscribers_count, 1)

        response = self.client.patch(
            reverse("auth-feed-settings"),
            data=json.dumps({"my_feed_comuns": [], "my_feed_comun_categories": {}}),
            content_type="application/json",
            **self.auth_headers,
        )
        self.assertEqual(response.status_code, 200, response.content.decode())
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.subscribers_count, 0)

    def test_my_feed_uses_saved_comun_subscriptions_without_query_filters(self):
        UserFeedSettings.objects.create(
            user=self.user,
            home_feed="mine",
            my_feed_comuns=[self.comun.slug],
        )
        response = self.client.get(reverse("my-feed"), {"limit": "10"}, **self.auth_headers)

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual([post["id"] for post in response.json()["posts"]], [self.comun_post.id])

    def test_my_feed_uses_saved_hide_read_setting_without_query_flag(self):
        UserFeedSettings.objects.create(
            user=self.user,
            home_feed="mine",
            hide_read_posts=True,
            my_feed_comuns=[self.comun.slug],
        )
        PostRead.objects.create(user=self.user, post=self.comun_post)

        response = self.client.get(reverse("my-feed"), {"limit": "10"}, **self.auth_headers)

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertEqual(payload["posts"], [])
        self.assertNotIn("hidden_read_count", payload)

    def test_my_feed_hide_read_only_checks_recent_reads(self):
        UserFeedSettings.objects.create(
            user=self.user,
            home_feed="mine",
            hide_read_posts=True,
            my_feed_comuns=[self.comun.slug],
        )
        read = PostRead.objects.create(user=self.user, post=self.comun_post)
        PostRead.objects.filter(id=read.id).update(read_at=timezone.now() - timedelta(days=21))

        response = self.client.get(reverse("my-feed"), {"limit": "10"}, **self.auth_headers)

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual([post["id"] for post in response.json()["posts"]], [self.comun_post.id])

    def test_my_feed_ignores_query_comun_override_for_authenticated_user(self):
        UserFeedSettings.objects.create(
            user=self.user,
            home_feed="mine",
            my_feed_comuns=[self.comun.slug],
        )
        response = self.client.get(
            reverse("my-feed"),
            {"comuns": self.other_comun.slug, "limit": "10"},
            **self.auth_headers,
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual([post["id"] for post in response.json()["posts"]], [self.comun_post.id])

    def test_my_feed_includes_saved_author_subscription(self):
        UserFeedSettings.objects.create(
            user=self.user,
            home_feed="mine",
            my_feed_authors=["chosen-author"],
        )
        response = self.client.get(reverse("my-feed"), {"limit": "10"}, **self.auth_headers)

        self.assertEqual(response.status_code, 200, response.content.decode())
        post_ids = {post["id"] for post in response.json()["posts"]}
        self.assertEqual(post_ids, {self.post.id, self.comun_post.id, self.other_comun_post.id})

    def test_my_feed_subscribed_comun_does_not_include_other_channel_posts(self):
        source_comun = Comun.objects.create(
            name="Subscribed Tech",
            slug="subscribed-tech",
            creator=self.user,
        )
        plain_author = Author.objects.create(username="plain-tech", title="Plain Tech")
        telegram_author = Author.objects.create(
            username="anrera_tech",
            title="Anrera Tech",
            channel_id=123456,
        )
        Comun.objects.create(
            name="Anrera Tech",
            slug="anrera_tech",
            creator=self.user,
            telegram_source_author=telegram_author,
        )
        source_comun_post = Post.objects.create(
            author=plain_author,
            message_id=401,
            title="Source comun post",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": source_comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        ComunPostCategoryAssignment.objects.create(
            comun=source_comun,
            post=source_comun_post,
            assigned_by=self.user,
        )
        other_comun_post = Post.objects.create(
            author=telegram_author,
            message_id=402,
            title="Other telegram comun post",
            content="{}",
            is_pending=False,
            is_blocked=False,
        )
        UserFeedSettings.objects.create(
            user=self.user,
            home_feed="mine",
            my_feed_comuns=[source_comun.slug],
        )

        response = self.client.get(reverse("my-feed"), {"limit": "10"}, **self.auth_headers)

        self.assertEqual(response.status_code, 200, response.content.decode())
        post_ids = {post["id"] for post in response.json()["posts"]}
        self.assertIn(source_comun_post.id, post_ids)
        self.assertNotIn(other_comun_post.id, post_ids)
