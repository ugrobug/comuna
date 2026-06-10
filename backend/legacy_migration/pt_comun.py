"""Правила ПТ → коммуна «После Титров» и внутренние категории Tambur."""

from __future__ import annotations

from dataclasses import dataclass

from legacy_migration.models import LegacyWpPostMap, WpPosts
from legacy_migration.wp_content import legacy_article_source_url
from legacy_migration.wp_redirects import normalize_legacy_path
from legacy_migration.wp_post_tags import wp_post_tag_names

# Сообщество на prod: https://tambur.pub/comuns/after_the_credits
PT_COMUN_SLUG = "after_the_credits"

def merge_pt_comun_manual_membership_raw(
    raw: dict | None,
    *,
    comun_slug: str = PT_COMUN_SLUG,
) -> dict:
    """
    raw_data для попадания импортированной статьи ПТ в ленту коммуны
    (_comun_manual_posts_filter), с сохранением следов WP-миграции.
    """
    base = dict(raw) if isinstance(raw, dict) else {}
    base["source"] = "manual_comun"
    base["comun_slug"] = comun_slug
    if "migration_origin" not in base and (
        base.get("legacy_wp_id") is not None or base.get("legacy_slug")
    ):
        base["migration_origin"] = "wordpress"
    return base


# ComunCategory.slug внутри коммуны (?category=filmy на сайте)
CATEGORY_SLUG_FILMY = "filmy"
CATEGORY_SLUG_SERIALY = "serialy"
CATEGORY_SLUG_ANIMATSIYA = "animatsiya"

PT_CATEGORY_SLUGS = (
    CATEGORY_SLUG_FILMY,
    CATEGORY_SLUG_SERIALY,
    CATEGORY_SLUG_ANIMATSIYA,
)

_PATH_TAG_INTERVIEW = "interview"
_PATH_TAG_QUIZ = "quiz"

_ANIMATION_TAG_HINTS = ("аниме", "мультфильм", "анимация", "anime", "cartoon")


@dataclass
class PtComunDecision:
    comun_slug: str
    category_slug: str
    legacy_pt_path: str
    wp_subsection: str = ""
    extra_tag_slugs: tuple[str, ...] = ()
    reason: str = ""


def legacy_pt_path_for_map(
    map_row: LegacyWpPostMap,
    wp_post: WpPosts | None = None,
) -> str:
    if map_row.legacy_url:
        path = normalize_legacy_path(map_row.legacy_url)
        if path and path != "/":
            return path
    if wp_post:
        url = legacy_article_source_url(
            (wp_post.post_name or "").strip(),
            wp_post.guid or "",
        )
        if url:
            path = normalize_legacy_path(url)
            if path and path != "/":
                return path
    slug = (map_row.legacy_slug or "").strip()
    if slug:
        return normalize_legacy_path(f"/articles/{slug}/")
    return ""


def _path_segments(path: str) -> list[str]:
    return [s for s in (path or "").strip("/").lower().split("/") if s]


def _wp_subsection_from_path(segs: list[str]) -> str:
    if len(segs) >= 3 and segs[0] == "articles" and segs[1] in (
        "movies",
        "tv-series",
        "interview",
    ):
        return segs[2]
    return ""


def _tag_names_suggest_animation(wp_post_id: int) -> bool:
    for name in wp_post_tag_names(wp_post_id):
        low = name.casefold()
        if any(hint in low for hint in _ANIMATION_TAG_HINTS):
            return True
    return False


def _decision(
    category_slug: str,
    path: str,
    *,
    wp_subsection: str = "",
    extra_tags: tuple[str, ...] = (),
    reason: str,
) -> PtComunDecision:
    return PtComunDecision(
        comun_slug=PT_COMUN_SLUG,
        category_slug=category_slug,
        legacy_pt_path=path,
        wp_subsection=wp_subsection,
        extra_tag_slugs=extra_tags,
        reason=reason,
    )


def decide_pt_comun(
    legacy_pt_path: str,
    *,
    wp_post_id: int | None = None,
) -> PtComunDecision:
    path = normalize_legacy_path(legacy_pt_path)
    segs = _path_segments(path)
    extra_tags: list[str] = []

    if _PATH_TAG_INTERVIEW in segs:
        extra_tags.append(_PATH_TAG_INTERVIEW)
    if _PATH_TAG_QUIZ in segs or (segs and segs[-1] == "quiz"):
        extra_tags.append(_PATH_TAG_QUIZ)

    wp_sub = _wp_subsection_from_path(segs)
    tags_tuple = tuple(extra_tags)

    if wp_post_id and _tag_names_suggest_animation(wp_post_id):
        return _decision(
            CATEGORY_SLUG_ANIMATSIYA,
            path,
            wp_subsection=wp_sub,
            extra_tags=tags_tuple,
            reason="wp_tag_animation",
        )
    if "anime" in segs or "animation" in segs or "multfilmy" in segs:
        return _decision(
            CATEGORY_SLUG_ANIMATSIYA,
            path,
            wp_subsection=wp_sub,
            extra_tags=tags_tuple,
            reason="path_animation",
        )

    if path.startswith("/news/tv-news"):
        return _decision(CATEGORY_SLUG_SERIALY, path, wp_subsection=wp_sub, extra_tags=tags_tuple, reason="news_tv")
    if path.startswith("/news/movie-news"):
        return _decision(CATEGORY_SLUG_FILMY, path, wp_subsection=wp_sub, extra_tags=tags_tuple, reason="news_movie")
    if path.startswith("/books") or path.startswith("/podborki"):
        return _decision(
            CATEGORY_SLUG_FILMY, path, wp_subsection=wp_sub, extra_tags=tags_tuple, reason="books_podborki"
        )
    if path.startswith("/articles/tv-series"):
        return _decision(
            CATEGORY_SLUG_SERIALY, path, wp_subsection=wp_sub, extra_tags=tags_tuple, reason="articles_tv"
        )
    if path.startswith("/articles/movies"):
        return _decision(
            CATEGORY_SLUG_FILMY, path, wp_subsection=wp_sub, extra_tags=tags_tuple, reason="articles_movies"
        )

    if path.startswith("/articles/"):
        return _decision(
            CATEGORY_SLUG_FILMY, path, wp_subsection=wp_sub, extra_tags=tags_tuple, reason="articles_default"
        )

    return _decision(
        CATEGORY_SLUG_FILMY, path, wp_subsection=wp_sub, extra_tags=tags_tuple, reason="fallback_filmy"
    )
