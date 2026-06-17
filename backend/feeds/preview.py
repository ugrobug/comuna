from __future__ import annotations

import base64
import json
import re
from html import escape, unescape
from typing import Any

from django.utils.html import strip_tags

from editor import service as editor_service


EDITOR_MODEL_BASE64_RE = re.compile(r"^[A-Za-z0-9+/_-]*={0,2}$")
IMAGE_URL_PATH_RE = re.compile(r"\.(?:avif|gif|jpe?g|png|webp)(?:$|[?#])", re.IGNORECASE)
IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)
IMG_TAG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ORPHAN_IMAGE_ATTR_FRAGMENT_RE = re.compile(r"(?:\s+alt=[\"'][^\"']*[\"']\s*/>)+", re.IGNORECASE)
PARAGRAPH_RE = re.compile(r"<p\b[^>]*>([\s\S]*?)</p>", re.IGNORECASE)
PREVIEW_DESCRIPTION_RE = re.compile(
    r"<preview-description>([\s\S]*?)</preview-description>", re.IGNORECASE
)
BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
BLOCK_BOUNDARY_RE = re.compile(r"</(?:p|div|li|blockquote|h[1-6])\s*>", re.IGNORECASE)
BUG_REPORT_PLATFORM_LABELS = {
    "web": "Web",
    "windows": "Windows",
    "macos": "macOS",
    "linux": "Linux",
    "android": "Android",
    "ios": "iOS",
}
BUG_REPORT_BROWSER_LABELS = {
    "chrome": "Chrome",
    "safari": "Safari",
    "firefox": "Firefox",
    "edge": "Edge",
    "opera": "Opera",
    "yandex_browser": "Яндекс Браузер",
    "samsung_internet": "Samsung Internet",
    "arc": "Arc",
    "other": "Другое",
}


def _normalize_text(value: str) -> str:
    html = BLOCK_BOUNDARY_RE.sub("\n", BR_RE.sub("\n", value or ""))
    text = unescape(strip_tags(html))
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _trim_preview_text(value: str, max_length: int) -> tuple[str, bool]:
    text = _normalize_text(value)
    if len(text) <= max_length:
        return text, False
    trimmed = text[:max_length].rsplit(" ", 1)[0].strip()
    return f"{trimmed}...", True


def _preview_paragraph_from_text(value: str, max_length: int) -> str:
    text, _trimmed = _trim_preview_text(value, max_length)
    if not text:
        return ""
    return f"<p>{escape(text).replace(chr(10), '<br>')}</p>"


def _preview_paragraph_from_html(value: str, max_length: int) -> str:
    html = (value or "").strip()
    text, trimmed = _trim_preview_text(html, max_length)
    if not text:
        return ""
    if not trimmed and html and _normalize_text(html) == text:
        return f"<p>{html}</p>"
    return f"<p>{escape(text).replace(chr(10), '<br>')}</p>"


def parse_editor_payload(raw_value: str) -> dict[str, Any] | None:
    raw = str(raw_value or "").strip()
    if not raw or (raw.startswith("<") and raw.endswith(">")):
        return None

    if raw.startswith("{") and raw.endswith("}"):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) and isinstance(parsed.get("blocks"), list) else None

    if not EDITOR_MODEL_BASE64_RE.match(raw) or len(raw) < 16:
        return None

    try:
        normalized = raw.replace("-", "+").replace("_", "/")
        normalized += "=" * (-len(normalized) % 4)
        decoded = base64.b64decode(normalized).decode("utf-8")
        parsed = json.loads(decoded)
    except (TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) and isinstance(parsed.get("blocks"), list) else None


def _image_url_from_value(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    return url if IMAGE_URL_PATH_RE.search(url) else ""


def _image_url_from_payload(value: Any) -> str:
    if isinstance(value, dict):
        return _image_url_from_value(value.get("url")) or _image_url_from_payload(value.get("file"))
    return _image_url_from_value(value)


def _editor_image_candidates(payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(payload, dict):
        return []

    candidates: list[str] = []
    additional = payload.get("additional")
    if isinstance(additional, dict):
        candidates.extend(
            filter(
                None,
                [
                    _image_url_from_value(additional.get("previewImage")),
                    _image_url_from_value(additional.get("preview_image_url")),
                    _image_url_from_value(additional.get("cover_image_url")),
                ],
            )
        )

    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return candidates

    for block in blocks:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()
        data = block.get("data")
        if not isinstance(data, dict):
            continue
        if block_type == "image":
            candidates.append(_image_url_from_payload(data.get("file")) or _image_url_from_value(data.get("url")))
        elif block_type == "gallery":
            images = data.get("images")
            if isinstance(images, list) and images:
                candidates.append(_image_url_from_payload(images[0]))
        elif block_type in {"imagecompare", "compare"}:
            candidates.append(_image_url_from_payload(data.get("before")))
            candidates.append(_image_url_from_payload(data.get("after")))
    return [candidate for candidate in candidates if candidate]


def _template_image_candidates(template_payload: dict[str, Any] | None) -> list[str]:
    if not isinstance(template_payload, dict):
        return []
    data = template_payload.get("data")
    if not isinstance(data, dict):
        return []
    template_type = str(template_payload.get("type") or "").strip()
    if template_type == "movie_review":
        keys = ("poster_url", "cover_image_url")
    elif template_type == "music_release":
        keys = ("cover_image_url", "poster_url")
    else:
        keys = ("cover_image_url", "preview_image_url")
    return [_image_url_from_value(data.get(key)) for key in keys if _image_url_from_value(data.get(key))]


def _raw_data_image_candidates(raw_data: dict[str, Any] | None) -> list[str]:
    if not isinstance(raw_data, dict):
        return []
    candidates: list[str] = []
    gallery_urls = raw_data.get("gallery_urls")
    if isinstance(gallery_urls, list):
        candidates.extend(_image_url_from_value(url) for url in gallery_urls)
    candidates.extend(
        _image_url_from_value(raw_data.get(key))
        for key in ("image_url", "photo_url", "preview_image_url")
    )
    return [candidate for candidate in candidates if candidate]


def _html_image_candidates(content: str) -> list[str]:
    return [_image_url_from_value(match.group(1)) for match in IMG_SRC_RE.finditer(content or "")]


def _editor_preview_content(payload: dict[str, Any], max_length: int) -> str:
    additional = payload.get("additional")
    if isinstance(additional, dict):
        description = str(additional.get("previewDescription") or "").strip()
        if description:
            return _preview_paragraph_from_text(description, max_length)

    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return ""
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if str(block.get("type") or "").strip().lower() != "paragraph":
            continue
        data = block.get("data")
        if not isinstance(data, dict):
            continue
        text = str(data.get("text") or "").strip()
        if text:
            return _preview_paragraph_from_html(text, max_length)
    return ""


def _collect_editor_text(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, str):
        return _normalize_text(value)
    if isinstance(value, list):
        return " ".join(filter(None, (_collect_editor_text(item) for item in value)))
    if not isinstance(value, dict):
        return ""

    chunks: list[str] = []
    for key in ("text", "caption", "title", "description", "quote", "message"):
        raw_text = value.get(key)
        if isinstance(raw_text, str):
            text = _normalize_text(raw_text)
            if text:
                chunks.append(text)
    for key in ("blocks", "data", "items", "content", "rows", "images", "file", "before", "after"):
        nested = value.get(key)
        if isinstance(nested, (dict, list)):
            text = _collect_editor_text(nested)
            if text:
                chunks.append(text)
    return " ".join(chunks)


def post_preview_has_more(content: str, preview_content: str) -> bool:
    preview_text = _normalize_text(preview_content or "")
    if not preview_text:
        return False

    editor_payload = parse_editor_payload(content)
    full_text = (
        _collect_editor_text(editor_payload)
        if editor_payload
        else _normalize_text(content or "")
    )
    if not full_text:
        return False

    normalized_preview = preview_text.rstrip(".…").strip()
    normalized_full = full_text.rstrip(".…").strip()
    return len(normalized_full) > len(normalized_preview) + 8


def _bug_report_preview_content(template_payload: dict[str, Any] | None, max_length: int) -> str:
    if not isinstance(template_payload, dict) or str(template_payload.get("type") or "").strip() != "bug_report":
        return ""
    data = template_payload.get("data")
    if not isinstance(data, dict):
        return ""

    platforms = [
        BUG_REPORT_PLATFORM_LABELS.get(str(item or "").strip(), str(item or "").strip())
        for item in data.get("platforms") or []
        if str(item or "").strip()
    ]
    browsers = [
        BUG_REPORT_BROWSER_LABELS.get(str(item or "").strip(), str(item or "").strip())
        for item in data.get("browsers") or []
        if str(item or "").strip()
    ]
    parts: list[str] = []
    if platforms:
        parts.append(f"Платформы: {', '.join(platforms)}")
    if browsers:
        parts.append(f"Браузеры: {', '.join(browsers)}")
    if not parts:
        return ""
    return _preview_paragraph_from_text("\n".join(parts), max_length)


def _html_preview_content(content: str, max_length: int) -> str:
    description_match = PREVIEW_DESCRIPTION_RE.search(content or "")
    if description_match and description_match.group(1).strip():
        return _preview_paragraph_from_text(description_match.group(1), max_length)

    paragraph_match = PARAGRAPH_RE.search(content or "")
    if paragraph_match and paragraph_match.group(1).strip():
        return _preview_paragraph_from_html(paragraph_match.group(1), max_length)

    without_images = IMG_TAG_RE.sub("", content or "")
    without_image_fragments = ORPHAN_IMAGE_ATTR_FRAGMENT_RE.sub("", without_images)
    return _preview_paragraph_from_text(without_image_fragments, max_length)


def build_post_preview(
    content: str,
    raw_data: dict[str, Any] | None = None,
    *,
    max_length: int = 250,
) -> dict[str, str]:
    raw_data = raw_data if isinstance(raw_data, dict) else {}
    template_payload, _template_error = editor_service._normalize_post_template_payload(
        raw_data.get("template") if isinstance(raw_data.get("template"), dict) else None
    )
    editor_payload = parse_editor_payload(content)
    is_bug_report = (
        isinstance(template_payload, dict)
        and str(template_payload.get("type") or "").strip() == "bug_report"
    )

    image_candidates: list[str] = []
    if not is_bug_report:
        image_candidates.extend(_template_image_candidates(template_payload))
        if editor_payload:
            image_candidates.extend(_editor_image_candidates(editor_payload))
        else:
            image_candidates.extend(_html_image_candidates(content))
        image_candidates.extend(_raw_data_image_candidates(raw_data))

    preview_image_url = next((url for url in image_candidates if url), "")
    preview_content = _bug_report_preview_content(template_payload, max_length)
    if not preview_content:
        preview_content = (
            _editor_preview_content(editor_payload, max_length)
            if editor_payload
            else _html_preview_content(content, max_length)
        )

    return {
        "preview_content": preview_content,
        "preview_image_url": preview_image_url,
    }
