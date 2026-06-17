"""Рубрики поста WP (taxonomy category) — правила коммуны Tambur."""

from __future__ import annotations

from legacy_migration.models import WpTermRelationships, WpTermTaxonomy, WpTerms

# Рубрика «Сериалы» в админке ПТ (taxonomy category)
_SERIALY_CATEGORY_NAMES_CF = frozenset({"сериалы"})
_SERIALY_CATEGORY_SLUGS_CF = frozenset(
    {"serialy", "serials", "serialy", "seriali", "serii"}
)


def wp_post_category_terms(wp_post_id: int) -> list[tuple[str, str]]:
    """Пары (name, slug) для taxonomy=category."""
    rels = WpTermRelationships.objects.filter(object_id=int(wp_post_id))
    taxonomy_ids = list(rels.values_list("term_taxonomy_id", flat=True))
    if not taxonomy_ids:
        return []

    rows = WpTermTaxonomy.objects.filter(
        term_taxonomy_id__in=taxonomy_ids,
        taxonomy="category",
    ).values_list("term_id", flat=True)
    term_ids = list(rows)
    if not term_ids:
        return []

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in WpTerms.objects.filter(term_id__in=term_ids).order_by("name"):
        name = (row.name or "").strip()
        slug = (row.slug or "").strip()
        if not name and not slug:
            continue
        key = f"{name.casefold()}\0{slug.casefold()}"
        if key in seen:
            continue
        seen.add(key)
        out.append((name, slug))
    return out


def term_is_serialy_category(name: str, slug: str) -> bool:
    n = (name or "").strip().casefold()
    s = (slug or "").strip().casefold()
    if n in _SERIALY_CATEGORY_NAMES_CF:
        return True
    return s in _SERIALY_CATEGORY_SLUGS_CF


def wp_categories_suggest_serialy(wp_post_id: int) -> bool:
    for name, slug in wp_post_category_terms(wp_post_id):
        if term_is_serialy_category(name, slug):
            return True
    return False
