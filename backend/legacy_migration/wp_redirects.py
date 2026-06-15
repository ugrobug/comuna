"""Сборка редиректов ПТ → Comuna из LegacyWpPostMap и зеркала WP."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import quote, unquote, urlparse

from feeds.models import Post, Tag, _lemmatize_tag
from legacy_migration.models import (
    LegacyWpPostMap,
    WpPostmeta,
    WpPosts,
    WpTermRelationships,
    WpTermTaxonomy,
    WpTerms,
)
from legacy_migration.wp_content import LEGACY_SITE, legacy_article_source_url
from legacy_migration.wp_content_rewrites import post_public_path

_CANONICAL_META_KEYS = (
    "_yoast_wpseo_canonical",
    "rank_math_canonical_url",
)


@dataclass
class RedirectRow:
    from_path: str
    to_path: str
    wp_post_id: int = 0
    post_id: int = 0
    wp_term_id: int = 0
    source: str = ""


@dataclass
class RedirectBuildResult:
    rows: list[RedirectRow] = field(default_factory=list)
    skipped_no_post: int = 0
    conflicts: list[str] = field(default_factory=list)


@dataclass
class TagRedirectBuildResult:
    rows: list[RedirectRow] = field(default_factory=list)
    skipped_no_slug: int = 0
    skipped_no_dest: int = 0
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


def tambur_tag_url_key(wp_name: str) -> str:
    """Ключ для /tags/{key} — как на фронте (normalizeTag от lemma/name)."""
    stored = (wp_name or "").strip()[:64]
    if not stored:
        return ""
    tag = Tag.objects.filter(name__iexact=stored).order_by("id").first()
    if tag:
        raw = (tag.lemma or _lemmatize_tag(tag.name) or tag.name).strip()
    else:
        raw = (_lemmatize_tag(stored) or stored).strip()
    return raw.lower()


def tag_public_path(wp_name: str) -> str:
    key = tambur_tag_url_key(wp_name)
    if not key:
        return ""
    return f"/tags/{quote(key, safe='')}"


def collect_tag_redirect_rows(
    *,
    mapped_wp_post_ids: list[int] | None = None,
    min_term_count: int = 1,
) -> TagRedirectBuildResult:
    """
    /tag/{wp_slug}/ → /tags/{lemma-key}/ на Tambur.
    slug из wp_terms; цель — lemma/name как у import_wp_post_tags (slug в Tag не пишем).
    """
    result = TagRedirectBuildResult()
    seen_dest: dict[str, str] = {}
    rows_by_path: dict[str, RedirectRow] = {}

    tt_qs = WpTermTaxonomy.objects.filter(taxonomy="post_tag")
    if min_term_count > 0:
        tt_qs = tt_qs.filter(count__gte=min_term_count)

    if mapped_wp_post_ids is not None:
        if not mapped_wp_post_ids:
            return result
        rel_tt_ids = (
            WpTermRelationships.objects.filter(object_id__in=mapped_wp_post_ids)
            .values_list("term_taxonomy_id", flat=True)
            .distinct()
        )
        tt_qs = tt_qs.filter(term_taxonomy_id__in=rel_tt_ids)

    term_ids = list(tt_qs.values_list("term_id", flat=True).distinct())
    if not term_ids:
        return result

    for term in WpTerms.objects.filter(term_id__in=term_ids).order_by("slug"):
        slug = (term.slug or "").strip()
        if not slug:
            result.skipped_no_slug += 1
            continue
        dest = tag_public_path(term.name or "")
        if not dest:
            result.skipped_no_dest += 1
            continue
        term_id = int(term.term_id)
        from_base = normalize_legacy_path(f"/tag/{slug}")
        for variant in path_variants(from_base):
            key = variant
            prev = seen_dest.get(key)
            if prev and prev != dest:
                result.conflicts.append(f"{key!r}: tag dest {prev!r} vs {dest!r}")
                continue
            seen_dest[key] = dest
            if key not in rows_by_path:
                rows_by_path[key] = RedirectRow(
                    from_path=variant,
                    to_path=dest,
                    wp_term_id=term_id,
                    source="post_tag",
                )

    result.rows = sorted(rows_by_path.values(), key=lambda r: r.from_path)
    return result


def merge_redirect_rows(
    post_rows: list[RedirectRow],
    tag_rows: list[RedirectRow],
) -> tuple[list[RedirectRow], list[str]]:
    """Объединить статьи и теги; при коллизии from_path приоритет у статьи."""
    by_path: dict[str, RedirectRow] = {}
    conflicts: list[str] = []
    for row in tag_rows:
        by_path[row.from_path] = row
    for row in post_rows:
        prev = by_path.get(row.from_path)
        if prev and prev.to_path != row.to_path:
            conflicts.append(
                f"{row.from_path!r}: post → {row.to_path!r} vs tag → {prev.to_path!r} (post wins)"
            )
        by_path[row.from_path] = row
    merged = sorted(by_path.values(), key=lambda r: (r.from_path, r.post_id, r.wp_term_id))
    return merged, conflicts


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


def _absolute_url(base: str, path: str) -> str:
    base = (base or "").strip().rstrip("/")
    path = normalize_legacy_path(path)
    if not path or path == "/":
        return base
    return f"{base}{path}"


def _redirection_plugin_metas() -> dict:
    """Шаблон metas как в нативном Export плагина Redirection (John Godley)."""
    return {
        "ignore_trailing_slashes": "1",
        "ignore_parameters": "1",
        "ignore_case": "1",
        "pass_on_parameters": "",
        "redirect_code": "301",
        "inclusion_exclusion_rules": "",
        "redirect_options": "are_case",
        "redirection_http_headers": "",
        "rules_group1": {"enabled": "0", "login_info": ""},
        "rules_group2": {"enabled": "0", "role": "", "role_name": "[]"},
        "rules_group3": {
            "enabled": "0",
            "referrer": "",
            "referrer_value": "",
            "referrer_regex": "0",
        },
        "rules_group4": {
            "enabled": "0",
            "agent": "",
            "agent_value": "",
            "agent_regex": "0",
        },
        "rules_group5": {
            "enabled": "0",
            "cookie": "",
            "cookie_name": "",
            "cookie_value": "",
            "cookie_regex": "0",
        },
        "rules_group6": {"enabled": "0", "ip": "", "ip_value": ""},
        "rules_group7": {"enabled": "0", "server": "", "server_value": ""},
        "rules_group8": {"enabled": "0", "language": "", "language_value": ""},
    }


def _dedupe_rows_by_normalized_path(rows: list[RedirectRow]) -> list[RedirectRow]:
    """Один redirect на путь; trailing slash покрывается metas.ignore_trailing_slashes."""
    by_path: dict[str, RedirectRow] = {}
    for row in rows:
        key = normalize_legacy_path(row.from_path)
        if not key or key == "/":
            continue
        if key not in by_path:
            by_path[key] = row
    return list(by_path.values())


def format_redirection_plugin_json(
    rows: list[RedirectRow],
    *,
    pt_base_url: str = LEGACY_SITE,
    tambur_base_url: str = "https://tambur.pub",
) -> str:
    """
    JSON для импорта в WP-плагин Redirection (Список для импорта).
    Структура как в Export: {"redirect": {...}, "metas": {...}}.
    """
    pt_base = (pt_base_url or LEGACY_SITE).strip().rstrip("/")
    metas = _redirection_plugin_metas()
    items: list[dict] = []
    for row in _dedupe_rows_by_normalized_path(rows):
        match_path = normalize_legacy_path(row.from_path)
        to_url = _absolute_url(tambur_base_url, row.to_path)
        items.append(
            {
                "redirect": {
                    "from": f"{pt_base}{match_path}",
                    "match": match_path,
                    "to": to_url,
                    "status": "1",
                    "type": "redirection",
                },
                "metas": metas,
            }
        )
    return json.dumps(items, ensure_ascii=False, indent=2) + "\n"


def format_redirection_plugin_csv(
    rows: list[RedirectRow],
    *,
    pt_base_url: str = LEGACY_SITE,
    tambur_base_url: str = "https://tambur.pub",
) -> str:
    """CSV для Redirection: source,target,regex,code (полные URL, как в импорте плагина)."""
    pt_base = (pt_base_url or LEGACY_SITE).strip().rstrip("/")
    lines = ["source,target,regex,code"]
    for row in _dedupe_rows_by_normalized_path(rows):
        match_path = normalize_legacy_path(row.from_path)
        source = f"{pt_base}{match_path}"
        target = _absolute_url(tambur_base_url, row.to_path)
        src = source.replace(",", "%2C")
        tgt = target.replace(",", "%2C")
        lines.append(f"{src},{tgt},0,301")
    return "\n".join(lines) + "\n"
