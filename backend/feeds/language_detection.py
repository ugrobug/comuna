from __future__ import annotations

import re
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from langdetect import DetectorFactory, LangDetectException, detect_langs

from feeds.preview import _collect_editor_text, _normalize_text, parse_editor_payload


SUPPORTED_POST_LANGUAGES = frozenset({"ru", "en", "es", "pt", "de", "fr", "tr", "id"})
DEFAULT_POST_LANGUAGE = "ru"
MINIMUM_LETTER_COUNT = 40
MINIMUM_CONFIDENCE = 0.80
MINIMUM_CONFIDENCE_GAP = 0.12

DetectorFactory.seed = 0


def normalize_post_language(value: object, fallback: str = DEFAULT_POST_LANGUAGE) -> str:
    language = str(value or "").strip().lower()
    return language if language in SUPPORTED_POST_LANGUAGES else fallback


def post_language_fallback_for_user(user: Any) -> str:
    try:
        feed_settings = user.feed_settings
    except (AttributeError, ObjectDoesNotExist):
        return DEFAULT_POST_LANGUAGE
    if not getattr(feed_settings, "interface_language_manual", False):
        return DEFAULT_POST_LANGUAGE
    return normalize_post_language(getattr(feed_settings, "interface_language", ""))


def post_language_text(title: str, content: str) -> str:
    editor_payload = parse_editor_payload(content)
    content_text = (
        _collect_editor_text(editor_payload)
        if editor_payload is not None
        else _normalize_text(content or "")
    )
    return re.sub(r"\s+", " ", f"{title or ''} {content_text}").strip()


def detect_post_language(
    title: str,
    content: str,
    *,
    fallback: str = DEFAULT_POST_LANGUAGE,
) -> str:
    normalized_fallback = normalize_post_language(fallback)
    text = post_language_text(title, content)
    letters = re.findall(r"[^\W\d_]", text, flags=re.UNICODE)
    if len(letters) < MINIMUM_LETTER_COUNT:
        return normalized_fallback

    cyrillic_count = len(re.findall(r"[А-Яа-яЁё]", text))
    if cyrillic_count / len(letters) >= 0.70:
        return "ru"

    try:
        candidates = [
            candidate
            for candidate in detect_langs(text[:20_000])
            if candidate.lang in SUPPORTED_POST_LANGUAGES
        ]
    except LangDetectException:
        return normalized_fallback
    if not candidates:
        return normalized_fallback

    best = candidates[0]
    runner_up_probability = candidates[1].prob if len(candidates) > 1 else 0.0
    if (
        best.prob < MINIMUM_CONFIDENCE
        or best.prob - runner_up_probability < MINIMUM_CONFIDENCE_GAP
    ):
        return normalized_fallback
    return best.lang
