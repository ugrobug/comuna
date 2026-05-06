import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse

from my_feed.views import (
    auth_feed_settings,
    my_feed,
    thematic_feed_manage_detail,
    thematic_feed_posts,
    thematic_feeds_list,
    thematic_feeds_manage,
)
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from feeds.models import Author, Post
from my_feed.models import UserFeedSettings
from users.service import _issue_token

User = get_user_model()


class MyFeedViewsApiTests(SimpleTestCase):
    def test_my_feed_urls_resolve_to_my_feed_app_views(self):
        self.assertIs(resolve("/api/home/my/").func, my_feed)
        self.assertIs(resolve("/api/auth/feed-settings/").func, auth_feed_settings)
        self.assertIs(resolve("/api/thematic-feeds/").func, thematic_feeds_list)
        self.assertIs(resolve("/api/thematic-feeds/manage/").func, thematic_feeds_manage)
        self.assertIs(
            resolve("/api/thematic-feeds/manage/demo/").func,
            thematic_feed_manage_detail,
        )
        self.assertIs(
            resolve("/api/thematic-feeds/demo/posts/").func,
            thematic_feed_posts,
        )


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


class UserFeedSettingsApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="feed-user", password="secret")
        self.comun = Comun.objects.create(name="Subscribed Comun", slug="subscribed", creator=self.user)
        self.other_comun = Comun.objects.create(name="Other Comun", slug="other", creator=self.user)
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

    def test_my_feed_uses_saved_comun_subscriptions_without_query_filters(self):
        UserFeedSettings.objects.create(
            user=self.user,
            home_feed="mine",
            my_feed_authors=["chosen-author"],
            my_feed_comuns=[self.comun.slug],
        )
        response = self.client.get(reverse("my-feed"), {"limit": "10"}, **self.auth_headers)

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual([post["id"] for post in response.json()["posts"]], [self.comun_post.id])

    def test_my_feed_ignores_saved_author_selection_without_comun_subscription(self):
        UserFeedSettings.objects.create(
            user=self.user,
            home_feed="mine",
            my_feed_authors=["chosen-author"],
        )
        response = self.client.get(reverse("my-feed"), {"limit": "10"}, **self.auth_headers)

        self.assertEqual(response.status_code, 200, response.content.decode())
        self.assertEqual(response.json()["posts"], [])
