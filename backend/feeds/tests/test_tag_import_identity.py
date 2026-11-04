from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import connections, transaction
from django.test import TestCase, TransactionTestCase
from feeds.models import Author, Post, Tag
from feeds.views import _apply_post_tags


class ImportedTagIdentityTests(TestCase):
    def setUp(self):
        author = Author.objects.create(username='tag-identity')
        self.post = Post.objects.create(author=author, message_id=1, title='Example', content='Text')

    def test_existing_name_with_different_saved_lemma_does_not_abort_post_transaction(self):
        tag = Tag.objects.create(name='фильмы', lemma='фильм')
        with patch('feeds.views._lemmatize_tag', return_value='фильмы'), transaction.atomic():
            _apply_post_tags(self.post, ['фильмы'])
            self.post.title = 'Still writable'
            self.post.save(update_fields=['title'])
        self.assertEqual(list(self.post.tags.values_list('pk', flat=True)), [tag.pk])
        self.assertEqual(Tag.objects.count(), 1)
        tag.refresh_from_db()
        self.assertEqual(tag.lemma, 'фильм')

    def test_missing_morphology_reuses_name_and_preserves_tag_moderation(self):
        tag = Tag.objects.create(name='фильмы', lemma='фильм', is_active=False, hide_from_home=True)
        with patch('feeds.views._lemmatize_tag', return_value=''):
            _apply_post_tags(self.post, ['фильмы'])
        self.assertEqual(list(self.post.tags.values_list('pk', flat=True)), [tag.pk])
        tag.refresh_from_db()
        self.assertFalse(tag.is_active)
        self.assertTrue(tag.hide_from_home)

    def test_other_spelling_with_matching_lemma_still_reuses_existing_tag(self):
        tag = Tag.objects.create(name='фильм', lemma='фильм')
        with patch('feeds.views._lemmatize_tag', return_value='фильм'):
            _apply_post_tags(self.post, ['фильмы'])
        self.assertEqual(list(self.post.tags.values_list('pk', flat=True)), [tag.pk])
        self.assertEqual(Tag.objects.count(), 1)


class ConcurrentImportedTagIdentityTests(TransactionTestCase):
    def test_two_imports_can_create_same_tag_concurrently(self):
        author = Author.objects.create(username='concurrent-tag')
        posts = [Post.objects.create(author=author, message_id=n, title='Example', content='Text') for n in (1, 2)]
        barrier = Barrier(2)

        def lemma(value):
            barrier.wait(timeout=10)
            return 'shared'

        def assign(pk):
            try:
                with transaction.atomic():
                    post = Post.objects.get(pk=pk)
                    _apply_post_tags(post, ['shared'])
                return list(post.tags.values_list('pk', flat=True))
            finally:
                connections.close_all()

        with patch('feeds.views._lemmatize_tag', side_effect=lemma), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(assign, [p.pk for p in posts]))
        self.assertEqual(Tag.objects.count(), 1)
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(results[0]), 1)
