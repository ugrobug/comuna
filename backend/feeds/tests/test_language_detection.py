from django.test import SimpleTestCase

from feeds.language_detection import detect_post_language


class PostLanguageDetectionTests(SimpleTestCase):
    def test_detects_english_post_from_title_and_content(self):
        language = detect_post_language(
            "A practical guide to community management",
            (
                "<p>This article explains how community owners can welcome new members, "
                "publish useful updates, and keep discussions focused and respectful.</p>"
            ),
        )

        self.assertEqual(language, "en")

    def test_detects_russian_post(self):
        language = detect_post_language(
            "Практическое руководство по управлению сообществом",
            (
                "<p>В этой статье подробно рассказывается, как встречать новых участников, "
                "публиковать полезные материалы и поддерживать содержательное обсуждение.</p>"
            ),
            fallback="en",
        )

        self.assertEqual(language, "ru")

    def test_keeps_fallback_for_short_ambiguous_text(self):
        self.assertEqual(
            detect_post_language("Tambur", "<p>New post</p>", fallback="tr"),
            "tr",
        )

    def test_russian_body_outweighs_short_english_title(self):
        language = detect_post_language(
            "Open Source",
            (
                "<p>Это подробная публикация на русском языке. В тексте достаточно слов, "
                "чтобы определить язык всего материала и не ориентироваться только на "
                "короткий английский заголовок.</p>"
            ),
            fallback="en",
        )

        self.assertEqual(language, "ru")

    def test_english_body_outweighs_short_russian_title(self):
        language = detect_post_language(
            "Новая статья",
            (
                "<p>This detailed article is written in English. The body contains enough "
                "meaningful words to determine the source language despite a short Russian title.</p>"
            ),
        )

        self.assertEqual(language, "en")
