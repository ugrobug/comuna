import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from communities import service as community_service
from communities.models import (
    Comun,
    ComunCategory,
    ComunPostCategoryAssignment,
    ComunPostRatingContribution,
)
from feeds.models import Author, Post, Tag
from my_feed.models import UserFeedSettings
from users import service as user_service
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
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.authors_count, 1)

    def test_comun_authors_count_increments_once_per_author(self):
        for index in range(2):
            response = self.client.post(
                reverse("auth-posts"),
                data=json.dumps(
                    {
                        "title": f"Пост автора {index}",
                        "content": "{\"time\":1772104218738,\"blocks\":[{\"type\":\"paragraph\",\"data\":{\"text\":\"Текст\"}}]}",
                        "author_source": "site",
                        "comun_slug": self.comun.slug,
                        "comun_category_id": self.category.id,
                    }
                ),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200, response.content.decode())

        self.comun.refresh_from_db()
        self.assertEqual(self.comun.authors_count, 1)

    def test_comun_authors_count_ignores_channel_posts(self):
        channel_author = Author.objects.create(
            username="channel-author",
            title="Channel Author",
            channel_id=12345,
            channel_url="https://t.me/channel-author",
        )
        post = Post.objects.create(
            author=channel_author,
            message_id=12345,
            title="Пост канала",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )

        incremented = community_service._maybe_increment_comun_author_count_for_post(
            post,
            comun=self.comun,
        )

        self.assertFalse(incremented)
        self.comun.refresh_from_db()
        self.assertEqual(self.comun.authors_count, 0)

    def test_foreign_welcome_post_is_not_serialized_or_accepted(self):
        foreign_author = Author.objects.create(
            username="foreign-channel",
            title="Foreign Channel",
            channel_id=67890,
            channel_url="https://t.me/foreign-channel",
        )
        foreign_post = Post.objects.create(
            author=foreign_author,
            message_id=67890,
            title="Чужой закреп",
            content="{}",
            is_pending=False,
            is_blocked=False,
        )
        self.comun.welcome_post = foreign_post
        self.comun.save(update_fields=["welcome_post"])

        response = self.client.get(reverse("comun-posts", kwargs={"slug": self.comun.slug}))
        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertIsNone(payload["comun"]["welcome_post_id"])
        self.assertIsNone(payload["comun"]["welcome_post"])

        update_response = self.client.patch(
            reverse("comun-detail-manage", kwargs={"slug": self.comun.slug}),
            data=json.dumps({"welcome_post_id": foreign_post.id}),
            content_type="application/json",
        )
        self.assertEqual(update_response.status_code, 400, update_response.content.decode())
        self.assertEqual(update_response.json()["error"], "post does not belong to comun")

    def test_comun_rating_post_delta_applies_only_in_first_rating_window(self):
        author = Author.objects.create(username="rating-author", title="Rating Author")
        post = Post.objects.create(
            author=author,
            message_id=991,
            title="Рейтинговый пост",
            content="{}",
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        self.comun.rating_score = 247
        self.comun.save(update_fields=["rating_score"])

        community_service._apply_comun_rating_delta_for_post(
            post,
            value_delta=7,
            event_type="post_vote",
        )
        self.comun.refresh_from_db()
        self.assertEqual(float(self.comun.rating_score), 254.0)
        contribution = ComunPostRatingContribution.objects.get(comun=self.comun, post=post)
        self.assertEqual(float(contribution.score), 7.0)

        Post.objects.filter(id=post.id).update(created_at=timezone.now() - timedelta(days=8))
        community_service._apply_comun_rating_delta_for_post(
            post.id,
            value_delta=-5,
            event_type="post_vote",
        )
        self.comun.refresh_from_db()
        self.assertEqual(float(self.comun.rating_score), 254.0)
        contribution.refresh_from_db()
        self.assertEqual(float(contribution.score), 7.0)

    def test_comun_rating_rebuild_uses_stored_post_contributions(self):
        author = Author.objects.create(username="rating-rebuild-author", title="Rating Rebuild Author")
        post = Post.objects.create(
            author=author,
            message_id=992,
            title="Пост для rebuild",
            content="{}",
            rating=7,
            comments_count=2,
            raw_data={"source": "manual_comun", "comun_slug": self.comun.slug},
            is_pending=False,
            is_blocked=False,
        )
        ComunPostRatingContribution.objects.create(
            comun=self.comun,
            post=post,
            score=7.2,
        )

        _votes_up, _votes_down, rating_score = community_service._recalculate_comun_rating(self.comun.id)

        self.assertEqual(float(rating_score), 7.2)
        self.comun.refresh_from_db()
        self.assertEqual(float(self.comun.rating_score), 7.2)

    def test_comuns_catalog_returns_paginated_lightweight_top(self):
        catalog_tag = Tag.objects.create(name="Catalog", lemma="catalog")
        self.comun.rating_score = 100
        self.comun.product_description = "Top catalog community"
        self.comun.save(update_fields=["rating_score", "product_description"])
        self.comun.tags.add(catalog_tag)
        for index in range(25):
            Comun.objects.create(
                name=f"Catalog Community {index}",
                slug=f"catalog-community-{index}",
                creator=self.user,
                rating_score=index,
            )

        response = self.client.get(reverse("comuns-catalog"), {"limit": "20"})

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["limit"], 20)
        self.assertEqual(payload["total_comuns"], 26)
        self.assertTrue(payload["has_next"])
        self.assertEqual(len(payload["comuns"]), 20)
        first_comun = payload["comuns"][0]
        self.assertEqual(first_comun["slug"], self.comun.slug)
        self.assertEqual(first_comun["rating"]["score"], 100.0)
        self.assertEqual(first_comun["tags"][0]["name"], catalog_tag.name)
        self.assertNotIn("template_type_options", first_comun)
        self.assertNotIn("template_editor_blocks_by_template", first_comun)
        self.assertNotIn("moderators", first_comun)
        self.assertNotIn("can_post", first_comun)

        second_page_response = self.client.get(reverse("comuns-catalog"), {"limit": "20", "page": "2"})
        self.assertEqual(second_page_response.status_code, 200, second_page_response.content.decode())
        second_page_payload = second_page_response.json()
        self.assertEqual(second_page_payload["page"], 2)
        self.assertFalse(second_page_payload["has_next"])
        self.assertEqual(len(second_page_payload["comuns"]), 6)

    def test_comuns_catalog_searches_on_backend(self):
        Comun.objects.create(
            name="Needle Community",
            slug="needle-community",
            creator=self.user,
            product_description="Private search marker",
            rating_score=10,
        )
        Comun.objects.create(
            name="Another Community",
            slug="another-community",
            creator=self.user,
            rating_score=20,
        )

        response = self.client.get(reverse("comuns-catalog"), {"q": "needle", "limit": "20"})

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        slugs = [item["slug"] for item in payload["comuns"]]
        self.assertEqual(slugs, ["needle-community"])
        self.assertEqual(payload["total_comuns"], 1)

    def test_comuns_sidebar_returns_catalog_card_fields(self):
        sidebar_tag = Tag.objects.create(name="Sidebar", lemma="sidebar")
        self.comun.product_description = "Sidebar community description"
        self.comun.subscribers_count = 12
        self.comun.authors_count = 3
        self.comun.rating_score = 42
        self.comun.save(
            update_fields=[
                "product_description",
                "subscribers_count",
                "authors_count",
                "rating_score",
            ]
        )
        self.comun.tags.add(sidebar_tag)

        response = self.client.get(reverse("comuns-sidebar"))

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        first_comun = payload["comuns"][0]
        self.assertEqual(first_comun["slug"], self.comun.slug)
        self.assertEqual(first_comun["product_description"], "Sidebar community description")
        self.assertEqual(first_comun["subscribers_count"], 12)
        self.assertEqual(first_comun["authors_count"], 3)
        self.assertEqual(first_comun["rating"]["score"], 42.0)
        self.assertEqual(first_comun["tags"][0]["name"], sidebar_tag.name)
        self.assertTrue(first_comun["can_moderate"])

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
        self.assertTrue(comun.only_moderators_can_post)

    def test_create_from_telegram_channel_defaults_to_moderator_only(self):
        telegram_author = Author.objects.create(
            username="managed-channel",
            title="Managed Channel",
            channel_id=780,
            channel_url="https://t.me/managed-channel",
        )
        AuthorAdmin.objects.create(
            user=self.user,
            author=telegram_author,
            verified_at=timezone.now(),
        )

        response = self.client.post(
            reverse("comun-create-from-telegram-channel"),
            data=json.dumps({"author_id": telegram_author.id}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("created"))
        self.assertTrue(payload["comun"]["only_moderators_can_post"])

        comun = Comun.objects.get(telegram_source_author=telegram_author)
        self.assertTrue(comun.only_moderators_can_post)
        self.assertTrue(comun.moderators.filter(id=self.user.id).exists())

    def test_interface_created_comun_remains_open_by_default(self):
        response = self.client.post(
            reverse("comuns-list-create"),
            data=json.dumps({"name": "Open Product Community"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        self.assertTrue(payload.get("ok"))
        self.assertFalse(payload["comun"]["only_moderators_can_post"])

        comun = Comun.objects.get(slug=payload["comun"]["slug"])
        self.assertFalse(comun.only_moderators_can_post)

    def test_site_admin_is_not_implicit_moderator_for_restricted_comun(self):
        site_admin = User.objects.create_user(username="site-admin", password="secret", is_staff=True)
        telegram_author = Author.objects.create(
            username="restricted-channel",
            title="Restricted Channel",
            channel_id=781,
            channel_url="https://t.me/restricted-channel",
        )
        comun = Comun.objects.create(
            name="Restricted Channel",
            slug="restricted-channel",
            creator=self.user,
            telegram_source_author=telegram_author,
            telegram_channel_username=telegram_author.username,
            only_moderators_can_post=True,
        )

        can_post, _minimum_rating, _author_rating = community_service._comun_post_access_state(
            site_admin,
            comun,
        )

        self.assertFalse(can_post)

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

    def test_comuns_list_marks_subscribed_and_writable_targets_for_composer(self):
        viewer = User.objects.create_user(username="subscriber", password="secret")
        self.client.force_login(viewer)

        subscribed_comun = Comun.objects.create(
            name="Subscribed Open",
            slug="subscribed-open",
            creator=self.user,
        )
        subscribed_category = ComunCategory.objects.create(
            comun=subscribed_comun,
            name="Отзывы",
            slug="otzyvy",
        )
        subscribed_comun.categories.add(subscribed_category)

        unsubscribed_comun = Comun.objects.create(
            name="Unsubscribed Open",
            slug="unsubscribed-open",
            creator=self.user,
        )
        unsubscribed_category = ComunCategory.objects.create(
            comun=unsubscribed_comun,
            name="Новости",
            slug="novosti",
        )
        unsubscribed_comun.categories.add(unsubscribed_category)

        restricted_comun = Comun.objects.create(
            name="Subscribed Restricted",
            slug="subscribed-restricted",
            creator=self.user,
            only_moderators_can_post=True,
        )
        restricted_category = ComunCategory.objects.create(
            comun=restricted_comun,
            name="Модераторская",
            slug="moderatorskaya",
            only_moderators_can_post=True,
        )
        restricted_comun.categories.add(restricted_category)

        moderated_comun = Comun.objects.create(
            name="Moderated Restricted",
            slug="moderated-restricted",
            creator=self.user,
            only_moderators_can_post=True,
        )
        moderated_comun.moderators.add(viewer)

        UserFeedSettings.objects.create(
            user=viewer,
            my_feed_comuns=[subscribed_comun.slug, restricted_comun.slug],
        )

        response = self.client.get(
            reverse("comuns-list-create"),
            HTTP_AUTHORIZATION=f"Bearer {user_service._issue_token(viewer)}",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        comuns_by_slug = {comun["slug"]: comun for comun in payload["comuns"]}

        subscribed_payload = comuns_by_slug[subscribed_comun.slug]
        self.assertTrue(subscribed_payload["is_subscribed"])
        self.assertTrue(subscribed_payload["can_start_post"])
        self.assertIn(subscribed_category.id, subscribed_payload["can_post_category_ids"])
        self.assertTrue(subscribed_payload["categories"][0]["can_post"])

        unsubscribed_payload = comuns_by_slug[unsubscribed_comun.slug]
        self.assertFalse(unsubscribed_payload["is_subscribed"])
        self.assertTrue(unsubscribed_payload["can_start_post"])

        restricted_payload = comuns_by_slug[restricted_comun.slug]
        self.assertTrue(restricted_payload["is_subscribed"])
        self.assertFalse(restricted_payload["can_start_post"])
        self.assertFalse(restricted_payload["can_post_without_category"])
        self.assertFalse(restricted_payload["categories"][0]["can_post"])

        moderated_payload = comuns_by_slug[moderated_comun.slug]
        self.assertFalse(moderated_payload["is_subscribed"])
        self.assertTrue(moderated_payload["can_moderate"])
        self.assertTrue(moderated_payload["can_start_post"])

    def test_comuns_composer_returns_only_available_targets(self):
        viewer = User.objects.create_user(username="composer-subscriber", password="secret")

        subscribed_comun = Comun.objects.create(
            name="Composer Subscribed",
            slug="composer-subscribed",
            creator=self.user,
            product_description="Можно писать",
            rules_text="Без спама",
        )
        subscribed_category = ComunCategory.objects.create(
            comun=subscribed_comun,
            name="Отзывы",
            slug="otzyvy",
        )
        subscribed_comun.categories.add(subscribed_category)

        unsubscribed_comun = Comun.objects.create(
            name="Composer Unsubscribed",
            slug="composer-unsubscribed",
            creator=self.user,
        )

        restricted_comun = Comun.objects.create(
            name="Composer Restricted",
            slug="composer-restricted",
            creator=self.user,
            only_moderators_can_post=True,
        )
        restricted_category = ComunCategory.objects.create(
            comun=restricted_comun,
            name="Модераторская",
            slug="moderatorskaya",
            only_moderators_can_post=True,
        )
        restricted_comun.categories.add(restricted_category)

        moderated_comun = Comun.objects.create(
            name="Composer Moderated",
            slug="composer-moderated",
            creator=self.user,
            only_moderators_can_post=True,
        )
        moderated_comun.moderators.add(viewer)

        UserFeedSettings.objects.create(
            user=viewer,
            my_feed_comuns=[subscribed_comun.slug, restricted_comun.slug],
        )

        response = self.client.get(
            reverse("comuns-composer"),
            HTTP_AUTHORIZATION=f"Bearer {user_service._issue_token(viewer)}",
        )

        self.assertEqual(response.status_code, 200, response.content.decode())
        payload = response.json()
        comuns_by_slug = {comun["slug"]: comun for comun in payload["comuns"]}

        self.assertIn(subscribed_comun.slug, comuns_by_slug)
        self.assertNotIn(unsubscribed_comun.slug, comuns_by_slug)
        self.assertNotIn(restricted_comun.slug, comuns_by_slug)
        self.assertIn(moderated_comun.slug, comuns_by_slug)
        self.assertIn("template_type_options", payload)
        self.assertIn("template_editor_blocks_by_template", payload)

        subscribed_payload = comuns_by_slug[subscribed_comun.slug]
        self.assertTrue(subscribed_payload["is_subscribed"])
        self.assertTrue(subscribed_payload["can_start_post"])
        self.assertEqual(subscribed_payload["rules_text"], "Без спама")
        self.assertIn(subscribed_category.id, subscribed_payload["can_post_category_ids"])
        self.assertTrue(subscribed_payload["categories"][0]["can_post"])
        self.assertNotIn("moderators", subscribed_payload)
        self.assertNotIn("rating", subscribed_payload)

        moderated_payload = comuns_by_slug[moderated_comun.slug]
        self.assertFalse(moderated_payload["is_subscribed"])
        self.assertTrue(moderated_payload["can_moderate"])
        self.assertTrue(moderated_payload["can_start_post"])


def editor_personal_author_id(user):
    from editor import service as editor_service

    author, error = editor_service._get_or_create_personal_author(user)
    if error:
        raise AssertionError(error)
    return author.id
