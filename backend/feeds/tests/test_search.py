import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from editor.models import PostTemplateConfig
from feeds import views
from feeds.models import Author, Post, PostLike, PostFavorite, Tag
from feeds.search import SearchReader
from ratings.models import RatingSettings
from ratings.service import calculate_author_rating
from users.service import _issue_token


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}})
class SearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = Author.objects.create(username="source", channel_id=8765)
        cls.user = get_user_model().objects.create_user(username="reader")
        cls.token = _issue_token(cls.user)
        RatingSettings.objects.get_or_create(pk=1)
        PostTemplateConfig.objects.update_or_create(template_type="basic", defaults={"is_active": True})

    def setUp(self):
        self.sequence = 0
        self.now = timezone.now()

    def post(self, **values):
        self.sequence += 1
        defaults = dict(author=self.author, message_id=self.sequence, title="Кино", content="<p>Кино и спорт</p>")
        defaults.update(values)
        return Post.objects.create(**defaults)

    def get(self, *, suggest=False, auth=False, **params):
        response = self.client.get(reverse("search-suggestions" if suggest else "search-content"),
                                   {"q": "кино", **params},
                                   **({"HTTP_AUTHORIZATION": f"Bearer {self.token}"} if auth else {}))
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def test_newest_first_is_global_stable_and_paginated_past_old_candidate_cap(self):
        posts = Post.objects.bulk_create([Post(author=self.author, message_id=i, title="Кино", content="Кино") for i in range(230)])
        Post.objects.filter(pk__in=[p.pk for p in posts]).update(created_at=self.now)
        expected = sorted([p.pk for p in posts], reverse=True)
        for page in (1, 2, 11, 12):
            with self.subTest(page=page):
                data = self.get(page=page, type="Posts").json()
                self.assertEqual([p['id'] for p in data['posts']], expected[(page-1)*20:page*20])
                self.assertEqual(data['total_posts'], min(page*20+1, len(posts)))

    def test_author_and_text_branches_merge_without_duplicates_or_fifty_author_cutoff(self):
        matching = [Author.objects.create(username=f"cinema{i:02}", description="кино", channel_id=10000+i) for i in range(55)]
        both = self.post(author=matching[0])
        author_only = self.post(author=matching[-1], title="Фотография", content="без совпадений")
        text_only = self.post()
        result = self.get(type="Posts").json()['posts']
        self.assertEqual([p['id'] for p in result], [text_only.pk, author_only.pk, both.pk])

    def test_ranked_branch_deduplicates_and_retains_text_rank_over_author_match(self):
        self.author.description = 'кино'
        self.author.save(update_fields=['description'])
        matched = self.post()
        only_author = self.post(title="другое", content="другое")
        ids = [p['id'] for p in self.get(type="Posts", sort="TopAll").json()['posts']]
        self.assertEqual(ids, [matched.pk, only_author.pk])

    def test_visibility_for_guest_user_and_suggestions(self):
        visible = self.post()
        for values in ({'is_pending': True}, {'is_blocked': True},
                       {'publish_at': self.now+timedelta(days=1)}, {'companion_matched_at': self.now}):
            self.post(**values)
        blocked = Author.objects.create(username='blocked', is_blocked=True)
        self.post(author=blocked)
        for auth in (False, True):
            for suggest in (False, True):
                self.assertEqual([p['id'] for p in self.get(auth=auth, suggest=suggest).json()['posts']], [visible.pk])

    def test_visibility_rechecked_between_selection_and_hydration(self):
        post = self.post()
        original = SearchReader.post_ids
        def hide(reader, offset, limit):
            ids = original(reader, offset, limit)
            Post.objects.filter(pk=post.pk).update(companion_matched_at=self.now)
            return ids
        with patch.object(SearchReader, 'post_ids', hide):
            self.assertEqual(self.get().json()['posts'], [])

    def test_legacy_card_keeps_votes_favorites_tags_and_community_permissions(self):
        comun = Comun.objects.create(name='Кино', slug='cinema', creator=self.user, telegram_source_author=self.author)
        post = self.post()
        tag = Tag.objects.create(name='cinema', lemma='cinema')
        post.tags.add(tag)
        PostLike.objects.create(post=post, user=self.user, value=1)
        PostFavorite.objects.create(post=post, user=self.user)
        personal = self.get(auth=True).json()['posts'][0]
        guest = self.get().json()['posts'][0]
        self.assertEqual(personal['user_vote'], 1)
        self.assertTrue(personal['is_favorite'])
        self.assertTrue(personal['comun']['can_moderate'])
        self.assertEqual(personal['comun']['id'], comun.pk)
        self.assertEqual(personal['tags'][0]['name'], 'cinema')
        self.assertEqual(guest['user_vote'], 0)
        self.assertFalse(guest['is_favorite'])
        self.assertFalse(guest['comun']['can_moderate'])
        for key in ('template', 'poll', 'views_count', 'author', 'source_url', 'content', 'has_full_content'):
            self.assertIn(key, personal)

    def test_people_keep_author_first_order_case_insensitive_dedupe_and_rating(self):
        author = Author.objects.create(username='Cinema', title='Кино', channel_id=555)
        self.post(author=author, rating=4, comments_count=3)
        get_user_model().objects.create_user(username='cinema', first_name='Кино')
        get_user_model().objects.create_user(username='person', first_name='Кино')
        get_user_model().objects.create_user(username='inactive', first_name='Кино', is_active=False)
        response = self.get(type='Users').json()['authors']
        self.assertEqual([row['username'] for row in response], ['Cinema', 'person'])
        self.assertEqual(response[0]['author_rating'], float(calculate_author_rating(author)))
        self.assertEqual(self.get(type='Users', limit=1, page=2).json()['authors'][0]['username'], 'person')

    def test_suggestions_are_compact_and_do_not_compute_ratings(self):
        for i in range(7):
            Author.objects.create(username=f'cinema{i}', title='Кино', channel_id=20000+i)
            Comun.objects.create(name=f'Кино {i}', slug=f'cinema-{i}')
            self.post(content='<p>Кино</p><img src="/media/uploads/post/sample-1280.webp">')
        with patch.object(views, '_calculate_author_ratings', side_effect=AssertionError('unnecessary rating')):
            data = self.get(suggest=True).json()
        self.assertEqual([len(data[k]) for k in ('posts','authors','communities')], [5,3,3])
        post = data['posts'][0]
        self.assertNotIn('content', post)
        self.assertNotIn('template', post)
        self.assertNotIn('user_vote', post)
        self.assertNotIn('author_rating', data['authors'][0])
        self.assertIn('-320.webp', post['thumbnail_url'])

    def test_cached_suggestions_do_not_reveal_matched_companion(self):
        self.post(raw_data={'template': {'type': 'companion', 'data': {}}})
        with override_settings(CACHES={'default': {'BACKEND':'django.core.cache.backends.locmem.LocMemCache', 'LOCATION':'search-test'}}):
            cache.clear()
            first = self.get(suggest=True)
            self.assertIn('no-store', first['Cache-Control'])
            Post.objects.all().update(companion_matched_at=self.now)
            self.assertEqual(self.get(suggest=True).json()['posts'], [])
            cache.clear()

    def test_empty_punctuation_short_prefix_and_input_bounds(self):
        self.post()
        for q in ('', '!!!'):
            self.assertEqual(self.get(q=q).json()['posts'], [])
        self.assertEqual(self.get(suggest=True, q='к').json()['posts'], [])
        self.assertTrue(self.get(q='КИНО').json()['posts'])
        self.assertEqual(self.client.get(reverse('search-content'), {'q': 'x'*513}).status_code, 400)
        self.assertEqual(self.client.get(reverse('search-content'), {'q': 'кино', 'page': 10000}).status_code, 400)
        self.assertEqual(self.get(page='bad', limit='bad').json()['page'], 1)

    def test_only_final_page_is_hydrated(self):
        Post.objects.bulk_create([Post(author=self.author, message_id=i, title='Кино', content='Кино') for i in range(60)])
        original = Post.from_db
        loaded = []
        def track(*args):
            obj = original(*args)
            loaded.append(obj.pk)
            return obj
        with patch.object(Post, 'from_db', side_effect=track):
            response = self.get(limit=5, page=2, type='Posts').json()
        self.assertEqual(len(loaded), 5)
        self.assertEqual(set(loaded), {p['id'] for p in response['posts']})

    def test_query_budget_with_distinct_authors_communities_and_roles(self):
        for i in range(30):
            author = Author.objects.create(username=f'source{i}', channel_id=30000+i)
            comun = Comun.objects.create(name=f'Community {i}', slug=f'comun-{i}', telegram_source_author=author)
            comun.moderators.add(self.user)
            self.post(author=author)
        for auth in (False, True):
            counts = []
            for limit in (10,30):
                with CaptureQueriesContext(connection) as queries:
                    response = self.get(limit=limit, auth=auth)
                self.assertEqual(len(response.json()['posts']), limit)
                counts.append(len(queries))
            self.assertLessEqual(counts[1], counts[0]+1)
            self.assertLessEqual(counts[1], 30)
