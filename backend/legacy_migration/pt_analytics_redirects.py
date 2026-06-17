"""Доп. редиректы из CSV просмотров Метрики: URL с вложенным path → пост Tambur."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from feeds.post_paths import build_post_public_path
from legacy_migration.models import LegacyWpPostMap, WpPosts
from legacy_migration.wp_content import LEGACY_SITE
from legacy_migration.wp_redirects import (
    RedirectBuildResult,
    RedirectRow,
    collect_redirect_rows,
    normalize_legacy_path,
    path_variants,
    redirection_plugin_items,
)

_PT_HOST_SUFFIXES = ("posletitrov.ru", "www.posletitrov.ru")

# Архивы / пагинация — отдельные json или не статьи
_SKIP_PATH_RE = re.compile(
    r"""
    ^/articles/movies/page/\d+/?$|
    ^/articles/tv-series/page/\d+/?$|
    ^/articles/(movies|tv-series|interview)/?$
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass
class AnalyticsRedirectBuildResult:
    rows: list[RedirectRow] = field(default_factory=list)
    csv_urls_total: int = 0
    pt_urls: int = 0
    skipped_pattern: int = 0
    skipped_already_exported: int = 0
    skipped_no_post: int = 0
    unresolved_samples: list[str] = field(default_factory=list)


def _is_posletitrov_url(url: str) -> bool:
    raw = (url or "").strip().strip('"')
    if not raw.startswith("http"):
        return False
    host = (urlparse(raw).netloc or "").lower()
    return any(host == h or host.endswith("." + h) for h in _PT_HOST_SUFFIXES)


def parse_analytics_csv_urls(path: Path, *, min_views: int = 1) -> list[tuple[str, int]]:
    """(нормализованный path, просмотры) уникально по path."""
    by_path: dict[str, int] = {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            url = (row[0] or "").strip().strip('"')
            try:
                views = int((row[1] or "0").strip().strip('"'))
            except ValueError:
                views = 0
            if views < min_views or not _is_posletitrov_url(url):
                continue
            p = normalize_legacy_path(url)
            if not p or p == "/":
                continue
            by_path[p] = by_path.get(p, 0) + views
    return sorted(by_path.items(), key=lambda x: (-x[1], x[0]))


def slug_tail_from_pt_path(path: str) -> str:
    """Последний сегмент ЧПУ статьи/новости (не page/N)."""
    norm = normalize_legacy_path(path)
    parts = [s for s in norm.strip("/").split("/") if s]
    if not parts:
        return ""
    if len(parts) >= 2 and parts[-2].lower() == "page" and parts[-1].isdigit():
        return ""
    last = parts[-1]
    if last.isdigit() and len(parts) >= 2 and parts[-2].lower() == "page":
        return ""
    return last


def load_exported_from_paths(json_path: Path) -> set[str]:
    """Нормализованные match-path из pt-redirection-full.json."""
    data = json.loads(json_path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for item in data:
        redirect = item.get("redirect") or {}
        match = redirect.get("match") or redirect.get("from") or ""
        p = normalize_legacy_path(str(match))
        if p and p != "/":
            out.add(p)
            for v in path_variants(p):
                out.add(normalize_legacy_path(v))
    return out


def paths_covered_by_standard_export() -> set[str]:
    maps = LegacyWpPostMap.objects.filter(post_id__isnull=False).select_related("post")
    built: RedirectBuildResult = collect_redirect_rows(maps)
    covered: set[str] = set()
    for row in built.rows:
        for v in path_variants(row.from_path):
            covered.add(normalize_legacy_path(v))
    return covered


def resolve_map_for_pt_path(path: str) -> LegacyWpPostMap | None:
    norm = normalize_legacy_path(path)
    slug = slug_tail_from_pt_path(norm)
    if not slug:
        return None

    for map_row in LegacyWpPostMap.objects.filter(legacy_slug__iexact=slug).select_related("post"):
        if map_row.post_id:
            return map_row

    wp = (
        WpPosts.objects.filter(post_name__iexact=slug, post_type="post", post_status="publish")
        .order_by("-id")
        .first()
    )
    if wp:
        map_row = LegacyWpPostMap.objects.filter(wp_post_id=wp.id, post_id__isnull=False).first()
        if map_row:
            return map_row
    return None


def build_analytics_supplement_rows(
    csv_path: Path,
    *,
    min_views: int = 1,
    existing_json: Path | None = None,
    use_db_export_paths: bool = True,
) -> AnalyticsRedirectBuildResult:
    result = AnalyticsRedirectBuildResult()
    covered: set[str] = set()
    if existing_json and existing_json.is_file():
        covered |= load_exported_from_paths(existing_json)
    if use_db_export_paths:
        covered |= paths_covered_by_standard_export()

    seen_from: set[str] = set()
    urls = parse_analytics_csv_urls(csv_path, min_views=min_views)
    result.csv_urls_total = len(urls)

    for path, _views in urls:
        result.pt_urls += 1
        if _SKIP_PATH_RE.match(path):
            result.skipped_pattern += 1
            continue
        if path in covered:
            result.skipped_already_exported += 1
            continue

        map_row = resolve_map_for_pt_path(path)
        if not map_row or not map_row.post:
            result.skipped_no_post += 1
            if len(result.unresolved_samples) < 30:
                result.unresolved_samples.append(path)
            continue

        post = map_row.post
        dest = build_post_public_path(post.id, post.title)
        key = normalize_legacy_path(path)
        if key in seen_from:
            continue
        seen_from.add(key)
        result.rows.append(
            RedirectRow(
                from_path=key,
                to_path=dest,
                wp_post_id=int(map_row.wp_post_id),
                post_id=int(post.id),
                source="analytics_csv",
            )
        )

    result.rows.sort(key=lambda r: r.from_path)
    return result


def format_analytics_supplement_json(
    rows: list[RedirectRow],
    *,
    tambur_base_url: str = "https://tambur.pub",
    compact: bool = False,
) -> str:
    items = redirection_plugin_items(rows, tambur_base_url=tambur_base_url)
    if compact:
        return json.dumps(items, ensure_ascii=False, separators=(",", ":")) + "\n"
    return json.dumps(items, ensure_ascii=False, indent=2) + "\n"
