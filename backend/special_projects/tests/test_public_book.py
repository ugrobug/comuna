from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from feeds.models import Post
from special_projects.public_book import (
    DISCUSSION_AUTHOR_TITLE,
    MAX_WORDS,
    PROJECT_SLUG,
    ensure_public_book_discussion_post,
    normalize_public_book_word,
    project_status_for_user,
    submit_word,
)
from special_projects.models import PublicBookBlockedWord, PublicBookState, PublicBookWord


User = get_user_model()


class PublicBookTests(TestCase):
    def test_normalize_requires_one_letter_word(self):
        self.assertEqual(
            normalize_public_book_word("Ёлка"),
            {"word": "Ёлка", "normalized_word": "елка"},
        )

        with self.assertRaisesMessage(ValueError, "одно слово"):
            normalize_public_book_word("два слова")
        with self.assertRaisesMessage(ValueError, "только из букв"):
            normalize_public_book_word("слово!")

    def test_submit_word_creates_position_and_updates_status(self):
        user = User.objects.create_user(username="book-user", password="pass")

        word = submit_word(user, "Свобода")
        status = project_status_for_user(user)

        self.assertEqual(word.position, 1)
        self.assertEqual(word.word, "Свобода")
        self.assertEqual(word.normalized_word, "свобода")
        self.assertEqual(PublicBookState.objects.get(project_slug=PROJECT_SLUG).total_words, 1)
        self.assertEqual(status["total_words"], 1)
        self.assertFalse(status["can_submit"])
        self.assertIsNotNone(status["discussion_post"]["id"])

    def test_submit_word_rejects_blocked_word(self):
        user = User.objects.create_user(username="blocked-book-user", password="pass")
        PublicBookBlockedWord.objects.create(word="Запрет")

        with self.assertRaisesMessage(ValueError, "нельзя добавить"):
            submit_word(user, "запрет")

        self.assertFalse(PublicBookWord.objects.exists())

    def test_submit_word_rejects_more_than_one_word_per_24_hours(self):
        user = User.objects.create_user(username="slow-book-user", password="pass")
        now = timezone.now()
        first = submit_word(user, "Первое")
        first.created_at = now
        first.save(update_fields=("created_at",))

        with patch("special_projects.public_book.timezone.now", return_value=now + timedelta(hours=23)):
            with self.assertRaisesMessage(ValueError, "24 часа"):
                submit_word(user, "Второе")

        with patch("special_projects.public_book.timezone.now", return_value=now + timedelta(hours=25)):
            second = submit_word(user, "Второе")

        self.assertEqual(second.position, 2)

    def test_submit_word_rejects_full_book(self):
        user = User.objects.create_user(username="late-book-user", password="pass")
        PublicBookState.objects.create(project_slug=PROJECT_SLUG, total_words=MAX_WORDS)

        with self.assertRaisesMessage(ValueError, "150000"):
            submit_word(user, "Финиш")

    def test_discussion_post_is_public(self):
        post = ensure_public_book_discussion_post()

        self.assertEqual(post.author.title, DISCUSSION_AUTHOR_TITLE)
        self.assertFalse(post.is_pending)
        self.assertFalse(post.is_blocked)
        self.assertEqual(post.raw_data.get("special_project", {}).get("slug"), PROJECT_SLUG)
        self.assertIn("Книга одного слова", post.title)
        self.assertIn(post, Post.objects.filter(is_blocked=False, is_pending=False))
