import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from communities import service as community_service
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from feeds.models import Author, Post
from users.models import AuthorAdmin


User = get_user_model()


class ComunPostingApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="comun-owner", password="secret")
        self.client.force_login(self.user)
        self.comun = Comun.objects.create(
            name="Unit Game",
            slug="unit-game",
            creator=self.user,
        )
        self.category = ComunCategory.objects.create(
            comun=self.comun,
            name="Рекорды",
            slug="rekordy",
        )
        self.comun.categories.add(self.category)

    def test_can_create_manual_post_in_comun_without_source(self):
        response = self.client.post(
            reverse("comun-posts", kwargs={"slug": self.comun.slug}),
            data=json.dumps(
                {
                    "title": "Новый рекорд",
                    "content": "{\"time\":1772104218738,\"blocks\":[{\"type\":\"paragraph\",\"data\":{\"text\":\"Пробил 1000 очков\"}}]}",
                    "author_source": "site",
                    "comun_category_id": self.category.id,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload.get("ok"))

        post = Post.objects.get(id=payload["post"]["id"])
        self.assertEqual(post.raw_data.get("source"), "manual_comun")
        self.assertEqual(post.raw_data.get("comun_slug"), self.comun.slug)

        assignment = ComunPostCategoryAssignment.objects.get(comun=self.comun, post=post)
        self.assertEqual(assignment.category_id, self.category.id)

    def test_manual_comun_post_ignores_requested_telegram_author(self):
        telegram_author = Author.objects.create(
            username="linked-channel",
            title="Linked Channel",
            channel_id=778,
            channel_url="https://t.me/linked-channel",
        )
        AuthorAdmin.objects.create(
            user=self.user,
            author=telegram_author,
            verified_at=timezone.now(),
        )

        response = self.client.post(
            reverse("comun-posts", kwargs={"slug": self.comun.slug}),
            data=json.dumps(
                {
                    "title": "Пост только от сайта",
                    "content": "{\"time\":1772104218738,\"blocks\":[{\"type\":\"paragraph\",\"data\":{\"text\":\"Проверяем автора\"}}]}",
                    "author_username": telegram_author.username,
                    "comun_category_id": self.category.id,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload.get("ok"))

        post = Post.objects.get(id=payload["post"]["id"])
        self.assertEqual(post.author.username, self.user.username)

    def test_manual_post_appears_in_comun_feed_without_source(self):
        post = Post.objects.create(
            author_id=editor_personal_author_id(self.user),
            message_id=123456789,
            title="Таблица рекордов",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        ComunPostCategoryAssignment.objects.create(
            comun=self.comun,
            post=post,
            category=self.category,
            assigned_by=self.user,
        )

        response = self.client.get(reverse("comun-posts", kwargs={"slug": self.comun.slug}))

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload.get("total_count"), 1)
        self.assertEqual(payload["posts"][0]["id"], post.id)

    def test_comun_access_uses_personal_site_author_rating(self):
        personal_author_id = editor_personal_author_id(self.user)
        personal_author = Author.objects.get(id=personal_author_id)
        personal_author.rating_total = 0
        personal_author.save(update_fields=["rating_total"])

        telegram_author = Author.objects.create(
            username="unit-channel",
            title="Unit Channel",
            channel_id=777,
            channel_url="https://t.me/unit-channel",
            rating_total=10_000,
        )
        AuthorAdmin.objects.create(
            user=self.user,
            author=telegram_author,
            verified_at=timezone.now(),
        )

        self.comun.minimum_author_rating_to_post = 50
        self.comun.save(update_fields=["minimum_author_rating_to_post"])

        can_post, minimum_rating, author_rating = community_service._comun_post_access_state(
            self.user,
            self.comun,
        )

        self.assertFalse(can_post)
        self.assertEqual(minimum_rating, 50)
        self.assertEqual(author_rating, 0)


def editor_personal_author_id(user):
    from editor import service as editor_service

    author, error = editor_service._get_or_create_personal_author(user)
    if error:
        raise AssertionError(error)
    return author.id
