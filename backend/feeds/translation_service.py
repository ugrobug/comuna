from __future__ import annotations

import base64
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
from communities.models import ComunCategory, ComunGlossaryTerm

from feeds.models import (
    CONTENT_TRANSLATION_KIND_COMMENT,
    CONTENT_TRANSLATION_KIND_COMUN,
    CONTENT_TRANSLATION_KIND_POST,
    CONTENT_TRANSLATION_KIND_STATIC_PAGE,
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
    StaticPageContent,
    StaticPageTranslation,
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
    CONTENT_TRANSLATION_KIND_STATIC_PAGE: timedelta(minutes=5),
}

TRANSLATION_DISABLED_RETRY_DELAY = timedelta(minutes=15)
POST_TRANSLATION_TITLE_MAX_LENGTH = 255
COMUN_TRANSLATION_NAME_MAX_LENGTH = 160
STATIC_PAGE_TRANSLATION_TITLE_MAX_LENGTH = 160
CONTENT_TRANSLATION_TASK_STALE_AFTER = timedelta(minutes=12)
CONTENT_TRANSLATION_TASK_FAILED_RETRY_AFTER = timedelta(minutes=15)
CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS = 10
TRANSLATION_PROVIDER_DEEPSEEK = "deepseek"
TRANSLATION_PROVIDER_OPENROUTER = "openrouter"
POST_CONTENT_FORMAT_TEXT = "text"
POST_CONTENT_FORMAT_EDITORJS_JSON = "editorjs_json"
POST_CONTENT_FORMAT_EDITORJS_BASE64 = "editorjs_base64"


def get_translation_language_label(language: str) -> str:
    return dict(POST_TRANSLATION_LANGUAGE_CHOICES).get(language, language)


def _translation_provider() -> str:
    provider = str(getattr(settings, "CONTENT_TRANSLATION_PROVIDER", "") or "").strip().lower()
    return provider or TRANSLATION_PROVIDER_OPENROUTER


def _translation_model() -> str:
    provider = _translation_provider()
    if provider == TRANSLATION_PROVIDER_DEEPSEEK:
        model = str(getattr(settings, "DEEPSEEK_TRANSLATION_MODEL", "") or "").strip()
        if not model:
            model = str(getattr(settings, "CONTENT_TRANSLATION_MODEL", "") or "").strip()
        if model.startswith("deepseek/"):
            model = model.split("/", 1)[1]
        return model or "deepseek-v4-flash"

    model = str(getattr(settings, "CONTENT_TRANSLATION_MODEL", "") or "").strip()
    if model:
        return model
    return str(getattr(settings, "OPENROUTER_TRANSLATION_MODEL", "") or "").strip()


def _translation_provider_label() -> str:
    return "DeepSeek" if _translation_provider() == TRANSLATION_PROVIDER_DEEPSEEK else "OpenRouter"


def _translation_api_config() -> tuple[str, str, str]:
    provider = _translation_provider()
    if provider == TRANSLATION_PROVIDER_DEEPSEEK:
        api_key = str(getattr(settings, "DEEPSEEK_API_KEY", "") or "").strip()
        api_url = str(getattr(settings, "DEEPSEEK_API_URL", "") or "").strip()
        model = _translation_model()
        if not api_key:
            raise PostTranslationError("DEEPSEEK_API_KEY не задан в окружении backend")
        if not api_url:
            raise PostTranslationError("DEEPSEEK_API_URL не задан")
        if not model:
            raise PostTranslationError("DEEPSEEK_TRANSLATION_MODEL не задан")
        return api_key, api_url, model

    if provider != TRANSLATION_PROVIDER_OPENROUTER:
        raise PostTranslationError(f"Провайдер перевода не поддерживается: {provider}")

    api_key = str(getattr(settings, "OPENROUTER_API_KEY", "") or "").strip()
    api_url = str(getattr(settings, "OPENROUTER_API_URL", "") or "").strip()
    model = _translation_model()
    if not api_key:
        raise PostTranslationError("OPENROUTER_API_KEY не задан в окружении backend")
    if not api_url:
        raise PostTranslationError("OPENROUTER_API_URL не задан")
    if not model:
        raise PostTranslationError("OPENROUTER_TRANSLATION_MODEL не задан")
    return api_key, api_url, model


def _truncate_translation_title(value: str) -> str:
    title = str(value or "").strip()
    if len(title) <= POST_TRANSLATION_TITLE_MAX_LENGTH:
        return title
    return title[:POST_TRANSLATION_TITLE_MAX_LENGTH].rstrip()


def _truncate_comun_name(value: str) -> str:
    name = str(value or "").strip()
    if len(name) <= COMUN_TRANSLATION_NAME_MAX_LENGTH:
        return name
    return name[:COMUN_TRANSLATION_NAME_MAX_LENGTH].rstrip()


def _decode_post_editor_payload(value: str) -> tuple[dict[str, Any] | None, str]:
    raw = str(value or "").strip()
    if not raw:
        return None, POST_CONTENT_FORMAT_TEXT

    candidates: list[tuple[str, str]] = []
    if raw.startswith("{") and raw.endswith("}"):
        candidates.append((raw, POST_CONTENT_FORMAT_EDITORJS_JSON))
    if re.fullmatch(r"[A-Za-z0-9_\-+/=]+", raw):
        for encoded in (raw, raw.replace("-", "+").replace("_", "/")):
            padded = encoded + ("=" * (-len(encoded) % 4))
            try:
                decoded = base64.b64decode(padded, validate=False).decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                continue
            candidates.append((decoded, POST_CONTENT_FORMAT_EDITORJS_BASE64))

    for candidate, content_format in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("blocks"), list):
            return payload, content_format
    return None, POST_CONTENT_FORMAT_TEXT


def _encode_post_editor_payload(payload: dict[str, Any], content_format: str) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if content_format == POST_CONTENT_FORMAT_EDITORJS_BASE64:
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return raw


def _post_translation_source_payload(post: Post) -> tuple[dict[str, Any], str]:
    editor_payload, content_format = _decode_post_editor_payload(post.content or "")
    return (
        {
            "title": post.title or "",
            "content": editor_payload if editor_payload is not None else post.content or "",
            "content_format": (
                "editorjs"
                if editor_payload is not None
                else POST_CONTENT_FORMAT_TEXT
            ),
        },
        content_format,
    )


def _validate_translated_editor_payload(
    source_payload: dict[str, Any],
    translated_payload: object,
) -> dict[str, Any]:
    if not isinstance(translated_payload, dict) or not isinstance(
        translated_payload.get("blocks"), list
    ):
        raise PostTranslationError(
            f"{_translation_provider_label()} вернул содержимое поста "
            "не в формате EditorJS"
        )

    source_blocks = source_payload.get("blocks") or []
    translated_blocks = translated_payload["blocks"]
    if len(source_blocks) != len(translated_blocks):
        raise PostTranslationError(
            f"{_translation_provider_label()} изменил количество блоков EditorJS"
        )

    for source_block, translated_block in zip(source_blocks, translated_blocks):
        if not isinstance(source_block, dict) or not isinstance(translated_block, dict):
            raise PostTranslationError(
                f"{_translation_provider_label()} вернул поврежденный блок EditorJS"
            )
        for key in ("id", "type"):
            if source_block.get(key) != translated_block.get(key):
                raise PostTranslationError(
                    f"{_translation_provider_label()} изменил {key} блока EditorJS"
                )
    return translated_payload


def _truncate_static_page_title(value: str) -> str:
    title = str(value or "").strip()
    if len(title) <= STATIC_PAGE_TRANSLATION_TITLE_MAX_LENGTH:
        return title
    return title[:STATIC_PAGE_TRANSLATION_TITLE_MAX_LENGTH].rstrip()


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
    model = str(_translation_model() or "").strip()
    translation.status = POST_TRANSLATION_STATUS_PENDING
    translation.model = model
    translation.error_message = ""
    translation.save(update_fields=["status", "model", "error_message", "updated_at"])

    try:
        source_payload, source_content_format = _post_translation_source_payload(post)
        response_payload = _request_openrouter_translation(source_payload, target)
        raw_translated_payload = _parse_translated_json_payload(response_payload)
        translated_title = _truncate_translation_title(
            str(raw_translated_payload.get("title", "") or "")
        )
        raw_translated_content = raw_translated_payload.get("content")
        if source_content_format in {
            POST_CONTENT_FORMAT_EDITORJS_JSON,
            POST_CONTENT_FORMAT_EDITORJS_BASE64,
        }:
            translated_editor_payload = _validate_translated_editor_payload(
                source_payload["content"],
                raw_translated_content,
            )
            translated_content = _encode_post_editor_payload(
                translated_editor_payload,
                source_content_format,
            )
        else:
            if raw_translated_content is not None and not isinstance(
                raw_translated_content, str
            ):
                raise PostTranslationError(
                    f"{_translation_provider_label()} вернул текст поста не строкой"
                )
            translated_content = str(raw_translated_content or "").strip()
        if (post.title or "").strip() and not translated_title:
            raise PostTranslationError(
                f"{_translation_provider_label()} вернул пустой заголовок"
            )
        if (post.content or "").strip() and not translated_content:
            raise PostTranslationError(
                f"{_translation_provider_label()} вернул пустой текст поста"
            )

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
    model = str(_translation_model() or "").strip()
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


def _comun_translation_source_payload(comun: Comun) -> dict[str, Any]:
    categories = [
        {
            "id": category.id,
            "name": category.name or "",
            "description": category.description or "",
        }
        for category in _comun_translation_categories(comun)
    ]
    glossary_terms = [
        {
            "id": term.id,
            "term": term.term or "",
            "term_en": term.term_en or "",
            "definition": term.definition or "",
        }
        for term in _comun_translation_glossary_terms(comun)
    ]
    return {
        "name": comun.name or "",
        "product_description": comun.product_description or "",
        "target_audience": comun.target_audience or "",
        "rules_text": comun.rules_text or "",
        "categories": categories,
        "glossary_terms": glossary_terms,
    }


def _normalize_translation_items(raw_items: object, *, keys: tuple[str, ...]) -> list[dict[str, Any]]:
    if not isinstance(raw_items, list):
        return []
    normalized: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if item_id <= 0 or item_id in seen_ids:
            continue
        seen_ids.add(item_id)
        normalized_item: dict[str, Any] = {"id": item_id}
        for key in keys:
            normalized_item[key] = str(item.get(key) or "").strip()
        normalized.append(normalized_item)
    return normalized


def _source_item_has_text(item: object, keys: tuple[str, ...]) -> bool:
    if not isinstance(item, dict):
        return False
    return any(str(item.get(key) or "").strip() for key in keys)


def _validate_translated_items(
    source_items: object,
    translated_items: list[dict[str, Any]],
    *,
    keys: tuple[str, ...],
    error_message: str,
) -> None:
    if not isinstance(source_items, list):
        return
    translated_by_id = _translation_items_by_id(translated_items)
    for source_item in source_items:
        if not isinstance(source_item, dict) or not _source_item_has_text(source_item, keys):
            continue
        try:
            item_id = int(source_item.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if item_id <= 0:
            continue
        translated_item = translated_by_id.get(item_id)
        if not translated_item:
            raise PostTranslationError(error_message)
        for key in keys:
            if str(source_item.get(key) or "").strip() and not str(translated_item.get(key) or "").strip():
                raise PostTranslationError(error_message)


def _translation_items_by_id(raw_items: object) -> dict[int, dict[str, Any]]:
    if not isinstance(raw_items, list):
        return {}
    result: dict[int, dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("id") or 0)
        except (TypeError, ValueError):
            continue
        if item_id > 0:
            result[item_id] = item
    return result


def translate_comun_to_language(comun: Comun, language: str) -> ComunTranslation:
    language = str(language or "").strip().lower()
    target = SUPPORTED_TRANSLATION_LANGUAGES.get(language)
    if target is None:
        raise PostTranslationError(f"Язык перевода не поддерживается: {language}")
    if _comun_has_negative_rating(comun):
        raise AutoTranslationSkipped("Сообщество имеет отрицательный рейтинг")
    source_payload = _comun_translation_source_payload(comun)
    if not _comun_translation_source_has_text(source_payload):
        raise AutoTranslationSkipped("Переводимый контент сообщества пуст")

    translation, _ = ComunTranslation.objects.get_or_create(comun=comun, language=language)
    model = str(_translation_model() or "").strip()
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
                "community": source_payload,
            },
            system_prompt=(
                "You are a professional localization editor. Translate Tambur community content from "
                "Russian. Return only valid JSON with keys name, product_description, target_audience, "
                "rules_text, categories, and glossary_terms. categories must be an array of objects "
                "with id, name, description. glossary_terms must be an array of objects with id, term, "
                "term_en, definition. Preserve ids exactly. Preserve markdown, lists, URLs, code blocks, "
                "placeholders, and formatting. Translate only human-readable Russian text. Do not add "
                "commentary."
            ),
        )
        translated_payload = _parse_translated_payload(
            response_payload,
            keys=("name", "product_description", "target_audience", "rules_text"),
        )
        raw_translated_payload = _parse_translated_json_payload(response_payload)
        translated_name = _truncate_comun_name(translated_payload.get("name", ""))
        translated_description = str(translated_payload.get("product_description", "") or "").strip()
        translated_target_audience = str(translated_payload.get("target_audience", "") or "").strip()
        translated_rules = str(translated_payload.get("rules_text", "") or "").strip()
        translated_categories = _normalize_translation_items(
            raw_translated_payload.get("categories"),
            keys=("name", "description"),
        )
        translated_glossary_terms = _normalize_translation_items(
            raw_translated_payload.get("glossary_terms"),
            keys=("term", "term_en", "definition"),
        )
        if (comun.name or "").strip() and not translated_name:
            raise PostTranslationError("OpenRouter вернул пустое название сообщества")
        if (comun.product_description or "").strip() and not translated_description:
            raise PostTranslationError("OpenRouter вернул пустое описание сообщества")
        if (comun.target_audience or "").strip() and not translated_target_audience:
            raise PostTranslationError("OpenRouter вернул пустой текст целевой аудитории")
        if (comun.rules_text or "").strip() and not translated_rules:
            raise PostTranslationError("OpenRouter вернул пустые правила сообщества")
        _validate_translated_items(
            source_payload.get("categories"),
            translated_categories,
            keys=("name", "description"),
            error_message="OpenRouter вернул неполные категории сообщества",
        )
        _validate_translated_items(
            source_payload.get("glossary_terms"),
            translated_glossary_terms,
            keys=("term", "definition"),
            error_message="OpenRouter вернул неполные термины глоссария",
        )

        translation.name = translated_name
        translation.product_description = translated_description
        translation.target_audience = translated_target_audience
        translation.rules_text = translated_rules
        translation.categories = translated_categories
        translation.glossary_terms = translated_glossary_terms
        translation.status = POST_TRANSLATION_STATUS_TRANSLATED
        translation.error_message = ""
        translation.raw_response = response_payload
        translation.model = model
        translation.save(
            update_fields=[
                "name",
                "product_description",
                "target_audience",
                "rules_text",
                "categories",
                "glossary_terms",
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


def _decode_static_page_editor_payload(value: str) -> dict[str, Any] | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    candidates = [raw]
    try:
        decoded = base64.b64decode(raw, validate=True).decode("utf-8")
        candidates.append(decoded)
    except (ValueError, UnicodeDecodeError):
        pass

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and isinstance(payload.get("blocks"), list):
            return payload
    return None


def _encode_static_page_editor_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def _static_page_translation_source_payload(page: StaticPageContent) -> dict[str, Any]:
    editor_payload = _decode_static_page_editor_payload(page.content or "")
    return {
        "title": page.title or "",
        "content": editor_payload if editor_payload is not None else page.content or "",
        "content_format": "editorjs" if editor_payload is not None else "text",
    }


def translate_static_page_to_language(page: StaticPageContent, language: str) -> StaticPageTranslation:
    language = str(language or "").strip().lower()
    target = SUPPORTED_TRANSLATION_LANGUAGES.get(language)
    if target is None:
        raise PostTranslationError(f"Язык перевода не поддерживается: {language}")
    if not _static_page_is_translatable(page):
        raise AutoTranslationSkipped("Статичная страница недоступна для перевода")

    source_payload = _static_page_translation_source_payload(page)
    translation, _ = StaticPageTranslation.objects.get_or_create(page=page, language=language)
    model = str(_translation_model() or "").strip()
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
                "static_page": source_payload,
            },
            system_prompt=(
                "You are a professional localization editor. Translate Tambur static pages from Russian. "
                "Return only valid JSON with keys title and content. If content is an EditorJS object, "
                "return content as the same EditorJS object shape and preserve every block type, id, URL, "
                "media URL, embed, code block, placeholder, and non-text field. Translate only "
                "human-readable Russian text inside title and content. Do not add commentary."
            ),
        )
        raw_translated_payload = _parse_translated_json_payload(response_payload)
        translated_payload = _parse_translated_payload(response_payload, keys=("title",))
        translated_title = _truncate_static_page_title(translated_payload.get("title", ""))
        if (page.title or "").strip() and not translated_title:
            raise PostTranslationError("OpenRouter вернул пустой заголовок статичной страницы")

        raw_translated_content = raw_translated_payload.get("content")
        if source_payload["content_format"] == "editorjs":
            if not isinstance(raw_translated_content, dict) or not isinstance(
                raw_translated_content.get("blocks"), list
            ):
                raise PostTranslationError("OpenRouter вернул статичную страницу не в формате EditorJS")
            translated_content = _encode_static_page_editor_payload(raw_translated_content)
        else:
            translated_content = str(raw_translated_content or "").strip()

        if (page.content or "").strip() and not translated_content:
            raise PostTranslationError("OpenRouter вернул пустое содержимое статичной страницы")

        translation.title = translated_title
        translation.content = translated_content
        translation.status = POST_TRANSLATION_STATUS_TRANSLATED
        translation.error_message = ""
        translation.raw_response = response_payload
        translation.model = model
        translation.save(
            update_fields=[
                "title",
                "content",
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

    model = str(_translation_model() or "").strip()
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
    source_updated_at = _comun_source_updated_at(comun)
    return _schedule_auto_translation_task(
        CONTENT_TRANSLATION_KIND_COMUN,
        comun.pk,
        source_updated_at=source_updated_at,
        scheduled_at=timezone.now() + AUTO_TRANSLATION_DELAYS[CONTENT_TRANSLATION_KIND_COMUN],
    )


def schedule_static_page_auto_translation(page: StaticPageContent) -> ContentTranslationTask | None:
    if not _static_page_is_translatable(page):
        _delete_auto_translation_task(CONTENT_TRANSLATION_KIND_STATIC_PAGE, page.pk)
        return None
    return _schedule_auto_translation_task(
        CONTENT_TRANSLATION_KIND_STATIC_PAGE,
        page.pk,
        source_updated_at=page.updated_at,
        scheduled_at=(page.updated_at or timezone.now()) + AUTO_TRANSLATION_DELAYS[CONTENT_TRANSLATION_KIND_STATIC_PAGE],
    )


def process_due_translation_tasks(*, limit: int = 20) -> dict[str, int]:
    stats = {"processed": 0, "done": 0, "failed": 0, "skipped": 0}
    now = timezone.now()
    _reset_stale_running_translation_tasks(now)
    _reset_retryable_failed_translation_tasks(now)
    task_ids = _claim_due_translation_task_ids(limit=limit, now=now)
    for task_id in task_ids:
        result = _process_claimed_translation_task(task_id)
        stats["processed"] += 1
        stats[result] = stats.get(result, 0) + 1
    return stats


def process_translation_task(task_id: int) -> str:
    task_id = _claim_translation_task_id(task_id)
    if task_id is None:
        return "skipped"
    return _process_claimed_translation_task(task_id)


def _claim_due_translation_task_ids(*, limit: int, now) -> list[int]:
    with transaction.atomic():
        tasks = list(
            ContentTranslationTask.objects.select_for_update(skip_locked=True)
            .filter(
                status=CONTENT_TRANSLATION_TASK_STATUS_PENDING,
                scheduled_at__lte=now,
                attempts__lt=CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS,
            )
            .order_by("scheduled_at", "id")[:limit]
        )
        _mark_translation_tasks_running(tasks)
        return [task.pk for task in tasks]


def _claim_translation_task_id(task_id: int) -> int | None:
    with transaction.atomic():
        try:
            task = ContentTranslationTask.objects.select_for_update().get(pk=task_id)
        except ContentTranslationTask.DoesNotExist:
            return None
        if task.status != CONTENT_TRANSLATION_TASK_STATUS_PENDING:
            return None
        if task.attempts >= CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS:
            return None
        if task.scheduled_at > timezone.now():
            return None
        _mark_translation_tasks_running([task])
        return task.pk


def _mark_translation_tasks_running(tasks: list[ContentTranslationTask]) -> None:
    if not tasks:
        return
    locked_at = timezone.now()
    for task in tasks:
        task.status = CONTENT_TRANSLATION_TASK_STATUS_RUNNING
        task.locked_at = locked_at
        task.attempts = int(task.attempts or 0) + 1
        task.last_error = ""
        task.updated_at = locked_at
    ContentTranslationTask.objects.bulk_update(
        tasks,
        ["status", "locked_at", "attempts", "last_error", "updated_at"],
    )


def _process_claimed_translation_task(task_id: int) -> str:
    task = ContentTranslationTask.objects.filter(pk=task_id).first()
    if not task or task.status != CONTENT_TRANSLATION_TASK_STATUS_RUNNING:
        return "skipped"
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


def _reset_retryable_failed_translation_tasks(now) -> int:
    retry_before = now - CONTENT_TRANSLATION_TASK_FAILED_RETRY_AFTER
    return ContentTranslationTask.objects.filter(
        status=CONTENT_TRANSLATION_TASK_STATUS_FAILED,
        updated_at__lt=retry_before,
        attempts__lt=CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS,
    ).update(
        status=CONTENT_TRANSLATION_TASK_STATUS_PENDING,
        scheduled_at=now,
        locked_at=None,
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
            "attempts": 0,
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
    return _comun_translation_source_has_text(_comun_translation_source_payload(comun))


def _static_page_is_translatable(page: StaticPageContent) -> bool:
    if not page.pk:
        return False
    return bool((page.title or "").strip() or (page.content or "").strip())


def _comun_translation_categories(comun: Comun) -> list[ComunCategory]:
    if not comun.pk:
        return []
    return list(
        ComunCategory.objects.filter(comun_id=comun.pk, is_active=True)
        .order_by("sort_order", "name", "id")
        .only("id", "name", "description", "updated_at")
    )


def _comun_translation_glossary_terms(comun: Comun) -> list[ComunGlossaryTerm]:
    if not comun.pk or not getattr(comun, "glossary_enabled", False):
        return []
    return list(
        ComunGlossaryTerm.objects.filter(comun_id=comun.pk, is_active=True)
        .order_by("sort_order", "term", "id")
        .only("id", "term", "term_en", "definition", "updated_at")
    )


def _comun_translation_source_has_text(source_payload: dict[str, Any]) -> bool:
    for key in ("name", "product_description", "target_audience", "rules_text"):
        if str(source_payload.get(key) or "").strip():
            return True
    for category in source_payload.get("categories") or []:
        if _source_item_has_text(category, ("name", "description")):
            return True
    for term in source_payload.get("glossary_terms") or []:
        if _source_item_has_text(term, ("term", "term_en", "definition")):
            return True
    return False


def _comun_source_updated_at(comun: Comun):
    timestamps = [getattr(comun, "updated_at", None)]
    timestamps.extend(category.updated_at for category in _comun_translation_categories(comun))
    timestamps.extend(term.updated_at for term in _comun_translation_glossary_terms(comun))
    return max((timestamp for timestamp in timestamps if timestamp), default=timezone.now())


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
        source_content_info = _decode_post_editor_payload(post.content or "")
        for language in SUPPORTED_TRANSLATION_LANGUAGES:
            if _post_translation_is_current(post, language, source_content_info):
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
        _raise_if_task_is_stale(task, _comun_source_updated_at(comun))
        _reserve_translation_budget(task)
        for language in SUPPORTED_TRANSLATION_LANGUAGES:
            if _comun_translation_is_current(comun, language):
                continue
            translate_comun_to_language(comun, language)
        return

    if task.kind == CONTENT_TRANSLATION_KIND_STATIC_PAGE:
        page = StaticPageContent.objects.filter(pk=task.object_id).first()
        if not page or not _static_page_is_translatable(page):
            raise AutoTranslationSkipped("Статичная страница недоступна для перевода")
        _raise_if_task_is_stale(task, page.updated_at)
        _reserve_translation_budget(task)
        for language in SUPPORTED_TRANSLATION_LANGUAGES:
            if _static_page_translation_is_current(page, language):
                continue
            translate_static_page_to_language(page, language)
        return

    raise AutoTranslationSkipped(f"Неизвестный тип задачи: {task.kind}")


def _translation_updated_after_source(translation, source_updated_at) -> bool:
    return not source_updated_at or translation.updated_at >= source_updated_at


def _post_translation_is_current(
    post: Post,
    language: str,
    source_content_info: tuple[dict[str, Any] | None, str] | None = None,
) -> bool:
    translation = PostTranslation.objects.filter(post=post, language=language).first()
    return post_translation_record_is_current(post, translation, source_content_info)


def post_translation_record_is_current(
    post: Post,
    translation: PostTranslation | None,
    source_content_info: tuple[dict[str, Any] | None, str] | None = None,
) -> bool:
    if not translation or translation.status != POST_TRANSLATION_STATUS_TRANSLATED:
        return False
    if (post.title or "").strip() and not (translation.title or "").strip():
        return False
    if (post.content or "").strip() and not (translation.content or "").strip():
        return False
    source_editor_payload, source_content_format = (
        source_content_info
        if source_content_info is not None
        else _decode_post_editor_payload(post.content or "")
    )
    if source_content_format in {
        POST_CONTENT_FORMAT_EDITORJS_JSON,
        POST_CONTENT_FORMAT_EDITORJS_BASE64,
    }:
        translated_editor_payload, _translated_format = _decode_post_editor_payload(
            translation.content or ""
        )
        if translated_editor_payload is None:
            return False
        try:
            _validate_translated_editor_payload(
                source_editor_payload or {},
                translated_editor_payload,
            )
        except PostTranslationError:
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
    if (comun.name or "").strip() and not (translation.name or "").strip():
        return False
    if (comun.product_description or "").strip() and not (
        translation.product_description or ""
    ).strip():
        return False
    if (comun.target_audience or "").strip() and not (
        translation.target_audience or ""
    ).strip():
        return False
    if (comun.rules_text or "").strip() and not (translation.rules_text or "").strip():
        return False
    translated_categories = _translation_items_by_id(translation.categories)
    for category in _comun_translation_categories(comun):
        if not _source_item_has_text(
            {"name": category.name, "description": category.description},
            ("name", "description"),
        ):
            continue
        category_translation = translated_categories.get(category.id)
        if not category_translation:
            return False
        if (category.name or "").strip() and not (category_translation.get("name") or "").strip():
            return False
        if (category.description or "").strip() and not (
            category_translation.get("description") or ""
        ).strip():
            return False

    translated_terms = _translation_items_by_id(translation.glossary_terms)
    for term in _comun_translation_glossary_terms(comun):
        if not _source_item_has_text(
            {"term": term.term, "term_en": term.term_en, "definition": term.definition},
            ("term", "term_en", "definition"),
        ):
            continue
        term_translation = translated_terms.get(term.id)
        if not term_translation:
            return False
        if (term.term or "").strip() and not (term_translation.get("term") or "").strip():
            return False
        if (term.definition or "").strip() and not (
            term_translation.get("definition") or ""
        ).strip():
            return False
    return _translation_updated_after_source(translation, _comun_source_updated_at(comun))


def _static_page_translation_is_current(page: StaticPageContent, language: str) -> bool:
    translation = StaticPageTranslation.objects.filter(page=page, language=language).first()
    if not translation or translation.status != POST_TRANSLATION_STATUS_TRANSLATED:
        return False
    if (page.title or "").strip() and not (translation.title or "").strip():
        return False
    if (page.content or "").strip() and not (translation.content or "").strip():
        return False
    return _translation_updated_after_source(translation, page.updated_at)


def _raise_if_task_is_stale(task: ContentTranslationTask, source_updated_at) -> None:
    if task.source_updated_at and source_updated_at and source_updated_at > task.source_updated_at:
        delay = AUTO_TRANSLATION_DELAYS.get(task.kind, timedelta(minutes=5))
        task.status = CONTENT_TRANSLATION_TASK_STATUS_PENDING
        task.scheduled_at = source_updated_at + delay
        task.source_updated_at = source_updated_at
        task.locked_at = None
        task.save(update_fields=["status", "scheduled_at", "source_updated_at", "locked_at", "updated_at"])
        raise AutoTranslationRescheduled("Контент был обновлен, задача перенесена")


def _request_openrouter_translation(
    post_payload: dict[str, Any],
    target: dict[str, str],
) -> dict[str, Any]:
    return _request_openrouter_json_translation(
        {
            "source_language": "Russian",
            "target_language": target["target"],
            "target_locale": target["locale"],
            "post": post_payload,
        },
        system_prompt=(
            "You are a professional localization editor. Translate Tambur posts from Russian. "
            "Return only valid JSON with keys title and content. If content is an EditorJS object, "
            "return content as the same EditorJS object shape and preserve every block type, id, URL, "
            "media URL, embed, code block, placeholder, and non-text field. Preserve HTML tags and "
            "markdown. Translate only human-readable Russian text. Do not add commentary."
        ),
    )


def _request_openrouter_json_translation(
    user_payload: dict[str, Any],
    *,
    system_prompt: str,
) -> dict[str, Any]:
    provider = _translation_provider()
    provider_label = _translation_provider_label()
    api_key, api_url, model = _translation_api_config()
    site_base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip()
    app_title = str(getattr(settings, "OPENROUTER_APP_TITLE", "") or "Tambur").strip()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Title": app_title,
    }
    if site_base_url:
        headers["HTTP-Referer"] = site_base_url
    if provider == TRANSLATION_PROVIDER_OPENROUTER:
        headers["X-OpenRouter-Title"] = app_title

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
        "max_tokens": max(
            min(int(getattr(settings, "CONTENT_TRANSLATION_MAX_TOKENS", 65_536)), 384_000),
            1_024,
        ),
    }
    if provider == TRANSLATION_PROVIDER_OPENROUTER:
        payload["provider"] = {
            "sort": "throughput",
            "require_parameters": True,
        }
        payload["reasoning"] = {
            "effort": "none",
            "exclude": True,
        }
    elif provider == TRANSLATION_PROVIDER_DEEPSEEK:
        payload["thinking"] = {"type": "disabled"}

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=90)
    except requests.RequestException as exc:
        raise PostTranslationError(f"Ошибка запроса {provider_label}: {exc}") from exc

    try:
        response_payload = response.json()
    except ValueError as exc:
        raise PostTranslationError(f"{provider_label} вернул не JSON, HTTP {response.status_code}") from exc

    if response.status_code >= 400:
        raise PostTranslationError(
            _extract_translation_provider_error(response_payload, response.status_code)
        )

    return response_payload


def _extract_translation_provider_error(response_payload: dict[str, Any], status_code: int) -> str:
    provider_label = _translation_provider_label()
    error = response_payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message") or "").strip()
        if message:
            return f"{provider_label} HTTP {status_code}: {message[:1000]}"
    return f"{provider_label} HTTP {status_code}"


def _parse_translated_payload(
    response_payload: dict[str, Any],
    *,
    keys: tuple[str, ...] = ("title", "content"),
) -> dict[str, str]:
    payload = _parse_translated_json_payload(response_payload)
    return {key: str(payload.get(key, "") or "") for key in keys}


def _parse_translated_json_payload(response_payload: dict[str, Any]) -> dict[str, Any]:
    provider_label = _translation_provider_label()
    try:
        message = response_payload["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise PostTranslationError(
            f"{provider_label} вернул ответ без choices[0].message"
        ) from exc

    content = _normalize_openrouter_content(message.get("content"))
    if not content.strip():
        raise PostTranslationError(f"{provider_label} вернул пустой content")

    try:
        payload = json.loads(content)
    except json.JSONDecodeError as initial_exc:
        try:
            payload = json.loads(_extract_json_object(content))
        except (json.JSONDecodeError, PostTranslationError) as exc:
            finish_reason = str(
                response_payload.get("choices", [{}])[0].get("finish_reason") or "unknown"
            )
            raise PostTranslationError(
                f"{provider_label} вернул некорректный JSON: "
                f"finish_reason={finish_reason}, content_chars={len(content)}, "
                f"parse_error={initial_exc.msg}"
            ) from exc

    if not isinstance(payload, dict):
        raise PostTranslationError(f"{provider_label} вернул не JSON-объект")
    return payload


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
    raise PostTranslationError(
        f"{_translation_provider_label()} вернул content не в формате JSON"
    )
