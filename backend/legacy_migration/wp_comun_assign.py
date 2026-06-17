"""Назначение импортированных постов ПТ в коммуну «После Титров»."""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from feeds.models import Post, Tag
from legacy_migration.models import LegacyWpPostMap, WpPosts
from legacy_migration.pt_comun import (
    PT_CATEGORY_SLUGS,
    PT_COMUN_SLUG,
    decide_pt_comun,
    legacy_pt_path_for_map,
)


@dataclass
class AssignStats:
    assigned: int = 0
    skipped_no_post: int = 0
    skipped_no_comun: int = 0
    skipped_no_category: int = 0


def load_pt_comun_context(comun_slug: str = PT_COMUN_SLUG) -> tuple[Comun | None, dict[str, ComunCategory]]:
    comun = Comun.objects.filter(slug=comun_slug, is_active=True).first()
    if not comun:
        return None, {}
    categories = {
        c.slug: c
        for c in ComunCategory.objects.filter(
            comun=comun,
            slug__in=PT_CATEGORY_SLUGS,
            is_active=True,
        )
    }
    return comun, categories


def _attach_path_tags(post: Post, tag_names: tuple[str, ...], *, dry_run: bool) -> int:
    added = 0
    for name in tag_names:
        stored = name.strip()[:64]
        if not stored:
            continue
        if dry_run:
            added += 1
            continue
        tag, _ = Tag.objects.get_or_create(name=stored)
        if not post.tags.filter(pk=tag.pk).exists():
            post.tags.add(tag)
            added += 1
    return added


def assign_post_to_pt_comun(
    map_row: LegacyWpPostMap,
    *,
    comun: Comun | None,
    categories_by_slug: dict[str, ComunCategory],
    wp_post: WpPosts | None = None,
    dry_run: bool = False,
    with_path_tags: bool = True,
    comun_slug: str = PT_COMUN_SLUG,
) -> str:
    """assigned | skipped_no_post | skipped_no_comun | skipped_no_category."""
    if not map_row.post_id or not map_row.post:
        return "skipped_no_post"

    if not comun and not dry_run:
        return "skipped_no_comun"

    post = map_row.post
    wp_post = wp_post or WpPosts.objects.filter(id=map_row.wp_post_id).first()
    path = legacy_pt_path_for_map(map_row, wp_post)
    decision = decide_pt_comun(path, wp_post_id=int(map_row.wp_post_id))

    category = categories_by_slug.get(decision.category_slug)
    if not category and not dry_run:
        return "skipped_no_category"

    if dry_run:
        return "assigned"

    assert comun is not None
    assert category is not None

    with transaction.atomic():
        raw = dict(post.raw_data) if isinstance(post.raw_data, dict) else {}
        raw["legacy_pt_path"] = decision.legacy_pt_path
        raw["legacy_comun_slug"] = comun_slug
        raw["legacy_comun_category_slug"] = decision.category_slug
        raw["legacy_comun_reason"] = decision.reason
        if decision.wp_subsection:
            raw["legacy_pt_subsection"] = decision.wp_subsection
        post.raw_data = raw
        post.save(update_fields=["raw_data", "updated_at"])

        ComunPostCategoryAssignment.objects.update_or_create(
            comun=comun,
            post=post,
            defaults={"category": category},
        )
        ComunPostCategoryAssignment.objects.filter(post=post).exclude(comun=comun).delete()

        if with_path_tags and decision.extra_tag_slugs:
            _attach_path_tags(post, decision.extra_tag_slugs, dry_run=False)

    return "assigned"


def assign_maps(
    maps: list[LegacyWpPostMap],
    *,
    comun_slug: str = PT_COMUN_SLUG,
    dry_run: bool = False,
    with_path_tags: bool = True,
) -> AssignStats:
    stats = AssignStats()
    comun, categories_by_slug = load_pt_comun_context(comun_slug)

    wp_ids = [int(m.wp_post_id) for m in maps]
    wp_by_id = {int(p.id): p for p in WpPosts.objects.filter(id__in=wp_ids)}

    for map_row in maps:
        status = assign_post_to_pt_comun(
            map_row,
            comun=comun,
            categories_by_slug=categories_by_slug,
            wp_post=wp_by_id.get(int(map_row.wp_post_id)),
            dry_run=dry_run,
            with_path_tags=with_path_tags,
            comun_slug=comun_slug,
        )
        if status == "assigned":
            stats.assigned += 1
        elif status == "skipped_no_post":
            stats.skipped_no_post += 1
        elif status == "skipped_no_comun":
            stats.skipped_no_comun += 1
        else:
            stats.skipped_no_category += 1

    return stats
