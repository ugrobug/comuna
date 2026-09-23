from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from communities import service
from communities.feed_reader import CommunityFeedReader
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from editor.models import PostTemplateConfig
from feeds.models import Author, Post, PostTranslation, PostComment, PostCommentLike, Tag
from feeds.views import _filter_posts_for_language
from ratings.models import RatingSettings
from ratings.service import calculate_post_total_rating
from users.models import AuthorAdmin
from users.service import _issue_token

User = get_user_model()


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class CommunityFeedPerformanceTests(TestCase):
    def setUp(self):
        PostTemplateConfig.objects.update_or_create(template_type="basic", defaults={"is_active": True})
        self.owner = User.objects.create_user(username="feed-owner")
        self.author = Author.objects.create(username="feed-owner")
        self.comun = Comun.objects.create(name="Feed", slug="fast-feed", creator=self.owner, allowed_post_templates=["basic"])
        self.category = ComunCategory.objects.create(comun=self.comun, name="News", slug="news")
        self.comun.categories.add(self.category)
        RatingSettings.objects.get_or_create(pk=1)
        self.url = reverse("comun-posts", kwargs={"slug": self.comun.slug})
        self.sequence = 0

    def post(self, **kwargs):
        self.sequence += 1
        values = dict(author=self.author, message_id=self.sequence, title=f"Post {self.sequence}",
                      content="<p>Example</p>", original_language="ru",
                      raw_data={"source": "manual_comun", "comun_slug": self.comun.slug})
        values.update(kwargs)
        return Post.objects.create(**values)

    def get(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_translations_do_not_duplicate_posts_and_match_old_membership(self):
        original = self.post()
        translated = self.post(original_language="en")
        pending = self.post(original_language="en")
        for language in ("en", "de", "fr"):
            PostTranslation.objects.create(post=original, language=language, status="translated")
        PostTranslation.objects.create(post=translated, language="ru", status="translated", title="Перевод")
        PostTranslation.objects.create(post=pending, language="ru", status="pending")
        base = service._comun_posts_base_queryset(self.comun)
        reader = CommunityFeedReader(base, community=self.comun, language="ru")
        self.assertSetEqual(set(reader.queryset.values_list("pk", flat=True)),
                            set(_filter_posts_for_language(base, "ru").values_list("pk", flat=True)))
        payload = self.get()
        self.assertEqual(payload["total_count"], 2)
        self.assertEqual([p["id"] for p in payload["posts"]], [translated.pk, original.pk])
        self.assertEqual(payload["posts"][0]["title"], "Перевод")
        self.assertTrue(payload["posts"][0]["is_translated"])

    def test_page_boundaries_with_equal_dates_are_stable(self):
        posts = [self.post() for _ in range(5)]
        Post.objects.filter(pk__in=[p.pk for p in posts]).update(created_at=timezone.now())
        first = self.get(limit=2, include_counts=0)
        second = self.get(limit=2, offset=2, include_counts=0)
        last = self.get(limit=2, offset=4, include_counts=0)
        self.assertEqual([p["id"] for page in (first, second, last) for p in page["posts"]],
                         [p.pk for p in reversed(posts)])
        self.assertTrue(first["has_more"])
        self.assertTrue(second["has_more"])
        self.assertFalse(last["has_more"])
        self.assertNotIn("total_count", first)

    def test_compact_page_does_not_calculate_counts_or_return_editor_configuration(self):
        self.post()
        with patch.object(CommunityFeedReader, "counts", side_effect=AssertionError("counts in page path")):
            payload = self.get(include_counts=0, include_comun=0, include_editor=0)
        self.assertNotIn("comun", payload)
        self.assertNotIn("category_counts", payload)
        self.assertNotIn("enabled_template_editor_blocks", payload["posts"][0])

    def test_counts_only_does_not_serialize_posts_and_matches_full_response(self):
        first, second, third = self.post(), self.post(), self.post()
        ComunPostCategoryAssignment.objects.create(comun=self.comun, post=first, category=self.category)
        ComunPostCategoryAssignment.objects.create(comun=self.comun, post=second, category=self.category)
        full = self.get(category=self.category.slug)
        with patch.object(CommunityFeedReader, "page", side_effect=AssertionError("page in counts path")):
            response = self.client.get(self.url, {"counts_only": 1, "category": self.category.slug})
        counts = response.json()
        for key in ("total_count", "category_counts", "uncategorized_count"):
            self.assertEqual(counts[key], full[key])
        self.assertEqual(counts["total_count"], 2)
        self.assertEqual(counts["uncategorized_count"], 1)
        self.assertNotIn("posts", counts)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        empty = self.get(categories="")
        self.assertEqual(empty["total_count"], 0)
        self.assertEqual(empty["posts"], [])

    def test_multiple_categories_and_unknown_category(self):
        other = ComunCategory.objects.create(comun=self.comun, name="Other", slug="other")
        self.comun.categories.add(other)
        for category in (self.category, other):
            ComunPostCategoryAssignment.objects.create(comun=self.comun, post=self.post(), category=category)
        self.post()
        result = self.get(categories="news,other,news")
        self.assertEqual(result["total_count"], 2)
        self.assertEqual(len(result["posts"]), 2)
        self.assertEqual(self.client.get(self.url, {"category": "missing"}).status_code, 404)

    def test_visibility_and_sources_are_preserved(self):
        visible = self.post()
        max_author = Author.objects.create(username="max-source", channel_url="https://max.ru/example")
        max_post = self.post(author=max_author, raw_data={"source": "max", "comun_slug": self.comun.slug})
        telegram = Author.objects.create(username="telegram-source", channel_id=1234)
        self.comun.telegram_source_author = telegram
        self.comun.save(update_fields=["telegram_source_author"])
        telegram_post = self.post(author=telegram, raw_data={})
        self.post(is_blocked=True)
        self.post(is_pending=True)
        self.post(publish_at=timezone.now() + timedelta(days=1))
        self.post(companion_matched_at=timezone.now())
        blocked_author = Author.objects.create(username="blocked", is_blocked=True)
        self.post(author=blocked_author)
        excluded = Author.objects.create(username="excluded")
        self.comun.excluded_authors.add(excluded)
        self.post(author=excluded)
        blocked_tag = Tag.objects.create(name="blocked-tag", lemma="blocked-tag")
        self.comun.blocked_tags.add(blocked_tag)
        tagged = self.post()
        tagged.tags.add(blocked_tag)
        self.post(raw_data={"source": "manual_comun", "comun_slug": "foreign"})
        pinned = self.post()
        self.comun.welcome_post = pinned
        self.comun.save(update_fields=["welcome_post"])
        result = self.get(include_comun=0)
        self.assertSetEqual({p["id"] for p in result["posts"]}, {visible.pk, max_post.pk, telegram_post.pk})
        self.assertEqual(result["total_count"], 3)

    def test_batch_rating_matches_original_calculation(self):
        post = self.post(rating=3, comments_count=2)
        comment = PostComment.objects.create(post=post, user=self.owner, body="Comment")
        PostCommentLike.objects.create(comment=comment, user=self.owner)
        self.comun.rating_score = 12
        self.comun.save(update_fields=["rating_score"])
        expected = float(calculate_post_total_rating(post, author_rating=0))
        self.assertEqual(self.get()["posts"][0]["score"], expected)

    def test_card_community_precedence_is_preserved(self):
        other = Comun.objects.create(name="Original", slug="original", creator=self.owner)
        telegram = Author.objects.create(username="source", channel_id=333)
        self.comun.telegram_source_author = telegram
        self.comun.save(update_fields=["telegram_source_author"])
        post = self.post(author=telegram, raw_data={"comun_slug": other.slug})
        result = self.get(include_comun=0)
        self.assertEqual(result["posts"][0]["comun"]["id"], other.pk)
        Post.objects.filter(pk=post.pk).update(raw_data={})
        ComunPostCategoryAssignment.objects.create(comun=other, post=post)
        self.assertEqual(self.get(include_comun=0)["posts"][0]["comun"]["id"], other.pk)
        ComunPostCategoryAssignment.objects.filter(post=post).delete()
        self.assertEqual(self.get(include_comun=0)["posts"][0]["comun"]["id"], self.comun.pk)

    def test_ten_distinct_authors_have_bounded_query_count(self):
        for index in range(10):
            author = Author.objects.create(username=f"personal-{index}")
            user = User.objects.create_user(username=f"personal-{index}")
            if index % 2:
                AuthorAdmin.objects.create(author=author, user=user, verified_at=timezone.now())
            self.post(author=author)
        # Warm Python imports, not responses (DummyCache).
        self.get(include_counts=0, include_comun=0, include_editor=0)
        with CaptureQueriesContext(connection) as queries:
            payload = self.get(include_counts=0, include_comun=0, include_editor=0)
        self.assertEqual(len(payload["posts"]), 10)
        self.assertTrue(all(post["author"].get("site_user_id") for post in payload["posts"]))
        self.assertLessEqual(len(queries), 30, "\n".join(q["sql"] for q in queries))
        sql = "\n".join(q["sql"] for q in queries)
        self.assertNotIn('SELECT DISTINCT "feeds_post"."id", "feeds_post"."author_id"', sql)

    def test_moderator_permissions_and_inactive_community(self):
        self.post()
        self.comun.is_active = False
        self.comun.save(update_fields=["is_active"])
        self.assertEqual(self.client.get(self.url).status_code, 404)
        response = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {_issue_token(self.owner)}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["comun"]["can_moderate"])

    def test_hidden_post_is_rechecked_between_id_selection_and_hydration(self):
        post = self.post()
        reader = CommunityFeedReader(service._comun_posts_base_queryset(self.comun), community=self.comun, language="ru")
        original = reader.filtered
        calls = 0

        def change_visibility(category_ids):
            nonlocal calls
            calls += 1
            if calls == 2:
                Post.objects.filter(pk=post.pk).update(companion_matched_at=timezone.now())
            return original(category_ids)

        with patch.object(reader, "filtered", side_effect=change_visibility):
            posts, _ = reader.page(offset=0, limit=10, prefetches=[])
        self.assertEqual(posts, [])

    def test_api_exposes_generation_timings_without_sql_text(self):
        self.post()
        response = self.client.get(self.url, {"include_counts": 0})
        timing = response["Server-Timing"]
        self.assertIn("app;dur=", timing)
        self.assertIn("db;dur=", timing)
        self.assertIn("queries", timing)
        self.assertNotIn("SELECT", timing)

    def test_moderator_card_permissions_use_prefetched_members(self):
        self.post()
        moderator = User.objects.create_user(username="feed-moderator")
        self.comun.moderators.add(moderator)
        response = self.client.get(self.url, {"include_comun": 0, "include_counts": 0},
                                   HTTP_AUTHORIZATION=f"Bearer {_issue_token(moderator)}")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["posts"][0]["comun"]["can_moderate"])
