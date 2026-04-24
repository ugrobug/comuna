import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from feeds.models import Post


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


def editor_personal_author_id(user):
    from editor import service as editor_service

    author, error = editor_service._get_or_create_personal_author(user)
    if error:
        raise AssertionError(error)
    return author.id
