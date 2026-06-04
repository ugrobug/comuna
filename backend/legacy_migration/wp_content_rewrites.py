"""Переписывание внутренних ссылок ПТ в Post.content (post_link, author, URL)."""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from html import unescape
from typing import Any

from django.utils.text import slugify

from feeds.models import Author, Post
from legacy_migration.models import LegacyWpPostMap, LegacyWpUserMap

_ARTICLE_HREF_RE = re.compile(
    r"""<a\s+[^>]*href=["'](?:https?://(?:www\.)?posletitrov\.ru)?(/articles/[^"'#?\s]+)/?[^"']*["'][^>]*>(.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)
_AUTHOR_HREF_RE = re.compile(
    r"""<a\s+[^>]*href=["'](?:https?://(?:www\.)?posletitrov\.ru)?/author/([^/"']+)/?[^"']*["'][^>]*>(.*?)</a>""",
    re.IGNORECASE | re.DOTALL,
)
def _block_id() -> str:
    return secrets.token_hex(5)


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", unescape(text)).strip()


def post_public_path(post: Post) -> str:
    title = (post.title or "").strip()
    slug = slugify(title)[:80] if title else ""
    return f"/b/post/{post.id}-{slug}" if slug else f"/b/post/{post.id}"


def _extract_article_slug(path: str) -> str:
    parts = [p for p in (path or "").strip("/").split("/") if p]
    if not parts or parts[0] != "articles":
        return ""
    return parts[-1]


def _resolve_post_by_article_path(path: str) -> Post | None:
    slug = _extract_article_slug(path)
    if not slug:
        return None
    map_row = (
        LegacyWpPostMap.objects.filter(legacy_slug__iexact=slug)
        .select_related("post", "post__author")
        .first()
    )
    if map_row and map_row.post_id:
        return map_row.post
    return None


def _build_post_link_block(target: Post, *, announcement: str = "") -> dict[str, Any]:
    author = target.author
    snapshot = {
        "post_id": int(target.id),
        "path": post_public_path(target),
        "title": (target.title or "").strip()[:255] or f"Материал #{target.id}",
        "author_title": (author.title or author.username or "").strip() if author else "",
        "author_username": (author.username or "").strip() if author else "",
    }
    try:
        payload = json.loads((target.content or "").strip())
        additional = payload.get("additional") if isinstance(payload, dict) else {}
        if isinstance(additional, dict):
            prev = (additional.get("previewDescription") or "").strip()
            img = (additional.get("previewImage") or "").strip()
            if prev:
                snapshot["preview_text"] = prev[:180]
            if img:
                snapshot["preview_image_url"] = img
    except json.JSONDecodeError:
        pass

    return {
        "id": _block_id(),
        "type": "post_link",
        "data": {
            "url": snapshot["path"],
            "announcement": (announcement or "").strip(),
            "post_id": snapshot["post_id"],
            "snapshot": snapshot,
        },
    }


def _resolve_author_by_wp_slug(slug: str) -> Author | None:
    slug = (slug or "").strip()
    if not slug:
        return None
    map_row = (
        LegacyWpUserMap.objects.filter(wp_login__iexact=slug)
        .select_related("author")
        .first()
    )
    if map_row and map_row.author_id:
        return map_row.author
    author = Author.objects.filter(username__iexact=slug).first()
    if author:
        return author
    return Author.objects.filter(username__iexact=slugify(slug)).first()


def _build_author_block(author: Author, *, caption: str = "") -> dict[str, Any]:
    username = (author.username or "").strip()
    title = (author.title or username).strip()
    snapshot = {
        "username": username,
        "title": title,
        "path": f"/{username}" if username else "",
        "avatar_url": "",
    }
    return {
        "id": _block_id(),
        "type": "author",
        "data": {
            "caption": (caption or "").strip(),
            "username": username,
            "snapshot": snapshot,
        },
    }


def _replace_article_urls_in_text(text: str, cache: dict[str, str]) -> str:
    def sub_href(match: re.Match[str]) -> str:
        path = match.group(2)
        key = path.rstrip("/")
        if key not in cache:
            post = _resolve_post_by_article_path(path)
            cache[key] = post_public_path(post) if post else ""
        if cache[key]:
            return f'href="{cache[key]}"'
        return match.group(0)

    return re.sub(
        r'href=["\'](https?://(?:www\.)?posletitrov\.ru)(/articles/[^"\']+)["\']',
        sub_href,
        text,
        flags=re.I,
    )


@dataclass
class RewriteStats:
    post_links: int = 0
    authors: int = 0
    url_replacements: int = 0


def _rewrite_paragraph_html(
    html: str,
    stats: RewriteStats,
    cache: dict[str, str],
    *,
    convert_post_link: bool,
    convert_author: bool,
    replace_urls: bool,
) -> list[dict[str, Any]]:
    raw = (html or "").strip()
    if not raw:
        return []

    blocks: list[dict[str, Any]] = []

    if convert_author:
        for m in _AUTHOR_HREF_RE.finditer(raw):
            wp_slug = (m.group(1) or "").strip()
            caption = _strip_html(m.group(2) or "")
            author = _resolve_author_by_wp_slug(wp_slug)
            if (
                author
                and len(_AUTHOR_HREF_RE.findall(raw)) == 1
                and _strip_html(raw.replace(m.group(0), "")) == ""
            ):
                blocks.append(_build_author_block(author, caption=caption))
                stats.authors += 1
                return blocks

    article_links = list(_ARTICLE_HREF_RE.finditer(raw))
    if convert_post_link and len(article_links) == 1:
        m = article_links[0]
        path = m.group(1) or ""
        link_text = _strip_html(m.group(2) or "")
        before = raw[: m.start()]
        after = raw[m.end() :]
        extra = _strip_html(before + after)
        post = _resolve_post_by_article_path(path)
        if post:
            if extra and not _strip_html(link_text):
                announcement = extra
            elif extra:
                announcement = extra
            else:
                announcement = link_text if link_text.lower() not in ("читать", "далее", "подробнее") else ""
            blocks.append(_build_post_link_block(post, announcement=announcement))
            stats.post_links += 1
            return blocks

    if replace_urls:
        new_html = _replace_article_urls_in_text(raw, cache)
        if new_html != raw:
            stats.url_replacements += 1
            raw = new_html

    if raw:
        blocks.append({"id": _block_id(), "type": "paragraph", "data": {"text": raw}})
    return blocks


def _rewrite_block(
    block: dict[str, Any],
    stats: RewriteStats,
    cache: dict[str, str],
    *,
    convert_post_link: bool,
    convert_author: bool,
    replace_urls: bool,
) -> list[dict[str, Any]]:
    btype = str(block.get("type") or "").lower()
    data = block.get("data") if isinstance(block.get("data"), dict) else {}

    if btype == "paragraph":
        text = str(data.get("text") or "")
        return (
            _rewrite_paragraph_html(
                text,
                stats,
                cache,
                convert_post_link=convert_post_link,
                convert_author=convert_author,
                replace_urls=replace_urls,
            )
            or [block]
        )

    if btype in ("quote",) and replace_urls:
        text = str(data.get("text") or "")
        new_text = _replace_article_urls_in_text(text, cache)
        if new_text != text:
            stats.url_replacements += 1
            out = dict(block)
            out["data"] = {**data, "text": new_text}
            return [out]
    return [block]


def rewrite_post_content_string(
    content: str,
    *,
    convert_post_link: bool = True,
    convert_author: bool = True,
    replace_urls: bool = True,
) -> tuple[str, RewriteStats]:
    """Возвращает новый JSON content и статистику."""
    stats = RewriteStats()
    raw = (content or "").strip()
    if not raw.startswith("{"):
        return content, stats
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return content, stats
    if not isinstance(payload, dict):
        return content, stats

    blocks = payload.get("blocks")
    if not isinstance(blocks, list):
        return content, stats

    cache: dict[str, str] = {}
    new_blocks: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, dict):
            new_blocks.append(block)
            continue

        rewritten = _rewrite_block(
            block,
            stats,
            cache,
            convert_post_link=convert_post_link,
            convert_author=convert_author,
            replace_urls=replace_urls,
        )
        new_blocks.extend(rewritten)

    payload["blocks"] = new_blocks
    return json.dumps(payload, ensure_ascii=False), stats
