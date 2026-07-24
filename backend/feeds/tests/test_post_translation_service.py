from __future__ import annotations

import base64
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from feeds.models import (
    Author,
    CONTENT_TRANSLATION_KIND_COMMENT,
    CONTENT_TRANSLATION_KIND_COMUN,
    CONTENT_TRANSLATION_KIND_POST,
    CONTENT_TRANSLATION_TASK_STATUS_DONE,
    CONTENT_TRANSLATION_TASK_STATUS_FAILED,
    CONTENT_TRANSLATION_TASK_STATUS_PENDING,
    Comun,
    ContentTranslationRun,
    ContentTranslationSettings,
    ContentTranslationTask,
    POST_TRANSLATION_STATUS_FAILED,
    POST_TRANSLATION_STATUS_PENDING,
    POST_TRANSLATION_STATUS_TRANSLATED,
    Post,
    PostComment,
    PostTranslation,
)
from feeds.translation_service import (
    CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS,
    PostTranslationError,
    post_translation_record_is_current,
    process_due_translation_tasks,
    process_translation_task,
    queue_post_translation,
    translate_post_to_language,
)

User = get_user_model()


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
        self.user = User.objects.create_user(username="commenter")
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
        self.assertEqual(request_payload["max_tokens"], 65_536)
        self.assertEqual(
            request_payload["reasoning"],
            {"effort": "none", "exclude": True},
        )
        self.assertEqual(
            request_payload["provider"],
            {"sort": "throughput", "require_parameters": True},
        )

    @patch("feeds.translation_service.requests.post")
    def test_translates_english_original_to_russian(self, post_mock) -> None:
        self.post.title = "An English source article"
        self.post.content = "<p>This article was originally written in English.</p>"
        self.post.original_language = "en"
        self.post.save(update_fields=["title", "content", "original_language", "updated_at"])
        post_mock.return_value = FakeOpenRouterResponse(
            200,
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"title": "Статья на английском", '
                                '"content": "<p>Эта статья изначально написана на английском.</p>"}'
                            )
                        }
                    }
                ]
            },
        )

        translation = translate_post_to_language(self.post, "ru")

        self.assertEqual(translation.language, "ru")
        request_payload = post_mock.call_args.kwargs["json"]
        user_payload = json.loads(request_payload["messages"][1]["content"])
        self.assertEqual(user_payload["source_language"], "English")
        self.assertEqual(user_payload["target_language"], "Russian")

    @override_settings(
        CONTENT_TRANSLATION_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="deepseek-test-key",
        DEEPSEEK_API_URL="https://api.deepseek.test/chat/completions",
        DEEPSEEK_TRANSLATION_MODEL="deepseek-v4-flash",
    )
    @patch("feeds.translation_service.requests.post")
    def test_translate_post_to_language_uses_deepseek_direct_payload(self, post_mock) -> None:
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
        self.assertEqual(translation.model, "deepseek-v4-flash")
        post_mock.assert_called_once()
        self.assertEqual(
            post_mock.call_args.args[0],
            "https://api.deepseek.test/chat/completions",
        )
        request_payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(request_payload["model"], "deepseek-v4-flash")
        self.assertEqual(request_payload["response_format"], {"type": "json_object"})
        self.assertEqual(request_payload["max_tokens"], 65_536)
        self.assertEqual(request_payload["thinking"], {"type": "disabled"})
        self.assertNotIn("provider", request_payload)
        self.assertNotIn("reasoning", request_payload)
        request_headers = post_mock.call_args.kwargs["headers"]
        self.assertNotIn("X-OpenRouter-Title", request_headers)

    @patch("feeds.translation_service.requests.post")
    def test_translate_post_decodes_and_reencodes_base64_editorjs(self, post_mock) -> None:
        source_editor = {
            "time": 1,
            "blocks": [
                {
                    "id": "paragraph-1",
                    "type": "paragraph",
                    "data": {"text": "Первый абзац"},
                }
            ],
            "version": "2.30.0",
        }
        translated_editor = {
            **source_editor,
            "blocks": [
                {
                    "id": "paragraph-1",
                    "type": "paragraph",
                    "data": {"text": "First paragraph"},
                }
            ],
        }
        self.post.content = base64.b64encode(
            json.dumps(source_editor, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        self.post.save(update_fields=["content", "updated_at"])
        post_mock.return_value = FakeOpenRouterResponse(
            200,
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {"title": "Title", "content": translated_editor},
                                ensure_ascii=False,
                            )
                        },
                    }
                ]
            },
        )

        translation = translate_post_to_language(self.post, "en")

        request_payload = post_mock.call_args.kwargs["json"]
        self.assertEqual(request_payload["messages"][1]["content"].count(self.post.content), 0)
        user_payload = json.loads(request_payload["messages"][1]["content"])
        self.assertEqual(user_payload["post"]["content"], source_editor)
        self.assertEqual(user_payload["post"]["content_format"], "editorjs")
        decoded_translation = json.loads(
            base64.b64decode(translation.content).decode("utf-8")
        )
        self.assertEqual(decoded_translation, translated_editor)
        self.assertIn("First paragraph", translation.preview_content)

    @patch("feeds.translation_service.requests.post")
    def test_translate_post_rejects_changed_editorjs_structure(self, post_mock) -> None:
        source_editor = {
            "blocks": [
                {"id": "paragraph-1", "type": "paragraph", "data": {"text": "Текст"}}
            ]
        }
        self.post.content = json.dumps(source_editor, ensure_ascii=False)
        self.post.save(update_fields=["content", "updated_at"])
        post_mock.return_value = FakeOpenRouterResponse(
            200,
            {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "title": "Title",
                                    "content": {
                                        "blocks": [
                                            {
                                                "id": "changed-id",
                                                "type": "paragraph",
                                                "data": {"text": "Text"},
                                            }
                                        ]
                                    },
                                }
                            )
                        },
                    }
                ]
            },
        )

        with self.assertRaisesMessage(PostTranslationError, "изменил id блока EditorJS"):
            translate_post_to_language(self.post, "en")

        translation = PostTranslation.objects.get(post=self.post, language="en")
        self.assertEqual(translation.status, POST_TRANSLATION_STATUS_FAILED)

    def test_editorjs_translation_with_wrapped_base64_is_not_current(self) -> None:
        source_editor = {
            "blocks": [
                {"id": "paragraph-1", "type": "paragraph", "data": {"text": "Текст"}}
            ]
        }
        encoded = base64.b64encode(
            json.dumps(source_editor, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        self.post.content = encoded
        self.post.save(update_fields=["content", "updated_at"])
        translation = PostTranslation.objects.create(
            post=self.post,
            language="en",
            title="Title",
            content=f"<p>{encoded}</p>",
            status=POST_TRANSLATION_STATUS_TRANSLATED,
        )

        self.assertFalse(post_translation_record_is_current(self.post, translation))

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

    def test_post_save_schedules_auto_translation_after_ten_minutes(self) -> None:
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )

        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_PENDING)
        self.assertEqual(task.source_updated_at, self.post.updated_at)
        self.assertGreaterEqual(task.scheduled_at, self.post.updated_at + timedelta(minutes=10))

    def test_post_edit_reschedules_auto_translation(self) -> None:
        original_task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )

        self.post.title = "Обновленный заголовок"
        self.post.save(update_fields=["title", "updated_at"])
        self.post.refresh_from_db()
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )

        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_PENDING)
        self.assertGreater(task.source_updated_at, original_task.source_updated_at)
        self.assertGreater(task.scheduled_at, original_task.scheduled_at)

    def test_comment_save_schedules_auto_translation_after_one_minute(self) -> None:
        comment = PostComment.objects.create(
            post=self.post,
            user=self.user,
            body="Комментарий",
        )
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_COMMENT,
            object_id=comment.pk,
        )

        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_PENDING)
        self.assertEqual(task.source_updated_at, comment.updated_at)
        self.assertGreaterEqual(task.scheduled_at, comment.updated_at + timedelta(minutes=1))

    def test_negative_comun_does_not_schedule_auto_translation(self) -> None:
        comun = Comun.objects.create(
            name="Минусовая комуна",
            slug="negative-comun",
            product_description="Описание",
            rules_text="Правила",
            rating_score=-1,
        )

        self.assertFalse(
            ContentTranslationTask.objects.filter(
                kind=CONTENT_TRANSLATION_KIND_COMUN,
                object_id=comun.pk,
            ).exists()
        )

    @patch("feeds.translation_service.translate_post_to_language")
    def test_process_due_translation_tasks_claims_due_batch(self, translate_mock) -> None:
        second_post = Post.objects.create(
            author=self.author,
            message_id=2,
            title="Второй заголовок",
            content="<p>Второй абзац</p>",
        )
        due_at = timezone.now() - timedelta(minutes=1)
        ContentTranslationTask.objects.filter(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id__in=[self.post.pk, second_post.pk],
        ).update(scheduled_at=due_at)

        stats = process_due_translation_tasks(limit=1)

        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["done"], 1)
        self.assertEqual(translate_mock.call_count, 7)
        self.assertEqual(
            ContentTranslationTask.objects.filter(
                kind=CONTENT_TRANSLATION_KIND_POST,
                status=CONTENT_TRANSLATION_TASK_STATUS_DONE,
            ).count(),
            1,
        )
        self.assertEqual(
            ContentTranslationTask.objects.filter(
                kind=CONTENT_TRANSLATION_KIND_POST,
                status=CONTENT_TRANSLATION_TASK_STATUS_PENDING,
            ).count(),
            1,
        )

    @patch("feeds.translation_service.translate_post_to_language")
    def test_process_due_translation_tasks_retries_old_failed_tasks(self, translate_mock) -> None:
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )
        retry_before = timezone.now() - timedelta(minutes=16)
        ContentTranslationTask.objects.filter(pk=task.pk).update(
            status=CONTENT_TRANSLATION_TASK_STATUS_FAILED,
            scheduled_at=retry_before,
            updated_at=retry_before,
            last_error="DeepSeek timeout",
        )

        stats = process_due_translation_tasks(limit=1)

        self.assertEqual(stats["processed"], 1)
        self.assertEqual(stats["done"], 1)
        task.refresh_from_db()
        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_DONE)

    @patch("feeds.translation_service.translate_post_to_language")
    def test_process_due_translation_tasks_stops_after_max_attempts(self, translate_mock) -> None:
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )
        retry_before = timezone.now() - timedelta(minutes=16)
        ContentTranslationTask.objects.filter(pk=task.pk).update(
            status=CONTENT_TRANSLATION_TASK_STATUS_FAILED,
            attempts=CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS,
            scheduled_at=retry_before,
            updated_at=retry_before,
            last_error="DeepSeek returned invalid JSON",
        )

        stats = process_due_translation_tasks(limit=1)

        self.assertEqual(stats["processed"], 0)
        task.refresh_from_db()
        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_FAILED)
        self.assertEqual(task.attempts, CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS)
        translate_mock.assert_not_called()

    @patch("feeds.translation_service.translate_post_to_language")
    def test_process_due_translation_tasks_skips_exhausted_pending_task(
        self,
        translate_mock,
    ) -> None:
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )
        ContentTranslationTask.objects.filter(pk=task.pk).update(
            status=CONTENT_TRANSLATION_TASK_STATUS_PENDING,
            attempts=CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS,
            scheduled_at=timezone.now() - timedelta(minutes=1),
        )

        stats = process_due_translation_tasks(limit=1)

        self.assertEqual(stats["processed"], 0)
        task.refresh_from_db()
        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_PENDING)
        self.assertEqual(task.attempts, CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS)
        translate_mock.assert_not_called()

    def test_reconcile_only_resets_exhausted_task_when_explicitly_requested(self) -> None:
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )
        ContentTranslationTask.objects.filter(pk=task.pk).update(
            status=CONTENT_TRANSLATION_TASK_STATUS_FAILED,
            attempts=CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS,
            source_updated_at=self.post.updated_at,
            last_error="DeepSeek returned invalid JSON",
        )

        call_command("queue_missing_post_translation_tasks", limit=1)
        task.refresh_from_db()
        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_FAILED)
        self.assertEqual(task.attempts, CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS)

        task.status = CONTENT_TRANSLATION_TASK_STATUS_PENDING
        task.save(update_fields=["status", "updated_at"])
        call_command(
            "queue_missing_post_translation_tasks",
            limit=1,
            reset_exhausted=True,
        )
        task.refresh_from_db()
        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_PENDING)
        self.assertEqual(task.attempts, 0)

    @patch("feeds.translation_service.translate_post_to_language")
    def test_disabled_auto_translation_reschedules_without_openrouter(self, translate_mock) -> None:
        ContentTranslationSettings.objects.update_or_create(
            pk=1,
            defaults={
                "enabled": False,
                "post_daily_limit": 200,
                "comment_daily_limit": 1000,
                "post_object_daily_limit": 3,
            },
        )
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )
        task.scheduled_at = timezone.now() - timedelta(minutes=1)
        task.save(update_fields=["scheduled_at"])

        result = process_translation_task(task.pk)

        self.assertEqual(result, "skipped")
        task.refresh_from_db()
        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_PENDING)
        self.assertIn("выключен", task.last_error)
        self.assertFalse(ContentTranslationRun.objects.exists())
        translate_mock.assert_not_called()

    @patch("feeds.translation_service.translate_post_to_language")
    def test_post_daily_translation_limit_reschedules_task(self, translate_mock) -> None:
        ContentTranslationSettings.objects.update_or_create(
            pk=1,
            defaults={
                "enabled": True,
                "post_daily_limit": 1,
                "comment_daily_limit": 1000,
                "post_object_daily_limit": 3,
            },
        )
        ContentTranslationRun.objects.create(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=999999,
        )
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )
        task.scheduled_at = timezone.now() - timedelta(minutes=1)
        task.save(update_fields=["scheduled_at"])

        result = process_translation_task(task.pk)

        self.assertEqual(result, "skipped")
        task.refresh_from_db()
        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_PENDING)
        self.assertIn("Дневной лимит", task.last_error)
        self.assertEqual(
            ContentTranslationRun.objects.filter(object_id=self.post.pk).count(),
            0,
        )
        translate_mock.assert_not_called()

    @patch("feeds.translation_service.translate_post_to_language")
    def test_one_post_translation_limit_uses_rolling_24_hours(self, translate_mock) -> None:
        ContentTranslationSettings.objects.update_or_create(
            pk=1,
            defaults={
                "enabled": True,
                "post_daily_limit": 200,
                "comment_daily_limit": 1000,
                "post_object_daily_limit": 3,
            },
        )
        for _ in range(3):
            ContentTranslationRun.objects.create(
                kind=CONTENT_TRANSLATION_KIND_POST,
                object_id=self.post.pk,
            )
        task = ContentTranslationTask.objects.get(
            kind=CONTENT_TRANSLATION_KIND_POST,
            object_id=self.post.pk,
        )
        task.scheduled_at = timezone.now() - timedelta(minutes=1)
        task.save(update_fields=["scheduled_at"])

        result = process_translation_task(task.pk)

        self.assertEqual(result, "skipped")
        task.refresh_from_db()
        self.assertEqual(task.status, CONTENT_TRANSLATION_TASK_STATUS_PENDING)
        self.assertIn("24 часа", task.last_error)
        self.assertEqual(
            ContentTranslationRun.objects.filter(object_id=self.post.pk).count(),
            3,
        )
        translate_mock.assert_not_called()
