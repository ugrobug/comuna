"""Конвертация WordPress Gutenberg HTML → JSON Editor.js (blocks + additional)."""

from __future__ import annotations

import json
import re
import secrets
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlparse

LEGACY_SITE = "https://posletitrov.ru"

_GUTENBERG_BLOCK_RE = re.compile(
    r"<!--\s*wp:(?P<name>[\w/-]+)(?P<attrs>\s+\{.*?\})?\s*(?:/)?-->"
    r"(?P<body>.*?)"
    r"<!--\s*/wp:(?P=name)\s*-->",
    re.DOTALL | re.IGNORECASE,
)
_IFRAME_SRC_RE = re.compile(
    r'<iframe[^>]+src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_IMG_TAG_RE = re.compile(
    r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>',
    re.IGNORECASE,
)
_HEADING_TAG_RE = re.compile(
    r"<h([1-6])[^>]*>(.*?)</h\1>",
    re.DOTALL | re.IGNORECASE,
)


def _block_id() -> str:
    return secrets.token_hex(5)


def _strip_html_text(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_wp_attrs(attrs_raw: str | None) -> dict[str, Any]:
    if not attrs_raw:
        return {}
    raw = attrs_raw.strip()
    if not raw.startswith("{"):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _youtube_ids(url: str) -> tuple[str | None, str | None]:
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return None, None
    host = (parsed.netloc or "").lower().replace("www.", "")
    path = parsed.path or ""
    video_id: str | None = None
    if host in ("youtu.be",):
        video_id = path.strip("/").split("/")[0] or None
    elif host.endswith("youtube.com"):
        if path.startswith("/embed/"):
            video_id = path.split("/")[2] if len(path.split("/")) > 2 else None
        elif path.startswith("/shorts/"):
            video_id = path.split("/")[2] if len(path.split("/")) > 2 else None
        else:
            qs = parse_qs(parsed.query)
            video_id = (qs.get("v") or [None])[0]
    if not video_id or len(video_id) < 6:
        return None, None
    embed = f"https://www.youtube.com/embed/{video_id}"
    return video_id, embed


def _embed_block_from_url(url: str, caption: str = "") -> dict[str, Any]:
    url = (url or "").strip()
    _, yt_embed = _youtube_ids(url)
    if yt_embed:
        return {
            "id": _block_id(),
            "type": "embed",
            "data": {
                "service": "youtube",
                "source": url,
                "embed": yt_embed,
                "width": 580,
                "height": 320,
                "caption": caption,
            },
        }
    return {
        "id": _block_id(),
        "type": "embed",
        "data": {
            "service": "code",
            "source": url,
            "embed": url,
            "width": 580,
            "height": 320,
            "caption": caption,
        },
    }


def _paragraph_block(html: str) -> dict[str, Any]:
    body = (html or "").strip()
    if not body:
        return {}
    if not body.startswith("<"):
        body = f"<p>{body}</p>"
    return {"id": _block_id(), "type": "paragraph", "data": {"text": body}}


def _image_block_from_html(body: str, attrs: dict[str, Any]) -> dict[str, Any]:
    url = ""
    alt = ""
    caption = ""
    m = _IMG_TAG_RE.search(body or "")
    if m:
        url = m.group(1).strip()
        alt_m = re.search(r'alt=["\']([^"\']*)["\']', body, re.I)
        if alt_m:
            alt = alt_m.group(1)
    figcap = re.search(
        r"<figcaption[^>]*>(.*?)</figcaption>",
        body or "",
        re.DOTALL | re.IGNORECASE,
    )
    if figcap:
        caption = _strip_html_text(figcap.group(1))
    if not url and attrs.get("id"):
        caption = caption or f"wp-attachment:{attrs.get('id')}"
    if not url:
        return _paragraph_block(body) if body.strip() else {}
    data: dict[str, Any] = {
        "file": {"url": url},
        "url": url,
        "caption": caption,
        "withBorder": False,
        "withBackground": False,
        "stretched": False,
    }
    if alt:
        data["alt"] = alt
    return {"id": _block_id(), "type": "image", "data": data}


def _quote_block_from_html(body: str) -> dict[str, Any]:
    bq = re.search(
        r"<blockquote[^>]*>(.*?)</blockquote>",
        body or "",
        re.DOTALL | re.IGNORECASE,
    )
    inner = bq.group(1) if bq else (body or "")
    cite = re.search(
        r"<cite[^>]*>(.*?)</cite>",
        inner,
        re.DOTALL | re.IGNORECASE,
    )
    caption = _strip_html_text(cite.group(1)) if cite else ""
    text_html = inner
    if cite:
        text_html = inner.replace(cite.group(0), "")
    text_html = re.sub(
        r"</?cite[^>]*>",
        "",
        text_html,
        flags=re.IGNORECASE,
    ).strip()
    if not text_html and not caption:
        return {}
    return {
        "id": _block_id(),
        "type": "quote",
        "data": {
            "text": text_html.strip() or _strip_html_text(inner),
            "caption": caption,
            "authorName": "",
            "authorPhoto": "",
        },
    }


def _header_block_from_html(body: str, attrs: dict[str, Any]) -> dict[str, Any]:
    level = int(attrs.get("level") or attrs.get("Level") or 2)
    hm = _HEADING_TAG_RE.search(body or "")
    if hm:
        level = int(hm.group(1))
        text = _strip_html_text(hm.group(2))
    else:
        text = _strip_html_text(body)
    if not text:
        return {}
    level = min(max(level, 1), 6)
    return {
        "id": _block_id(),
        "type": "header",
        "data": {"text": text, "level": level},
    }


class _TableHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] | None = None
        self._cell_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "tr":
            self._current_row = []
        elif t in ("td", "th") and self._current_row is not None:
            self._cell_parts = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in ("td", "th") and self._current_row is not None:
            self._current_row.append(_strip_html_text("".join(self._cell_parts)))
            self._cell_parts = []
        elif t == "tr" and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data: str) -> None:
        if self._current_row is not None:
            self._cell_parts.append(data)


def _table_block_from_html(body: str) -> dict[str, Any]:
    parser = _TableHTMLParser()
    try:
        parser.feed(body or "")
    except Exception:
        return _paragraph_block(body) if body.strip() else {}
    rows = parser.rows
    if not rows:
        return _paragraph_block(body) if body.strip() else {}
    with_headings = any(
        re.search(r"<th[\s>]", body or "", re.IGNORECASE) for _ in [0]
    )
    return {
        "id": _block_id(),
        "type": "table",
        "data": {"withHeadings": with_headings, "content": rows},
    }


def _convert_gutenberg_block(name: str, attrs_raw: str | None, body: str) -> list[dict[str, Any]]:
    attrs = _parse_wp_attrs(attrs_raw)
    base_name = name.split("/")[-1].lower()
    body = body or ""

    if base_name in ("paragraph", "classic"):
        blk = _paragraph_block(body)
        return [blk] if blk else []

    if base_name == "image":
        blk = _image_block_from_html(body, attrs)
        return [blk] if blk else []

    if base_name == "embed":
        url = str(attrs.get("url") or "").strip()
        if not url:
            a = re.search(r'href=["\']([^"\']+)["\']', body, re.I)
            if a:
                url = a.group(1)
        if not url:
            iframe = _IFRAME_SRC_RE.search(body)
            if iframe:
                url = iframe.group(1)
        if url:
            return [_embed_block_from_url(url)]
        return _convert_freeform_html(body)

    if base_name == "quote":
        blk = _quote_block_from_html(body)
        return [blk] if blk else []

    if base_name == "heading":
        blk = _header_block_from_html(body, attrs)
        return [blk] if blk else []

    if base_name == "separator":
        return [{"id": _block_id(), "type": "divider", "data": {}}]

    if base_name == "table":
        blk = _table_block_from_html(body)
        return [blk] if blk else []

    if base_name in ("html", "freeform"):
        return _convert_freeform_html(body)

    if body.strip():
        return _convert_freeform_html(body)
    return []


def _convert_freeform_html(fragment: str) -> list[dict[str, Any]]:
    fragment = (fragment or "").strip()
    if not fragment:
        return []

    blocks: list[dict[str, Any]] = []
    for m in _IFRAME_SRC_RE.finditer(fragment):
        url = m.group(1).strip()
        if url:
            blocks.append(_embed_block_from_url(url))

    if blocks and _IFRAME_SRC_RE.sub("", fragment).strip() == "":
        return blocks

    if _HEADING_TAG_RE.search(fragment) and "<!-- wp:" not in fragment:
        for hm in _HEADING_TAG_RE.finditer(fragment):
            level = int(hm.group(1))
            text = _strip_html_text(hm.group(2))
            if text:
                blocks.append(
                    {
                        "id": _block_id(),
                        "type": "header",
                        "data": {"text": text, "level": level},
                    }
                )
        if blocks:
            return blocks

    blk = _paragraph_block(fragment)
    return [blk] if blk else []


def gutenberg_to_editor_payload(
    post_content: str,
    *,
    post_excerpt: str = "",
    include_toc: bool = False,
) -> dict[str, Any]:
    """Возвращает {blocks: [...], additional: {...}}."""
    raw = post_content or ""
    blocks: list[dict[str, Any]] = []

    if include_toc:
        blocks.append({"id": _block_id(), "type": "toc", "data": {}})

    if "<!-- wp:" in raw:
        pos = 0
        for m in _GUTENBERG_BLOCK_RE.finditer(raw):
            prefix = raw[pos:m.start()]
            blocks.extend(_convert_freeform_html(prefix))
            blocks.extend(
                _convert_gutenberg_block(m.group("name"), m.group("attrs"), m.group("body"))
            )
            pos = m.end()
        blocks.extend(_convert_freeform_html(raw[pos:]))
    else:
        blocks.extend(_convert_freeform_html(raw))

    blocks = [b for b in blocks if b]

    additional: dict[str, Any] = {}
    excerpt = _strip_html_text(post_excerpt or "")
    if excerpt:
        additional["previewDescription"] = excerpt

    payload: dict[str, Any] = {"blocks": blocks}
    if additional:
        payload["additional"] = additional
    return payload


def editor_payload_to_content_string(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def legacy_article_source_url(slug: str, guid: str = "") -> str:
    slug = (slug or "").strip().strip("/")
    guid = (guid or "").strip()
    if guid.startswith("http") and slug and slug in guid:
        return guid[:255]
    if slug:
        return f"{LEGACY_SITE}/articles/{slug}/"[:255]
    return guid[:255] if guid else ""
