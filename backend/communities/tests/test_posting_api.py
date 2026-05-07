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

    def test_auth_posts_require_comun_for_published_post(self):
        response = self.client.post(
            reverse("auth-posts"),
            data=json.dumps(
                {
                    "title": "Без сообщества",
                    "content": "{\"time\":1772104218738,\"blocks\":[{\"type\":\"paragraph\",\"data\":{\"text\":\"Текст\"}}]}",
                    "author_source": "site",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400, response.content.decode())
        self.assertEqual(response.json().get("error"), "community required")

    def test_auth_posts_can_publish_to_comun_category(self):
        response = self.client.post(
            reverse("auth-posts"),
            data=json.dumps(
                {
                    "title": "Новый рекорд",
                    "content": "{\"time\":1772104218738,\"blocks\":[{\"type\":\"paragraph\",\"data\":{\"text\":\"Пробил 2000 очков\"}}]}",
                    "author_source": "site",
                    "comun_slug": self.comun.slug,
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
        self.assertEqual(payload["post"].get("comun_slug"), self.comun.slug)
        self.assertEqual(payload["post"].get("comun_category_id"), self.category.id)

        assignment = ComunPostCategoryAssignment.objects.get(comun=self.comun, post=post)
        self.assertEqual(assignment.category_id, self.category.id)

    def test_auth_draft_can_be_published_to_comun_category(self):
        draft_response = self.client.post(
            reverse("auth-posts"),
            data=json.dumps(
                {
                    "title": "Черновик",
                    "content": "{\"time\":1772104218738,\"blocks\":[{\"type\":\"paragraph\",\"data\":{\"text\":\"Сначала черновик\"}}]}",
                    "author_source": "site",
                    "is_draft": True,
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(draft_response.status_code, 200, draft_response.content.decode())
        draft_id = draft_response.json()["post"]["id"]

        publish_response = self.client.patch(
            reverse("auth-post-update", kwargs={"post_id": draft_id}),
            data=json.dumps(
                {
                    "title": "Опубликованный черновик",
                    "content": "{\"time\":1772104218738,\"blocks\":[{\"type\":\"paragraph\",\"data\":{\"text\":\"Теперь опубликован\"}}]}",
                    "author_source": "site",
                    "comun_slug": self.comun.slug,
                    "comun_category_id": self.category.id,
                    "is_draft": False,
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(publish_response.status_code, 200, publish_response.content.decode())
        payload = publish_response.json()
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload["post"].get("comun_slug"), self.comun.slug)
        self.assertEqual(payload["post"].get("comun_category_id"), self.category.id)

        post = Post.objects.get(id=draft_id)
        self.assertFalse(post.is_pending)
        self.assertEqual(post.raw_data.get("source"), "manual_comun")
        self.assertEqual(post.raw_data.get("comun_slug"), self.comun.slug)

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

    def test_verified_channel_owner_claims_unowned_linked_comun(self):
        telegram_author = Author.objects.create(
            username="unit-channel",
            title="Unit Channel",
            channel_id=777,
            channel_url="https://t.me/unit-channel",
            avatar_image="authors/avatars/unit-channel.jpg",
        )
        comun = Comun.objects.create(
            name="Unit Channel",
            slug="unit-channel-comun",
            creator=None,
            telegram_source_author=telegram_author,
            telegram_channel_username="unit-channel",
        )
        AuthorAdmin.objects.create(
            user=self.user,
            author=telegram_author,
            verified_at=timezone.now(),
        )

        community_service._attach_pending_comuns_for_author(telegram_author)

        comun.refresh_from_db()
        self.assertEqual(comun.creator_id, self.user.id)
        self.assertEqual(comun.logo_url, "/media/authors/avatars/unit-channel.jpg")
        self.assertTrue(comun.moderators.filter(id=self.user.id).exists())

    def test_verified_channel_owner_claims_pending_channel_comun(self):
        telegram_author = Author.objects.create(
            username="pending-channel",
            title="Pending Channel",
            channel_id=778,
            channel_url="https://t.me/pending-channel",
            avatar_url="https://example.com/pending-channel.jpg",
        )
        comun = Comun.objects.create(
            name="Pending Channel",
            slug="pending-channel-comun",
            creator=None,
            telegram_channel_username="pending-channel",
        )
        AuthorAdmin.objects.create(
            user=self.user,
            author=telegram_author,
            verified_at=timezone.now(),
        )

        community_service._attach_pending_comuns_for_author(telegram_author)

        comun.refresh_from_db()
        self.assertEqual(comun.creator_id, self.user.id)
        self.assertEqual(comun.telegram_source_author_id, telegram_author.id)
        self.assertEqual(comun.logo_url, "https://example.com/pending-channel.jpg")
        self.assertTrue(comun.moderators.filter(id=self.user.id).exists())

    def test_telegram_author_without_owner_gets_unowned_comun(self):
        telegram_author = Author.objects.create(
            username="orphan-channel",
            title="Orphan Channel",
            channel_id=779,
            channel_url="https://t.me/orphan-channel",
            avatar_url="https://example.com/orphan-channel.jpg",
        )

        comun = community_service._ensure_telegram_channel_comun_for_author(telegram_author)

        self.assertIsNotNone(comun)
        self.assertIsNone(comun.creator_id)
        self.assertEqual(comun.logo_url, "https://example.com/orphan-channel.jpg")
        self.assertEqual(comun.telegram_source_author_id, telegram_author.id)

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
