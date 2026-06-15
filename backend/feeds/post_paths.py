"""Публичные пути постов и slug из заголовка (как на фронте: slugifyTitle)."""

from __future__ import annotations

import re

_TRANSLIT_MAP = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ы": "y",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    "ъ": "",
    "ь": "",
}


def slugify_title(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower()
    translit = "".join(_TRANSLIT_MAP.get(ch, ch) for ch in lowered)
    return re.sub(r"[^a-z0-9]+", "-", translit).strip("-")


def build_post_public_path(post_id: int, title: str | None = None) -> str:
    """Канонический публичный путь поста: `/b/post/{id}` или `/b/post/{id}-{slug}`."""
    slug = slugify_title((title or "").strip())
    return f"/b/post/{post_id}-{slug}" if slug else f"/b/post/{post_id}"
