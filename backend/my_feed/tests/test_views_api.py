import json

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse

from my_feed.views import (
    my_feed,
    thematic_feed_manage_detail,
    thematic_feed_posts,
    thematic_feeds_list,
    thematic_feeds_manage,
)
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from feeds.models import Author, Post

User = get_user_model()


class MyFeedViewsApiTests(SimpleTestCase):
    def test_my_feed_urls_resolve_to_my_feed_app_views(self):
        self.assertIs(resolve("/api/home/my/").func, my_feed)
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
