from django.test import SimpleTestCase, TestCase

from feeds.models import Author, Post
from feeds.translation_quality import (
    MIN_POST_TRANSLATION_TEXT_LENGTH,
    post_meets_translation_quality,
    post_translation_text_length,
)


class PostTranslationTextLengthTests(SimpleTestCase):
    def test_counts_only_post_content_without_hashtags(self) -> None:
        content = f"<p>{'а' * MIN_POST_TRANSLATION_TEXT_LENGTH} #новости #тест</p>"

        self.assertEqual(
            post_translation_text_length(content),
            MIN_POST_TRANSLATION_TEXT_LENGTH,
        )

    def test_does_not_count_title_towards_limit(self) -> None:
        post = Post(
            title="Очень длинный заголовок " * 50,
            content=f"<p>{'а' * (MIN_POST_TRANSLATION_TEXT_LENGTH - 1)} #тег</p>",
        )

        self.assertFalse(post_meets_translation_quality(post))


class PostTranslationTextLengthPersistenceTests(TestCase):
    def test_post_save_refreshes_translation_text_length(self) -> None:
        author = Author.objects.create(username="translation-quality-author")
        post = Post.objects.create(
            author=author,
            message_id=1,
            title="Заголовок не участвует в подсчете",
            content=f"<p>{'а' * MIN_POST_TRANSLATION_TEXT_LENGTH} #неучитываемыйтег</p>",
        )

        self.assertEqual(
            post.translation_text_length,
            MIN_POST_TRANSLATION_TEXT_LENGTH,
        )
        self.assertTrue(post_meets_translation_quality(post))
