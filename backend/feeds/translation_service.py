from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import timedelta
from typing import Any

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from feeds.models import (
    CONTENT_TRANSLATION_KIND_COMMENT,
    CONTENT_TRANSLATION_KIND_COMUN,
    CONTENT_TRANSLATION_KIND_POST,
    CONTENT_TRANSLATION_TASK_STATUS_DONE,
    CONTENT_TRANSLATION_TASK_STATUS_FAILED,
    CONTENT_TRANSLATION_TASK_STATUS_PENDING,
    CONTENT_TRANSLATION_TASK_STATUS_RUNNING,
    CONTENT_TRANSLATION_TASK_STATUS_SKIPPED,
    POST_TRANSLATION_LANGUAGE_CHOICES,
    POST_TRANSLATION_LANGUAGE_ENGLISH,
    POST_TRANSLATION_LANGUAGE_FRENCH,
    POST_TRANSLATION_LANGUAGE_GERMAN,
    POST_TRANSLATION_LANGUAGE_INDONESIAN,
    POST_TRANSLATION_LANGUAGE_PORTUGUESE,
    POST_TRANSLATION_LANGUAGE_SPANISH,
    POST_TRANSLATION_LANGUAGE_TURKISH,
    POST_TRANSLATION_STATUS_FAILED,
    POST_TRANSLATION_STATUS_PENDING,
    POST_TRANSLATION_STATUS_TRANSLATED,
    Comun,
    ComunTranslation,
    ContentTranslationRun,
    ContentTranslationSettings,
    ContentTranslationTask,
    Post,
    PostComment,
    PostCommentTranslation,
    PostTranslation,
)
from feeds.preview import build_post_preview


class PostTranslationError(Exception):
    pass


class AutoTranslationSkipped(PostTranslationError):
    pass


class AutoTranslationRescheduled(PostTranslationError):
    pass


SUPPORTED_TRANSLATION_LANGUAGES = {
    POST_TRANSLATION_LANGUAGE_ENGLISH: {
        "label": "Английский",
        "target": "English",
        "locale": "en",
    },
    POST_TRANSLATION_LANGUAGE_SPANISH: {
        "label": "Испанский",
        "target": "Spanish",
        "locale": "es",
    },
    POST_TRANSLATION_LANGUAGE_PORTUGUESE: {
        "label": "Португальский",
        "target": "Portuguese",
        "locale": "pt",
    },
    POST_TRANSLATION_LANGUAGE_GERMAN: {
        "label": "Немецкий",
        "target": "German",
        "locale": "de",
    },
    POST_TRANSLATION_LANGUAGE_FRENCH: {
        "label": "Французский",
        "target": "French",
        "locale": "fr",
    },
    POST_TRANSLATION_LANGUAGE_TURKISH: {
        "label": "Турецкий",
        "target": "Turkish",
        "locale": "tr",
    },
    POST_TRANSLATION_LANGUAGE_INDONESIAN: {
        "label": "Индонезийский",
        "target": "Indonesian",
        "locale": "id",
    },
}

AUTO_TRANSLATION_DELAYS = {
    CONTENT_TRANSLATION_KIND_POST: timedelta(minutes=10),
    CONTENT_TRANSLATION_KIND_COMMENT: timedelta(minutes=1),
    CONTENT_TRANSLATION_KIND_COMUN: timedelta(minutes=5),
}

TRANSLATION_DISABLED_RETRY_DELAY = timedelta(minutes=15)
POST_TRANSLATION_TITLE_MAX_LENGTH = 255
CONTENT_TRANSLATION_TASK_STALE_AFTER = timedelta(minutes=12)


def get_translation_language_label(language: str) -> str:
    return dict(POST_TRANSLATION_LANGUAGE_CHOICES).get(language, language)


def _truncate_translation_title(value: str) -> str:
    title = str(value or "").strip()
    if len(title) <= POST_TRANSLATION_TITLE_MAX_LENGTH:
        return title
    return title[:POST_TRANSLATION_TITLE_MAX_LENGTH].rstrip()


def get_content_translation_settings() -> ContentTranslationSettings:
    settings_obj, _created = ContentTranslationSettings.objects.get_or_create(pk=1)
    return settings_obj


def _current_day_start(now=None):
    localized = timezone.localtime(now or timezone.now())
    return localized.replace(hour=0, minute=0, second=0, microsecond=0)


def _next_day_start(now=None):
    return _current_day_start(now) + timedelta(days=1)


def content_translation_usage(now=None) -> dict[str, int | str]:
    day_start = _current_day_start(now)
    post_used = ContentTranslationRun.objects.filter(
        kind=CONTENT_TRANSLATION_KIND_POST,
        created_at__gte=day_start,
    ).count()
    comment_used = ContentTranslationRun.objects.filter(
        kind=CONTENT_TRANSLATION_KIND_COMMENT,
        created_at__gte=day_start,
    ).count()
    comun_used = ContentTranslationRun.objects.filter(
        kind=CONTENT_TRANSLATION_KIND_COMUN,
        created_at__gte=day_start,
    ).count()
    return {
        "day_start": day_start.isoformat(),
        "post_used": post_used,
        "comment_used": comment_used,
        "comun_used": comun_used,
    }


def serialize_content_translation_settings(
    settings_obj: ContentTranslationSettings | None = None,
) -> dict:
    settings_obj = settings_obj or get_content_translation_settings()
    usage = content_translation_usage()
    post_limit = int(settings_obj.post_daily_limit or 0)
    comment_limit = int(settings_obj.comment_daily_limit or 0)
    return {
        "enabled": bool(settings_obj.enabled),
        "post_daily_limit": post_limit,
        "comment_daily_limit": comment_limit,
        "post_object_daily_limit": int(settings_obj.post_object_daily_limit or 0),
        "updated_at": settings_obj.updated_at.isoformat() if settings_obj.updated_at else None,
        "usage": {
            **usage,
            "post_remaining": max(post_limit - int(usage["post_used"]), 0),
            "comment_remaining": max(comment_limit - int(usage["comment_used"]), 0),
        },
    }


def update_content_translation_settings(payload: dict) -> ContentTranslationSettings:
    settings_obj = get_content_translation_settings()

    if "enabled" in payload:
        settings_obj.enabled = bool(payload.get("enabled"))

    integer_fields = {
        "post_daily_limit": 200,
        "comment_daily_limit": 1000,
        "post_object_daily_limit": 3,
    }
    for field, default in integer_fields.items():
        if field not in payload:
            continue
        try:
            value = int(payload.get(field, default))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} must be an integer") from exc
        if value < 0:
            raise ValueError(f"{field} must be greater than or equal to 0")
        if value > 1_000_000:
            raise ValueError(f"{field} is too large")
        setattr(settings_obj, field, value)

    settings_obj.save(
        update_fields=[
            "enabled",
            "post_daily_limit",
            "comment_daily_limit",
            "post_object_daily_limit",
            "updated_at",
        ]
    )
    return settings_obj


def translate_post_to_language(post: Post, language: str) -> PostTranslation:
    language = str(language or "").strip().lower()
    target = SUPPORTED_TRANSLATION_LANGUAGES.get(language)
    if target is None:
        raise PostTranslationError(f"Язык перевода не поддерживается: {language}")

    translation, _ = PostTranslation.objects.get_or_create(post=post, language=language)
    model = str(getattr(settings, "OPENROUTER_TRANSLATION_MODEL", "") or "").strip()
    translation.status = POST_TRANSLATION_STATUS_PENDING
    translation.model = model
    translation.error_message = ""
    translation.save(update_fields=["status", "model", "error_message", "updated_at"])

    try:
        response_payload = _request_openrouter_translation(post, target)
        translated_payload = _parse_translated_payload(response_payload)
        translated_title = _truncate_translation_title(translated_payload.get("title", ""))
        translated_content = str(translated_payload.get("content", "") or "").strip()
        if (post.title or "").strip() and not translated_title:
            raise PostTranslationError("OpenRouter вернул пустой заголовок")
        if (post.content or "").strip() and not translated_content:
            raise PostTranslationError("OpenRouter вернул пустой текст поста")

        preview = build_post_preview(translated_content, post.raw_data)
        translation.title = translated_title
        translation.content = translated_content
        translation.preview_content = preview["preview_content"]
        translation.status = POST_TRANSLATION_STATUS_TRANSLATED
        translation.error_message = ""
        translation.raw_response = response_payload
        translation.model = model
        translation.save(
            update_fields=[
                "title",
                "content",
                "preview_content",
                "status",
                "error_message",
                "raw_response",
                "model",
                "updated_at",
            ]
        )
    except Exception as exc:
        message = str(exc)[:2000]
        translation.status = POST_TRANSLATION_STATUS_FAILED
        translation.error_message = message
        translation.save(update_fields=["status", "error_message", "updated_at"])
        if isinstance(exc, PostTranslationError):
            raise
        raise PostTranslationError(message) from exc

    return translation


def translate_post_to_all_languages(post: Post) -> list[PostTranslation]:
    return [
        translate_post_to_language(post, language)
        for language in SUPPORTED_TRANSLATION_LANGUAGES
    ]


def translate_comment_to_language(comment: PostComment, language: str) -> PostCommentTranslation:
    language = str(language or "").strip().lower()
    target = SUPPORTED_TRANSLATION_LANGUAGES.get(language)
    if target is None:
        raise PostTranslationError(f"Язык перевода не поддерживается: {language}")
    if comment.is_deleted or not (comment.body or "").strip():
        raise AutoTranslationSkipped("Комментарий удален или пуст")

    translation, _ = PostCommentTranslation.objects.get_or_create(
        comment=comment,
        language=language,
    )
    model = str(getattr(settings, "OPENROUTER_TRANSLATION_MODEL", "") or "").strip()
    translation.status = POST_TRANSLATION_STATUS_PENDING
    translation.model = model
    translation.error_message = ""
    translation.save(update_fields=["status", "model", "error_message", "updated_at"])

    try:
        response_payload = _request_openrouter_json_translation(
            {
                "source_language": "Russian",
                "target_language": target["target"],
                "target_locale": target["locale"],
                "comment": {"body": comment.body or ""},
            },
            system_prompt=(
                "You are a professional localization editor. Translate Tambur comments from Russian. "
                "Return only valid JSON with key body. Preserve markdown, URLs, media URLs, code blocks, "
                "emoji, mentions, and placeholders. Translate only human-readable Russian text. "
                "Do not add commentary."
            ),
        )
        translated_payload = _parse_translated_payload(response_payload, keys=("body",))
        translated_body = str(translated_payload.get("body", "") or "").strip()
        if (comment.body or "").strip() and not translated_body:
            raise PostTranslationError("OpenRouter вернул пустой комментарий")

        translation.body = translated_body
        translation.status = POST_TRANSLATION_STATUS_TRANSLATED
        translation.error_message = ""
        translation.raw_response = response_payload
        translation.model = model
        translation.save(
            update_fields=[
                "body",
                "status",
                "error_message",
                "raw_response",
                "model",
                "updated_at",
            ]
        )
    except Exception as exc:
        message = str(exc)[:2000]
        translation.status = POST_TRANSLATION_STATUS_FAILED
        translation.error_message = message
        translation.save(update_fields=["status", "error_message", "updated_at"])
        if isinstance(exc, PostTranslationError):
            raise
        raise PostTranslationError(message) from exc

    return translation


def translate_comun_to_language(comun: Comun, language: str) -> ComunTranslation:
    language = str(language or "").strip().lower()
    target = SUPPORTED_TRANSLATION_LANGUAGES.get(language)
    if target is None:
        raise PostTranslationError(f"Язык перевода не поддерживается: {language}")
    if _comun_has_negative_rating(comun):
        raise AutoTranslationSkipped("Сообщество имеет отрицательный рейтинг")
    if not (comun.product_description or "").strip() and not (comun.rules_text or "").strip():
        raise AutoTranslationSkipped("Описание и правила сообщества пустые")

    translation, _ = ComunTranslation.objects.get_or_create(comun=comun, language=language)
    model = str(getattr(settings, "OPENROUTER_TRANSLATION_MODEL", "") or "").strip()
    translation.status = POST_TRANSLATION_STATUS_PENDING
    translation.model = model
    translation.error_message = ""
    translation.save(update_fields=["status", "model", "error_message", "updated_at"])

    try:
        response_payload = _request_openrouter_json_translation(
            {
                "source_language": "Russian",
                "target_language": target["target"],
                "target_locale": target["locale"],
                "community": {
                    "product_description": comun.product_description or "",
                    "rules_text": comun.rules_text or "",
                },
            },
            system_prompt=(
                "You are a professional localization editor. Translate Tambur community profile text "
                "from Russian. Return only valid JSON with keys product_description and rules_text. "
                "Preserve markdown, lists, URLs, code blocks, placeholders, and formatting. Translate "
                "only human-readable Russian text. Do not add commentary."
            ),
        )
        translated_payload = _parse_translated_payload(
            response_payload,
            keys=("product_description", "rules_text"),
        )
        translated_description = str(translated_payload.get("product_description", "") or "").strip()
        translated_rules = str(translated_payload.get("rules_text", "") or "").strip()
        if (comun.product_description or "").strip() and not translated_description:
            raise PostTranslationError("OpenRouter вернул пустое описание сообщества")
        if (comun.rules_text or "").strip() and not translated_rules:
            raise PostTranslationError("OpenRouter вернул пустые правила сообщества")

        translation.product_description = translated_description
        translation.rules_text = translated_rules
        translation.status = POST_TRANSLATION_STATUS_TRANSLATED
        translation.error_message = ""
        translation.raw_response = response_payload
        translation.model = model
        translation.save(
            update_fields=[
                "product_description",
                "rules_text",
                "status",
                "error_message",
                "raw_response",
                "model",
                "updated_at",
            ]
        )
    except Exception as exc:
        message = str(exc)[:2000]
        translation.status = POST_TRANSLATION_STATUS_FAILED
        translation.error_message = message
        translation.save(update_fields=["status", "error_message", "updated_at"])
        if isinstance(exc, PostTranslationError):
            raise
        raise PostTranslationError(message) from exc

    return translation


def queue_post_translation(post: Post, languages: list[str]) -> list[PostTranslation]:
    normalized_languages = _normalize_translation_languages(languages)
    if not normalized_languages:
        return []

    model = str(getattr(settings, "OPENROUTER_TRANSLATION_MODEL", "") or "").strip()
    translations: list[PostTranslation] = []
    for language in normalized_languages:
        translation, _ = PostTranslation.objects.get_or_create(
            post=post,
            language=language,
        )
        translation.status = POST_TRANSLATION_STATUS_PENDING
        translation.model = model
        translation.error_message = ""
        translation.save(
            update_fields=["status", "model", "error_message", "updated_at"]
        )
        translations.append(translation)

    _start_post_translation_process(post.pk, tuple(normalized_languages))
    return translations


def schedule_post_auto_translation(post: Post) -> ContentTranslationTask | None:
    if not _post_is_translatable(post):
        _delete_auto_translation_task(CONTENT_TRANSLATION_KIND_POST, post.pk)
        return None
    return _schedule_auto_translation_task(
        CONTENT_TRANSLATION_KIND_POST,
        post.pk,
        source_updated_at=post.updated_at,
        scheduled_at=_scheduled_at_for(post, CONTENT_TRANSLATION_KIND_POST),
    )


def schedule_comment_auto_translation(comment: PostComment) -> ContentTranslationTask | None:
    if not _comment_is_translatable(comment):
        _delete_auto_translation_task(CONTENT_TRANSLATION_KIND_COMMENT, comment.pk)
        return None
    return _schedule_auto_translation_task(
        CONTENT_TRANSLATION_KIND_COMMENT,
        comment.pk,
        source_updated_at=comment.updated_at,
        scheduled_at=(comment.updated_at or timezone.now()) + AUTO_TRANSLATION_DELAYS[CONTENT_TRANSLATION_KIND_COMMENT],
    )


def schedule_comun_auto_translation(comun: Comun) -> ContentTranslationTask | None:
    if not _comun_is_translatable(comun):
        _delete_auto_translation_task(CONTENT_TRANSLATION_KIND_COMUN, comun.pk)
        return None
    return _schedule_auto_translation_task(
        CONTENT_TRANSLATION_KIND_COMUN,
        comun.pk,
        source_updated_at=comun.updated_at if hasattr(comun, "updated_at") else timezone.now(),
        scheduled_at=timezone.now() + AUTO_TRANSLATION_DELAYS[CONTENT_TRANSLATION_KIND_COMUN],
    )


def process_due_translation_tasks(*, limit: int = 20) -> dict[str, int]:
    stats = {"processed": 0, "done": 0, "failed": 0, "skipped": 0}
    now = timezone.now()
    _reset_stale_running_translation_tasks(now)
    task_ids = list(
        ContentTranslationTask.objects.filter(
            status=CONTENT_TRANSLATION_TASK_STATUS_PENDING,
            scheduled_at__lte=now,
        )
        .order_by("scheduled_at", "id")
        .values_list("id", flat=True)[:limit]
    )
    for task_id in task_ids:
        result = process_translation_task(task_id)
        stats["processed"] += 1
        stats[result] = stats.get(result, 0) + 1
    return stats


def process_translation_task(task_id: int) -> str:
    with transaction.atomic():
        try:
            task = ContentTranslationTask.objects.select_for_update().get(pk=task_id)
        except ContentTranslationTask.DoesNotExist:
            return "skipped"
        if task.status != CONTENT_TRANSLATION_TASK_STATUS_PENDING:
            return "skipped"
        if task.scheduled_at > timezone.now():
            return "skipped"
        task.status = CONTENT_TRANSLATION_TASK_STATUS_RUNNING
        task.locked_at = timezone.now()
        task.attempts = int(task.attempts or 0) + 1
        task.last_error = ""
        task.save(update_fields=["status", "locked_at", "attempts", "last_error", "updated_at"])

    try:
        _process_translation_task_payload(task)
    except AutoTranslationRescheduled:
        return "skipped"
    except AutoTranslationSkipped as exc:
        return _finish_translation_task(
            task,
            CONTENT_TRANSLATION_TASK_STATUS_SKIPPED,
            last_error=str(exc)[:2000],
            result="skipped",
        )
    except Exception as exc:
        return _finish_translation_task(
            task,
            CONTENT_TRANSLATION_TASK_STATUS_FAILED,
            last_error=str(exc)[:2000],
            result="failed",
        )

    return _finish_translation_task(
        task,
        CONTENT_TRANSLATION_TASK_STATUS_DONE,
        last_error="",
        result="done",
    )


def _reset_stale_running_translation_tasks(now) -> int:
    stale_before = now - CONTENT_TRANSLATION_TASK_STALE_AFTER
    return ContentTranslationTask.objects.filter(
        status=CONTENT_TRANSLATION_TASK_STATUS_RUNNING,
        locked_at__lt=stale_before,
    ).update(
        status=CONTENT_TRANSLATION_TASK_STATUS_PENDING,
        locked_at=None,
        last_error="Задача возвращена в очередь после таймаута обработчика",
        updated_at=now,
    )


def _normalize_translation_languages(languages: list[str]) -> list[str]:
    normalized: list[str] = []
    for language in languages:
        code = str(language or "").strip().lower()
        if code not in SUPPORTED_TRANSLATION_LANGUAGES:
            raise PostTranslationError(f"Язык перевода не поддерживается: {code}")
        if code not in normalized:
            normalized.append(code)
    return normalized


def _start_post_translation_process(post_id: int, languages: tuple[str, ...]) -> None:
    manage_py = settings.BASE_DIR / "manage.py"
    command = [sys.executable, str(manage_py), "translate_post", str(post_id)]
    for language in languages:
        command.extend(["--language", language])
    try:
        subprocess.Popen(
            command,
            cwd=str(settings.BASE_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise PostTranslationError(f"Не удалось запустить фоновый перевод: {exc}") from exc


def _schedule_auto_translation_task(
    kind: str,
    object_id: int,
    *,
    source_updated_at,
    scheduled_at,
) -> ContentTranslationTask:
    task, _created = ContentTranslationTask.objects.update_or_create(
        kind=kind,
        object_id=object_id,
        defaults={
            "status": CONTENT_TRANSLATION_TASK_STATUS_PENDING,
            "scheduled_at": scheduled_at,
            "source_updated_at": source_updated_at,
            "last_error": "",
            "locked_at": None,
        },
    )
    return task


def _delete_auto_translation_task(kind: str, object_id: int | None) -> None:
    if not object_id:
        return
    ContentTranslationTask.objects.filter(kind=kind, object_id=object_id).delete()


def _finish_translation_task(
    task: ContentTranslationTask,
    status: str,
    *,
    last_error: str,
    result: str,
) -> str:
    updated = ContentTranslationTask.objects.filter(
        pk=task.pk,
        status=CONTENT_TRANSLATION_TASK_STATUS_RUNNING,
        source_updated_at=task.source_updated_at,
    ).update(
        status=status,
        last_error=last_error,
        locked_at=None,
        updated_at=timezone.now(),
    )
    return result if updated else "skipped"


def _reschedule_translation_task(task: ContentTranslationTask, *, scheduled_at, reason: str) -> None:
    task.status = CONTENT_TRANSLATION_TASK_STATUS_PENDING
    task.scheduled_at = scheduled_at
    task.locked_at = None
    task.last_error = reason[:2000]
    task.save(update_fields=["status", "scheduled_at", "locked_at", "last_error", "updated_at"])


def _translation_budget_reschedule(task: ContentTranslationTask) -> tuple[object, str] | None:
    now = timezone.now()
    day_start = _current_day_start(now)
    next_day = _next_day_start(now)
    object_window_start = now - timedelta(days=1)

    with transaction.atomic():
        settings_obj = get_content_translation_settings()
        settings_obj = ContentTranslationSettings.objects.select_for_update().get(
            pk=settings_obj.pk
        )
        if not settings_obj.enabled:
            return (
                now + TRANSLATION_DISABLED_RETRY_DELAY,
                "Автоматический перевод выключен в модераторской",
            )

        if task.kind == CONTENT_TRANSLATION_KIND_POST:
            post_limit = int(settings_obj.post_daily_limit or 0)
            per_post_limit = int(settings_obj.post_object_daily_limit or 0)
            post_used = ContentTranslationRun.objects.filter(
                kind=CONTENT_TRANSLATION_KIND_POST,
                created_at__gte=day_start,
            ).count()
            if post_used >= post_limit:
                return (next_day, "Дневной лимит перевода статей исчерпан")

            object_runs = ContentTranslationRun.objects.filter(
                kind=CONTENT_TRANSLATION_KIND_POST,
                object_id=task.object_id,
                created_at__gte=object_window_start,
            )
            object_used = object_runs.count()
            if object_used >= per_post_limit:
                oldest_run = object_runs.order_by("created_at").first()
                scheduled_at = (
                    oldest_run.created_at + timedelta(days=1)
                    if oldest_run
                    else now + TRANSLATION_DISABLED_RETRY_DELAY
                )
                return (
                    scheduled_at,
                    "Лимит переводов этой статьи за 24 часа исчерпан",
                )

        if task.kind == CONTENT_TRANSLATION_KIND_COMMENT:
            comment_limit = int(settings_obj.comment_daily_limit or 0)
            comment_used = ContentTranslationRun.objects.filter(
                kind=CONTENT_TRANSLATION_KIND_COMMENT,
                created_at__gte=day_start,
            ).count()
            if comment_used >= comment_limit:
                return (next_day, "Дневной лимит перевода комментариев исчерпан")

        ContentTranslationRun.objects.create(
            kind=task.kind,
            object_id=task.object_id,
            task=task,
        )
    return None


def _reserve_translation_budget(task: ContentTranslationTask) -> None:
    reschedule = _translation_budget_reschedule(task)
    if reschedule is None:
        return
    scheduled_at, reason = reschedule
    _reschedule_translation_task(task, scheduled_at=scheduled_at, reason=reason)
    raise AutoTranslationRescheduled(reason)


def _scheduled_at_for(post: Post, kind: str):
    base = post.updated_at or timezone.now()
    if post.publish_at and post.publish_at > base:
        base = post.publish_at
    return base + AUTO_TRANSLATION_DELAYS[kind]


def _post_is_translatable(post: Post) -> bool:
    if not post.pk or post.is_blocked or post.is_pending:
        return False
    if post.publish_at and post.publish_at > timezone.now():
        return True
    if not (post.title or "").strip() and not (post.content or "").strip():
        return False
    return not _post_has_negative_comun_rating(post)


def _comment_is_translatable(comment: PostComment) -> bool:
    if not comment.pk or comment.is_deleted or not (comment.body or "").strip():
        return False
    post = getattr(comment, "post", None)
    if post is None:
        post = Post.objects.filter(pk=comment.post_id).select_related("author").first()
    return bool(post and _post_is_translatable(post))


def _comun_is_translatable(comun: Comun) -> bool:
    if not comun.pk or not comun.is_active or _comun_has_negative_rating(comun):
        return False
    return bool((comun.product_description or "").strip() or (comun.rules_text or "").strip())


def _comun_has_negative_rating(comun: Comun | None) -> bool:
    if not comun:
        return False
    try:
        return comun.rating_score < 0
    except TypeError:
        return False


def _post_has_negative_comun_rating(post: Post) -> bool:
    try:
        from communities import service as community_service

        comun_ids = community_service._candidate_comun_ids_for_post(post)
        if not comun_ids:
            return False
        return Comun.objects.filter(id__in=comun_ids, rating_score__lt=0).exists()
    except Exception:
        return False


def _process_translation_task_payload(task: ContentTranslationTask) -> None:
    if task.kind == CONTENT_TRANSLATION_KIND_POST:
        post = Post.objects.select_related("author").filter(pk=task.object_id).first()
        if not post or not _post_is_translatable(post):
            raise AutoTranslationSkipped("Пост недоступен для перевода")
        _raise_if_task_is_stale(task, post.updated_at)
        _reserve_translation_budget(task)
        for language in SUPPORTED_TRANSLATION_LANGUAGES:
            if _post_translation_is_current(post, language):
                continue
            translate_post_to_language(post, language)
        return

    if task.kind == CONTENT_TRANSLATION_KIND_COMMENT:
        comment = (
            PostComment.objects.select_related("post", "post__author")
            .filter(pk=task.object_id)
            .first()
        )
        if not comment or not _comment_is_translatable(comment):
            raise AutoTranslationSkipped("Комментарий недоступен для перевода")
        _raise_if_task_is_stale(task, comment.updated_at)
        _reserve_translation_budget(task)
        for language in SUPPORTED_TRANSLATION_LANGUAGES:
            if _comment_translation_is_current(comment, language):
                continue
            translate_comment_to_language(comment, language)
        return

    if task.kind == CONTENT_TRANSLATION_KIND_COMUN:
        comun = Comun.objects.filter(pk=task.object_id).first()
        if not comun or not _comun_is_translatable(comun):
            raise AutoTranslationSkipped("Сообщество недоступно для перевода")
        _raise_if_task_is_stale(task, comun.updated_at)
        _reserve_translation_budget(task)
        for language in SUPPORTED_TRANSLATION_LANGUAGES:
            if _comun_translation_is_current(comun, language):
                continue
            translate_comun_to_language(comun, language)
        return

    raise AutoTranslationSkipped(f"Неизвестный тип задачи: {task.kind}")


def _translation_updated_after_source(translation, source_updated_at) -> bool:
    return not source_updated_at or translation.updated_at >= source_updated_at


def _post_translation_is_current(post: Post, language: str) -> bool:
    translation = PostTranslation.objects.filter(post=post, language=language).first()
    if not translation or translation.status != POST_TRANSLATION_STATUS_TRANSLATED:
        return False
    if (post.title or "").strip() and not (translation.title or "").strip():
        return False
    if (post.content or "").strip() and not (translation.content or "").strip():
        return False
    return _translation_updated_after_source(translation, post.updated_at)


def _comment_translation_is_current(comment: PostComment, language: str) -> bool:
    translation = PostCommentTranslation.objects.filter(comment=comment, language=language).first()
    if not translation or translation.status != POST_TRANSLATION_STATUS_TRANSLATED:
        return False
    if (comment.body or "").strip() and not (translation.body or "").strip():
        return False
    return _translation_updated_after_source(translation, comment.updated_at)


def _comun_translation_is_current(comun: Comun, language: str) -> bool:
    translation = ComunTranslation.objects.filter(comun=comun, language=language).first()
    if not translation or translation.status != POST_TRANSLATION_STATUS_TRANSLATED:
        return False
    if (comun.product_description or "").strip() and not (
        translation.product_description or ""
    ).strip():
        return False
    if (comun.rules_text or "").strip() and not (translation.rules_text or "").strip():
        return False
    return _translation_updated_after_source(translation, comun.updated_at)


def _raise_if_task_is_stale(task: ContentTranslationTask, source_updated_at) -> None:
    if task.source_updated_at and source_updated_at and source_updated_at > task.source_updated_at:
        delay = AUTO_TRANSLATION_DELAYS.get(task.kind, timedelta(minutes=5))
        task.status = CONTENT_TRANSLATION_TASK_STATUS_PENDING
        task.scheduled_at = source_updated_at + delay
        task.source_updated_at = source_updated_at
        task.locked_at = None
        task.save(update_fields=["status", "scheduled_at", "source_updated_at", "locked_at", "updated_at"])
        raise AutoTranslationRescheduled("Контент был обновлен, задача перенесена")


def _request_openrouter_translation(post: Post, target: dict[str, str]) -> dict[str, Any]:
    return _request_openrouter_json_translation(
        {
            "source_language": "Russian",
            "target_language": target["target"],
            "target_locale": target["locale"],
            "post": {
                "title": post.title or "",
                "content": post.content or "",
            },
        },
        system_prompt=(
            "You are a professional localization editor. Translate Tambur posts from Russian. "
            "Return only valid JSON with keys title and content. Preserve HTML tags, markdown, "
            "EditorJS JSON structure, URLs, media URLs, embeds, code blocks, and placeholders. "
            "Translate only human-readable Russian text. Do not add commentary."
        ),
    )


def _request_openrouter_json_translation(
    user_payload: dict[str, Any],
    *,
    system_prompt: str,
) -> dict[str, Any]:
    api_key = str(getattr(settings, "OPENROUTER_API_KEY", "") or "").strip()
    if not api_key:
        raise PostTranslationError("OPENROUTER_API_KEY не задан в окружении backend")

    api_url = str(getattr(settings, "OPENROUTER_API_URL", "") or "").strip()
    model = str(getattr(settings, "OPENROUTER_TRANSLATION_MODEL", "") or "").strip()
    if not api_url:
        raise PostTranslationError("OPENROUTER_API_URL не задан")
    if not model:
        raise PostTranslationError("OPENROUTER_TRANSLATION_MODEL не задан")

    site_base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip()
    app_title = str(getattr(settings, "OPENROUTER_APP_TITLE", "") or "Tambur").strip()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": app_title,
        "X-OpenRouter-Title": app_title,
    }
    if site_base_url:
        headers["HTTP-Referer"] = site_base_url

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=90)
    except requests.RequestException as exc:
        raise PostTranslationError(f"Ошибка запроса OpenRouter: {exc}") from exc

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise PostTranslationError(f"OpenRouter вернул не JSON, HTTP {response.status_code}") from exc

    if response.status_code >= 400:
        raise PostTranslationError(_extract_openrouter_error(response_payload, response.status_code))

    return response_payload


def _extract_openrouter_error(response_payload: dict[str, Any], status_code: int) -> str:
    error = response_payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "").strip()
        if message:
            return f"OpenRouter HTTP {status_code}: {message[:1000]}"
    return f"OpenRouter HTTP {status_code}"


def _parse_translated_payload(
    response_payload: dict[str, Any],
    *,
    keys: tuple[str, ...] = ("title", "content"),
) -> dict[str, str]:
    try:
        message = response_payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PostTranslationError("OpenRouter вернул ответ без choices[0].message") from exc

    content = _normalize_openrouter_content(message.get("content"))
    if not content.strip():
        raise PostTranslationError("OpenRouter вернул пустой content")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        payload = json.loads(_extract_json_object(content))

    if not isinstance(payload, dict):
        raise PostTranslationError("OpenRouter вернул не JSON-объект")
    return {key: str(payload.get(key, "") or "") for key in keys}


def _normalize_openrouter_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "") or ""))
            elif item is not None:
                parts.append(str(item))
        return "".join(parts)
    if content is None:
        return ""
    return str(content)


def _extract_json_object(value: str) -> str:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", value, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = value.find("{")
    end = value.rfind("}")
    if start >= 0 and end > start:
        return value[start : end + 1]
    raise PostTranslationError("OpenRouter вернул content не в формате JSON")
