"""Врезка (post_excerpt) и обложка (_thumbnail_id) для уже импортированных Post."""

from __future__ import annotations

import json
from typing import Any

from feeds.models import Post

from legacy_migration.wp_content import (
    editor_payload_to_content_string,
    gutenberg_to_editor_payload,
)
from legacy_migration.wp_media import (
    legacy_media_use_object_storage,
    target_public_url,
    wp_thumbnail_attachment_url,
    wp_url_to_storage_path,
)
from legacy_migration.legacy_posts import wp_has_ez_toc


def _load_content_payload(post: Post) -> dict[str, Any]:
    raw = (post.content or "").strip()
    if not raw.startswith("{"):
        return {"blocks": [], "additional": {}}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"blocks": [], "additional": {}}
    if not isinstance(data, dict):
        return {"blocks": [], "additional": {}}
    return data


def apply_post_excerpt(post: Post, *, post_excerpt: str, wp_post_id: int) -> bool:
    """Обновить additional.previewDescription из wp_posts.post_excerpt."""
    payload = _load_content_payload(post)
    include_toc = any(
        isinstance(b, dict) and b.get("type") == "toc" for b in (payload.get("blocks") or [])
    )
    if not include_toc:
        include_toc = wp_has_ez_toc(wp_post_id)

    rebuilt = gutenberg_to_editor_payload(
        "",
        post_excerpt=post_excerpt,
        include_toc=include_toc,
    )
    excerpt = (rebuilt.get("additional") or {}).get("previewDescription") or ""
    additional = dict(payload.get("additional") or {})
    if excerpt:
        additional["previewDescription"] = excerpt
    elif "previewDescription" in additional:
        del additional["previewDescription"]

    if not excerpt and not additional.get("previewDescription"):
        return False

    payload["additional"] = additional
    post.content = editor_payload_to_content_string(payload)
    return True


def apply_post_cover(
    post: Post,
    *,
    wp_post_id: int,
    backend_base: str = "",
    relative_urls: bool | None = None,
) -> str | None:
    """
    Записать additional.previewImage из _thumbnail_id.
    URL без скачивания файла (mirror_wp_post_media докачает файл).
    """
    thumb_url = wp_thumbnail_attachment_url(wp_post_id)
    if not thumb_url:
        return None

    storage_path = wp_url_to_storage_path(thumb_url)
    if not storage_path:
        return None

    if relative_urls is None:
        relative_urls = not legacy_media_use_object_storage()

    public_url = target_public_url(
        storage_path,
        backend_base=backend_base,
        relative_urls=relative_urls,
    )

    payload = _load_content_payload(post)
    additional = dict(payload.get("additional") or {})
    additional["previewImage"] = public_url
    payload["additional"] = additional
    post.content = editor_payload_to_content_string(payload)

    raw = dict(post.raw_data or {})
    raw["legacy_cover_url"] = public_url
    post.raw_data = raw
    return public_url
