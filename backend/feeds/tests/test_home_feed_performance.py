from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from communities import service
from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from editor.models import PostTemplateConfig
from feeds import views
from feeds.home_reader import HomeFeedReader, HomeFeedCardBatch
from feeds.models import (
    Author, Post, PostTranslation, PublicFeedItem, PostRead, PostLike, PostFavorite,
    PostComment, PostCommentLike, Tag,
)
from my_feed.models import UserFeedSettings
from ratings.models import RatingSettings
from ratings.service import calculate_author_rating, calculate_post_total_rating
from users.models import AuthorAdmin
from users.service import _issue_token

User = get_user_model()


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class HomeFeedPerformanceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="hot-reader")
        self.other = User.objects.create_user(username="hot-other")
        self.token = _issue_token(self.user)
        self.author = Author.objects.create(username="hot-source", channel_id=987)
        self.now = timezone.now()
        self.sequence = 0
        self.url = reverse("home-feed")
        RatingSettings.objects.get_or_create(pk=1)
        PostTemplateConfig.objects.update_or_create(template_type="basic", defaults={"is_active": True})

    def post(self, **values):
        self.sequence += 1
        defaults = dict(author=self.author, message_id=self.sequence, title=f"Post {self.sequence}",
                        content="<p>Текст карточки</p>", original_language="ru", rating=2)
        defaults.update(values)
        post = Post.objects.create(**defaults)
        Post.objects.filter(pk=post.pk).update(created_at=self.now - timedelta(minutes=self.sequence))
        post.refresh_from_db()
        return post

    def snapshot(self, posts):
        PublicFeedItem.objects.bulk_create([
            PublicFeedItem(feed="home", post=post, rank=index + 1, score=999,
                           post_created_at=post.created_at, author_id_snapshot=post.author_id)
            for index, post in enumerate(posts)
        ])

    def get(self, *, auth=False, **params):
        response = self.client.get(self.url, {"card": 1, **params},
                                   **({"HTTP_AUTHORIZATION": f"Bearer {self.token}"} if auth else {}))
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def test_language_membership_matches_join_without_duplicate_cards(self):
        original = self.post()
        translated = self.post(original_language="en")
        pending = self.post(original_language="en")
        for language in ("en", "de", "fr"):
            PostTranslation.objects.create(post=original, language=language, status="translated")
        PostTranslation.objects.create(post=translated, language="ru", status="translated", title="Переведено")
        PostTranslation.objects.create(post=pending, language="ru", status="pending")
        self.snapshot([original, translated, pending])
        for base, prefix in ((Post.objects.all(), ""), (PublicFeedItem.objects.all(), "post__")):
            for language in ("ru", "en", "de", "es"):
                with self.subTest(prefix=prefix, language=language):
                    new = HomeFeedReader(language=language).for_language(base, prefix=prefix)
                    old = views._filter_posts_for_language(base, language, prefix=prefix)
                    self.assertSetEqual(set(new.values_list("pk", flat=True)), set(old.values_list("pk", flat=True)))
        for params in ({}, {"card": 0}):
            cards = self.get(**params)["posts"]
            self.assertEqual([p["id"] for p in cards], [original.pk, translated.pk])
            self.assertEqual(cards[1]["title"], "Переведено")
            self.assertTrue(cards[1]["is_translated"])

    def test_read_filters_keep_fourteen_day_window_and_user_isolation(self):
        recent, old, unread, others = [self.post() for _ in range(4)]
        PostRead.objects.create(post=recent, user=self.user)
        marker = PostRead.objects.create(post=old, user=self.user)
        PostRead.objects.filter(pk=marker.pk).update(read_at=self.now - timedelta(days=15))
        PostRead.objects.create(post=others, user=self.other)
        self.snapshot([recent, old, unread, others])
        self.assertEqual([p["id"] for p in self.get(auth=True, hide_read=1)["posts"]], [old.pk, unread.pk, others.pk])
        self.assertEqual([p["id"] for p in self.get(auth=True, only_read=1)["posts"]], [recent.pk])
        self.assertEqual([p["id"] for p in self.get(auth=True, only_read=1, hide_read=1)["posts"]], [recent.pk])
        self.assertEqual(self.client.get(self.url, {"only_read": 1}).status_code, 401)
        self.assertEqual(len(self.get(hide_read=1)["posts"]), 4)

    def test_visibility_is_preserved_on_live_path(self):
        visible = self.post()
        for values in ({"is_pending": True}, {"is_blocked": True},
                       {"publish_at": self.now + timedelta(days=1)}, {"companion_matched_at": self.now}):
            self.post(**values)
        for flag in ("is_blocked", "shadow_banned"):
            author = Author.objects.create(username=flag, **{flag: True})
            self.post(author=author)
        forced = self.post(author=Author.objects.create(username="forced", shadow_banned=True, force_home=True))
        hidden_tag = Tag.objects.create(name="hidden", lemma="hidden", hide_from_home=True)
        self.post().tags.add(hidden_tag)
        comun = Comun.objects.create(name="Hidden", slug="hidden", hide_from_home=True)
        self.post(raw_data={"source": "manual_comun", "comun_slug": comun.slug})
        category = ComunCategory.objects.create(comun=comun, name="Hidden", slug="hidden", hide_from_home=True)
        ComunPostCategoryAssignment.objects.create(post=self.post(), comun=comun, category=category)
        self.assertSetEqual({p["id"] for p in self.get(auth=True, hide_read=1)["posts"]}, {visible.pk, forced.pk})

    def test_hidden_posts_authors_and_all_community_links_on_both_paths(self):
        visible = self.post(raw_data={"comun_slug": "unrelated"})
        explicit = self.post()
        author = Author.objects.create(username="hidden-author", channel_id=456)
        by_author = self.post(author=author)
        source = Author.objects.create(username="hidden-channel", channel_id=789)
        comun = Comun.objects.create(name="Hidden", slug="hidden", telegram_source_author=source)
        raw = self.post(raw_data={"source": "max", "comun_slug": comun.slug})
        assigned = self.post()
        ComunPostCategoryAssignment.objects.create(post=assigned, comun=comun)
        from_source = self.post(author=source)
        self.snapshot([visible, explicit, by_author, raw, assigned, from_source])
        UserFeedSettings.objects.create(user=self.user, hidden_post_ids=[explicit.pk],
                                       hidden_authors=["HIDDEN-AUTHOR"], hidden_comuns=[comun.slug])
        for params in ({}, {"hide_read": 1}, {"card": 0}):
            with self.subTest(params=params):
                self.assertEqual([p["id"] for p in self.get(auth=True, **params)["posts"]], [visible.pk])
        self.assertEqual(len(self.get()["posts"]), 6)

    def test_rating_and_author_alternation_daily_quota_and_offsets(self):
        other_author = Author.objects.create(username="second", channel_id=321)
        a1, a2, b1, a3 = self.post(), self.post(), self.post(author=other_author), self.post()
        expected = [a1.pk, b1.pk, a2.pk, a3.pk]
        self.assertEqual([p["id"] for p in self.get()["posts"]], expected)
        self.assertEqual([p["id"] for p in self.get(offset=1, limit=2)["posts"]], expected[1:3])
        negative = self.post(author=Author.objects.create(username="negative"), rating=-100)
        self.assertNotIn(negative.pk, [p["id"] for p in self.get()["posts"]])
        comun = Comun.objects.create(name="Daily", slug="daily")
        Post.objects.filter(pk__in=[a1.pk, a2.pk, a3.pk]).update(raw_data={"comun_slug": comun.slug})
        RatingSettings.objects.filter(pk=1).update(home_posts_per_community_per_day=2)
        self.assertEqual([p["id"] for p in self.get()["posts"]], [a1.pk, b1.pk, a2.pk])

    def test_batch_scores_equal_original_fractional_ratings_for_read_and_unread(self):
        RatingSettings.objects.filter(pk=1).update(post_author_rating_weight="0.35", post_community_rating_weight="0.25")
        comun = Comun.objects.create(name="Rated", slug="rated", rating_score="12.50")
        post = self.post(comments_count=3, rating=7, raw_data={"comun_slug": comun.slug})
        comment = PostComment.objects.create(post=post, user=self.user, body="Comment")
        PostCommentLike.objects.create(comment=comment, user=self.other)
        PostLike.objects.create(post=post, user=self.user, value=-1)
        PostFavorite.objects.create(post=post, user=self.user)
        author_score = round(float(calculate_author_rating(post.author)), 2)
        expected = float(calculate_post_total_rating(post, author_rating=author_score))
        for params in ({}, {"card": 0}, {"hide_read": 1}):
            card = self.get(auth=True, **params)["posts"][0]
            self.assertEqual(card["score"], expected)
            self.assertEqual(card["user_vote"], -1)
            self.assertTrue(card["is_favorite"])
        PostRead.objects.create(post=post, user=self.user)
        for card_mode in (0, 1):
            card = self.get(auth=True, only_read=1, card=card_mode)["posts"][0]
            self.assertEqual(card["score"], expected)
            self.assertEqual(card["user_vote"], -1)
            self.assertTrue(card["is_favorite"])

    def test_card_community_precedence_and_roles_match_individual_serializer(self):
        source = Comun.objects.create(name="Source", slug="source", telegram_source_author=self.author, creator=self.other)
        assigned = Comun.objects.create(name="Assigned", slug="assigned", creator=self.other)
        manual = Comun.objects.create(name="Manual", slug="manual", creator=self.user)
        assigned.moderators.add(self.user)
        posts = [self.post(raw_data={"comun_slug": manual.slug}), self.post(), self.post()]
        ComunPostCategoryAssignment.objects.create(post=posts[0], comun=assigned)
        ComunPostCategoryAssignment.objects.create(post=posts[1], comun=assigned)
        request = RequestFactory().get(self.url)
        expected = [service._serialize_post_comun(request, p, self.user) for p in posts]
        loaded = list(Post.objects.filter(pk__in=[p.pk for p in posts]).select_related("author", "author__telegram_source_comun").order_by("pk"))
        HomeFeedCardBatch(prepare_authors=views._prepare_post_card_authors,
                          prepare_communities=service._prepare_post_card_comuns).prepare(request, loaded, self.user)
        with self.assertNumQueries(0):
            actual = [service._serialize_post_comun(request, p, self.user) for p in loaded]
        self.assertEqual(actual, expected)
        self.assertEqual([c["can_moderate"] for c in actual], [True, True, False])
        manual.is_active = False
        manual.save(update_fields=["is_active"])
        self.assertEqual(self.get(auth=True)["posts"][0]["comun"]["id"], assigned.pk)
        self.assertFalse(self.get()["posts"][1]["comun"]["can_moderate"])

    def test_equal_dates_have_stable_non_overlapping_read_pages(self):
        posts = [self.post() for _ in range(5)]
        Post.objects.filter(pk__in=[p.pk for p in posts]).update(created_at=self.now)
        PostRead.objects.bulk_create([PostRead(post=p, user=self.user) for p in posts])
        ids = [p["id"] for offset in (0, 2, 4) for p in self.get(auth=True, only_read=1, limit=2, offset=offset)["posts"]]
        self.assertEqual(ids, [p.pk for p in posts])
        self.assertEqual(self.get(auth=True, only_read=1, offset=999)["posts"], [])

    def test_reader_rechecks_visibility_between_queries(self):
        post = self.post()
        reader = HomeFeedReader(language="ru")
        query = reader.for_language(Post.objects.filter(companion_matched_at__isnull=True))
        changed = False

        def hide_after_selection(execute, sql, params, many, context):
            nonlocal changed
            result = execute(sql, params, many, context)
            if not changed and sql.startswith("SELECT"):
                changed = True
                Post.objects.filter(pk=post.pk).update(companion_matched_at=self.now)
            return result

        with connection.execute_wrapper(hide_after_selection):
            posts = reader.load(query, limit=10, ordering=("-created_at", "pk"), related=("author",), prefetches=[])
        self.assertEqual(posts, [])

    def test_ten_and_thirty_distinct_communities_have_bounded_queries(self):
        posts = []
        for index in range(30):
            author = Author.objects.create(username=f"source-{index}", channel_id=1000 + index)
            comun = Comun.objects.create(name=f"Community {index}", slug=f"community-{index}",
                                         telegram_source_author=author, creator=self.other)
            comun.moderators.add(self.user)
            posts.append(self.post(author=author))
        self.snapshot(posts)
        for auth, params in ((False, {}), (True, {}), (True, {"hide_read": 1})):
            counts = []
            for limit in (10, 30):
                self.get(auth=auth, limit=limit, **params)
                with CaptureQueriesContext(connection) as queries:
                    result = self.get(auth=auth, limit=limit, **params)
                self.assertEqual(len(result["posts"]), limit)
                self.assertLessEqual(len(queries), 30, "\n".join(q["sql"] for q in queries))
                sql = "\n".join(q["sql"] for q in queries)
                self.assertNotIn('SELECT DISTINCT "feeds_post"."id", "feeds_post"."author_id"', sql)
                self.assertNotIn('SELECT DISTINCT "feeds_publicfeeditem"."id", "feeds_publicfeeditem"."feed"', sql)
                counts.append(len(queries))
            self.assertEqual(counts[0], counts[1])

    def test_deep_page_serializes_only_requested_cards(self):
        for _ in range(30):
            self.post()
        with patch.object(views, "_serialize_lightweight_post_card", wraps=views._serialize_lightweight_post_card) as serialize:
            payload = self.get(hide_read=1, offset=20, limit=10)
        self.assertEqual(len(payload["posts"]), 10)
        self.assertEqual(serialize.call_count, 10)

    def test_personal_author_mapping_uses_verified_owner(self):
        author = Author.objects.create(username="personal")
        AuthorAdmin.objects.create(author=author, user=self.user, verified_at=self.now)
        self.post(author=author)
        card = self.get()["posts"][0]
        self.assertEqual(card["author"]["site_user_id"], self.user.pk)

    def test_empty_snapshot_keeps_live_fallback_and_parameter_validation(self):
        post = self.post()
        payload = self.get(limit="bad", offset="bad")
        self.assertNotIn("materialized", payload)
        self.assertEqual([p["id"] for p in payload["posts"]], [post.pk])
        self.assertEqual(self.get(offset=999)["posts"], [])

    def test_templates_and_permissions_match_individual_cards_for_two_users_and_guest(self):
        comun = Comun.objects.create(name="Templates", slug="templates", creator=self.user,
                                     telegram_source_author=self.author)
        template_data = {
            "basic": {},
            "event": {"starts_at": (self.now + timedelta(days=1)).isoformat()},
            "question": {},
            "bug_report": {"status": "new"},
            "movie_review": {"title": "Фильм", "author_rating": "8"},
        }
        posts = []
        for template_type, data in template_data.items():
            PostTemplateConfig.objects.update_or_create(template_type=template_type, defaults={"is_active": True})
            post = self.post(raw_data={"template": {"type": template_type, "version": 1, "data": data},
                                       "comun_slug": comun.slug})
            template = views._serialize_post_template(post)
            if template_type == "basic":
                self.assertIsNone(template)
            else:
                self.assertIsNotNone(template, template_type)
                self.assertEqual(template["type"], template_type)
            posts.append(post)
        RatingSettings.objects.filter(pk=1).update(home_posts_per_community_per_day=10)
        self.snapshot(posts)
        with patch.object(views.timezone, "now", return_value=self.now):
            for user in (self.user, self.other, None):
                request = RequestFactory().get(self.url)
                expected = [views._serialize_lightweight_post_card(
                    request, p, user, now=self.now,
                    score_override=float(calculate_post_total_rating(
                        p, author_rating=round(float(calculate_author_rating(p.author)), 2))),
                ) for p in Post.objects.filter(pk__in=[p.pk for p in posts]).order_by("pk")]
                response = self.client.get(self.url, {"card": 1},
                                           **({"HTTP_AUTHORIZATION": f"Bearer {_issue_token(user)}"} if user else {}))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["posts"], expected)

    def test_home_response_cache_does_not_leak_personal_votes_or_roles(self):
        post = self.post()
        self.snapshot([post])
        PostLike.objects.create(post=post, user=self.user, value=1)
        PostFavorite.objects.create(post=post, user=self.user)
        with override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                                                  "LOCATION": "home-feed-regression-isolation"}}):
            from django.core.cache import cache
            cache.clear()
            self.get()  # Populate the anonymous response cache first.
            personal = self.get(auth=True)["posts"][0]
            guest = self.get()["posts"][0]
            self.assertEqual(personal["user_vote"], 1)
            self.assertTrue(personal["is_favorite"])
            self.assertEqual(guest["user_vote"], 0)
            self.assertFalse(guest["is_favorite"])
            cache.clear()
