from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase, override_settings

from feeds.models import (
    Author,
    POST_TRANSLATION_STATUS_FAILED,
    POST_TRANSLATION_STATUS_PENDING,
    POST_TRANSLATION_STATUS_TRANSLATED,
    Post,
    PostTranslation,
)
from feeds.translation_service import (
    PostTranslationError,
    queue_post_translation,
    translate_post_to_language,
)


class FakeOpenRouterResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_API_URL="https://openrouter.test/api/v1/chat/completions",
    OPENROUTER_TRANSLATION_MODEL="deepseek/deepseek-v4-flash",
    SITE_BASE_URL="https://tambur.pub",
)
class PostTranslationServiceTests(TestCase):
    def setUp(self) -> None:
        self.author = Author.objects.create(username="source")
        self.post = Post.objects.create(
            author=self.author,
            message_id=1,
            title="Заголовок",
            content="<p>Первый абзац</p>",
        )

    @patch("feeds.translation_service.requests.post")
    def test_translate_post_to_language_saves_translation(self, post_mock) -> None:
        post_mock.return_value = FakeOpenRouterResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title": "Baslik", "content": "<p>Ilk paragraf</p>"}'
                            )
                        }
                    }
                ]
            },
        )

        translation = translate_post_to_language(self.post, "tr")

        self.assertEqual(translation.status, POST_TRANSLATION_STATUS_TRANSLATED)
        self.assertEqual(translation.language, "tr")
        self.assertEqual(translation.title, "Baslik")
        self.assertEqual(translation.content, "<p>Ilk paragraf</p>")
        self.assertEqual(translation.preview_content, "<p>Ilk paragraf</p>")
        self.assertEqual(translation.model, "deepseek/deepseek-v4-flash")
        self.assertEqual(self.post.title, "Заголовок")
        post_mock.assert_called_once()
        request_payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(request_payload["model"], "deepseek/deepseek-v4-flash")
        self.assertEqual(request_payload["response_format"], {"type": "json_object"})

    @patch("feeds.translation_service.requests.post")
    def test_failed_openrouter_response_marks_translation_failed(self, post_mock) -> None:
        post_mock.return_value = FakeOpenRouterResponse(
            429,
            {"error": {"message": "rate limit"}},
        )

        with self.assertRaises(PostTranslationError):
            translate_post_to_language(self.post, "id")

        translation = PostTranslation.objects.get(post=self.post, language="id")
        self.assertEqual(translation.status, POST_TRANSLATION_STATUS_FAILED)
        self.assertIn("rate limit", translation.error_message)

    @override_settings(OPENROUTER_API_KEY="")
    def test_missing_api_key_marks_translation_failed(self) -> None:
        with self.assertRaises(PostTranslationError):
            translate_post_to_language(self.post, "tr")

        translation = PostTranslation.objects.get(post=self.post, language="tr")
        self.assertEqual(translation.status, POST_TRANSLATION_STATUS_FAILED)
        self.assertIn("OPENROUTER_API_KEY", translation.error_message)

    @patch("feeds.translation_service.subprocess.Popen")
    def test_queue_post_translation_sets_pending_and_starts_worker(self, popen_mock) -> None:
        translations = queue_post_translation(self.post, ["tr", "id"])

        self.assertEqual([translation.language for translation in translations], ["tr", "id"])
        self.assertEqual(
            list(
                PostTranslation.objects.filter(post=self.post)
                .order_by("language")
                .values_list("language", "status")
            ),
            [("id", POST_TRANSLATION_STATUS_PENDING), ("tr", POST_TRANSLATION_STATUS_PENDING)],
        )
        popen_mock.assert_called_once()
        command = popen_mock.call_args.args[0]
        self.assertIn("translate_post", command)
        self.assertIn(str(self.post.pk), command)
        self.assertIn("tr", command)
        self.assertIn("id", command)
