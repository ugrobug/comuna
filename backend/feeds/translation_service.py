from __future__ import annotations

import json
import re
import threading
from typing import Any

import requests
from django.conf import settings
from django.db import close_old_connections

from feeds.models import (
    POST_TRANSLATION_LANGUAGE_CHOICES,
    POST_TRANSLATION_LANGUAGE_INDONESIAN,
    POST_TRANSLATION_LANGUAGE_TURKISH,
    POST_TRANSLATION_STATUS_FAILED,
    POST_TRANSLATION_STATUS_PENDING,
    POST_TRANSLATION_STATUS_TRANSLATED,
    Post,
    PostTranslation,
)
from feeds.preview import build_post_preview


class PostTranslationError(Exception):
    pass


SUPPORTED_TRANSLATION_LANGUAGES = {
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


def get_translation_language_label(language: str) -> str:
    return dict(POST_TRANSLATION_LANGUAGE_CHOICES).get(language, language)


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
        translated_title = str(translated_payload.get("title", "") or "").strip()
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

    worker = threading.Thread(
        target=_run_queued_post_translations,
        args=(post.pk, tuple(normalized_languages)),
        daemon=True,
    )
    worker.start()
    return translations


def _normalize_translation_languages(languages: list[str]) -> list[str]:
    normalized: list[str] = []
    for language in languages:
        code = str(language or "").strip().lower()
        if code not in SUPPORTED_TRANSLATION_LANGUAGES:
            raise PostTranslationError(f"Язык перевода не поддерживается: {code}")
        if code not in normalized:
            normalized.append(code)
    return normalized


def _run_queued_post_translations(post_id: int, languages: tuple[str, ...]) -> None:
    close_old_connections()
    try:
        post = Post.objects.get(pk=post_id)
        for language in languages:
            try:
                translate_post_to_language(post, language)
            except PostTranslationError:
                continue
    except Post.DoesNotExist:
        return
    finally:
        close_old_connections()


def _request_openrouter_translation(post: Post, target: dict[str, str]) -> dict[str, Any]:
    api_key = str(getattr(settings, "OPENROUTER_API_KEY", "") or "").strip()
    if not api_key:
        raise PostTranslationError("OPENROUTER_API_KEY не задан в окружении backend")

    api_url = str(getattr(settings, "OPENROUTER_API_URL", "") or "").strip()
    model = str(getattr(settings, "OPENROUTER_TRANSLATION_MODEL", "") or "").strip()
    if not api_url:
        raise PostTranslationError("OPENROUTER_API_URL не задан")
    if not model:
        raise PostTranslationError("OPENROUTER_TRANSLATION_MODEL не задан")

    user_payload = {
        "source_language": "Russian",
        "target_language": target["target"],
        "target_locale": target["locale"],
        "post": {
            "title": post.title or "",
            "content": post.content or "",
        },
    }
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
                "content": (
                    "You are a professional localization editor. Translate Tambur posts from Russian. "
                    "Return only valid JSON with keys title and content. Preserve HTML tags, markdown, "
                    "EditorJS JSON structure, URLs, media URLs, embeds, code blocks, and placeholders. "
                    "Translate only human-readable Russian text. Do not add commentary."
                ),
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


def _parse_translated_payload(response_payload: dict[str, Any]) -> dict[str, str]:
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
    return {
        "title": str(payload.get("title", "") or ""),
        "content": str(payload.get("content", "") or ""),
    }


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
