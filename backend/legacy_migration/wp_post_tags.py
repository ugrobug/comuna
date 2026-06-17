"""Теги поста WP (taxonomy post_tag) → feeds.Tag."""

from __future__ import annotations

from feeds.models import Post, Tag
from legacy_migration.models import (
    WpTermRelationships,
    WpTermTaxonomy,
    WpTerms,
)


def wp_post_tag_names(wp_post_id: int) -> list[str]:
    rels = WpTermRelationships.objects.filter(object_id=int(wp_post_id))
    taxonomy_ids = list(rels.values_list("term_taxonomy_id", flat=True))
    if not taxonomy_ids:
        return []

    term_ids = list(
        WpTermTaxonomy.objects.filter(
            term_taxonomy_id__in=taxonomy_ids,
            taxonomy="post_tag",
        ).values_list("term_id", flat=True)
    )
    if not term_ids:
        return []

    names: list[str] = []
    seen: set[str] = set()
    for row in WpTerms.objects.filter(term_id__in=term_ids).order_by("name"):
        name = (row.name or "").strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
    return names


def attach_wp_tags_to_post(post: Post, wp_post_id: int) -> list[str]:
    """Привязать теги; возвращает имена, записанные в Tag (до 64 символов)."""
    attached: list[str] = []
    tags: list[Tag] = []
    for name in wp_post_tag_names(wp_post_id):
        stored = name[:64]
        if not stored:
            continue
        tag, _ = Tag.objects.get_or_create(name=stored)
        tags.append(tag)
        attached.append(stored)
    post.tags.set(tags)
    return attached
