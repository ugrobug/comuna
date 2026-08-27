from __future__ import annotations

import re

from feeds.language_detection import post_language_text


MIN_POST_TRANSLATION_TEXT_LENGTH = 500
_HASHTAG_RE = re.compile(r"(?<!\w)#[^\s#]+", flags=re.UNICODE)


def post_translation_text(content: str) -> str:
    text = post_language_text("", content or "")
    text = _HASHTAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def post_translation_text_length(content: str) -> int:
    return len(post_translation_text(content))


def post_meets_translation_quality(post) -> bool:
    text_length = int(getattr(post, "translation_text_length", 0) or 0)
    if not text_length and getattr(post, "content", ""):
        text_length = post_translation_text_length(post.content)
    return text_length >= MIN_POST_TRANSLATION_TEXT_LENGTH
