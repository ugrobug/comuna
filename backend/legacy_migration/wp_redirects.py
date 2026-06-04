"""Сборка редиректов ПТ → Comuna из LegacyWpPostMap и зеркала WP."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import unquote, urlparse

from django.utils.text import slugify

from feeds.models import Post
from legacy_migration.models import LegacyWpPostMap, WpPostmeta, WpPosts
from legacy_migration.wp_content import legacy_article_source_url
from legacy_migration.wp_content_rewrites import post_public_path

_CANONICAL_META_KEYS = (
    "_yoast_wpseo_canonical",
    "rank_math_canonical_url",
)


@dataclass
class RedirectRow:
    from_path: str
    to_path: str
    wp_post_id: int
    post_id: int
    source: str = ""


@dataclass
class RedirectBuildResult:
    rows: list[RedirectRow] = field(default_factory=list)
    skipped_no_post: int = 0
    conflicts: list[str] = field(default_factory=list)


def normalize_legacy_path(value: str) -> str:
    """Только path, без query/fragment, с ведущим слэшем."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        path = parsed.path or ""
    elif raw.startswith("/"):
        path = raw.split("?", 1)[0].split("#", 1)[0]
    else:
        path = "/" + raw.split("?", 1)[0].split("#", 1)[0]
    path = unquote(path)
    if not path.startswith("/"):
        path = "/" + path
    path = path.rstrip("/") or "/"
    return path


def path_variants(path: str) -> list[str]:
    path = normalize_legacy_path(path)
    if not path or path == "/":
        return []
    if path.endswith("/"):
        return [path.rstrip("/") or "/", path]
    return [path, f"{path}/"]


def _legacy_url_paths(legacy_url: str) -> list[str]:
    return path_variants(normalize_legacy_path(legacy_url))


def _paths_from_wp_post(wp_post: WpPosts) -> list[str]:
    slug = (wp_post.post_name or "").strip()
    paths: list[str] = []
    for url in (
        legacy_article_source_url(slug, wp_post.guid or ""),
        (wp_post.guid or "").strip(),
    ):
        if not url:
            continue
        if url.startswith("http"):
            p = normalize_legacy_path(url)
            if p and p != "/":
                paths.append(p)
    if slug:
        paths.append(normalize_legacy_path(f"/articles/{slug}/"))
    return paths


def _canonical_paths(wp_post_id: int) -> list[str]:
    metas = WpPostmeta.objects.filter(
        post_id=wp_post_id,
        meta_key__in=_CANONICAL_META_KEYS,
    ).exclude(meta_value="")
    paths: list[str] = []
    for meta in metas:
        val = (meta.meta_value or "").strip()
        if val.startswith("http"):
            p = normalize_legacy_path(val)
            if p and p != "/":
                paths.append(p)
    return paths


def collect_redirect_rows(
    maps: Iterable[LegacyWpPostMap],
    *,
    include_wp_guid: bool = True,
    include_canonical_meta: bool = True,
    include_slug_fallback: bool = True,
) -> RedirectBuildResult:
    result = RedirectBuildResult()
    seen_dest: dict[str, tuple[str, int]] = {}
    rows_by_path: dict[str, RedirectRow] = {}

    wp_ids = [int(m.wp_post_id) for m in maps if m.post_id]
    wp_by_id: dict[int, WpPosts] = {}
    if include_wp_guid and wp_ids:
        wp_by_id = {int(p.id): p for p in WpPosts.objects.filter(id__in=wp_ids)}

    for map_row in maps:
        if not map_row.post_id or not map_row.post:
            result.skipped_no_post += 1
            continue
        post = map_row.post
        dest = post_public_path(post)
        wp_id = int(map_row.wp_post_id)

        sources: list[tuple[str, str]] = []
        if map_row.legacy_url:
            for p in _legacy_url_paths(map_row.legacy_url):
                sources.append((p, "legacy_url"))
        wp_post = wp_by_id.get(wp_id)
        if wp_post:
            for p in _paths_from_wp_post(wp_post):
                sources.append((p, "wp_guid"))
        if include_canonical_meta:
            for p in _canonical_paths(wp_id):
                sources.append((p, "canonical_meta"))
        if include_slug_fallback and map_row.legacy_slug:
            p = normalize_legacy_path(f"/articles/{map_row.legacy_slug}/")
            sources.append((p, "slug_fallback"))

        for from_path, source in sources:
            for variant in path_variants(from_path):
                key = variant
                prev = seen_dest.get(key)
                if prev and prev[0] != dest:
                    result.conflicts.append(
                        f"{key!r}: post {prev[1]} ({prev[0]}) vs post {post.id} ({dest})"
                    )
                    continue
                seen_dest[key] = (dest, int(post.id))
                if key not in rows_by_path:
                    rows_by_path[key] = RedirectRow(
                        from_path=variant,
                        to_path=dest,
                        wp_post_id=wp_id,
                        post_id=int(post.id),
                        source=source,
                    )

    result.rows = sorted(rows_by_path.values(), key=lambda r: (r.from_path, r.post_id))
    return result


def format_nginx_map(rows: list[RedirectRow], *, map_name: str = "pt_legacy_post_redirect") -> str:
    lines = [
        f"# Сгенерировано export_wp_redirects, строк: {len(rows)}",
        f"map $uri ${map_name} {{",
        '    default "";',
    ]
    emitted: set[str] = set()
    for row in rows:
        if row.from_path in emitted:
            continue
        emitted.add(row.from_path)
        lines.append(f"    {row.from_path} {row.to_path};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def format_csv(rows: list[RedirectRow]) -> str:
    lines = ["from_path,to_path,wp_post_id,post_id,source"]
    for row in rows:
        lines.append(
            f"{row.from_path},{row.to_path},{row.wp_post_id},{row.post_id},{row.source}"
        )
    return "\n".join(lines) + "\n"


def format_json(rows: list[RedirectRow]) -> str:
    payload = [
        {
            "from": r.from_path,
            "to": r.to_path,
            "wp_post_id": r.wp_post_id,
            "post_id": r.post_id,
            "source": r.source,
        }
        for r in rows
    ]
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
