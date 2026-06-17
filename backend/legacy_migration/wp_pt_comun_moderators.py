"""Пользователи сайта для авторов перенесённых статей ПТ → модераторы коммуны."""

from __future__ import annotations

from django.contrib.auth import get_user_model

from feeds.models import Author
from legacy_migration.models import LegacyWpPostMap, LegacyWpUserMap
from users.models import AuthorAdmin

User = get_user_model()


def pt_imported_post_author_ids() -> set[int]:
    ids = set(LegacyWpPostMap.objects.filter(post_id__isnull=False).values_list("post__author_id", flat=True))
    ids.discard(None)
    return {int(x) for x in ids}


def user_ids_for_pt_authors(*, author_ids: set[int] | None = None) -> set[int]:
    """
    User.id для авторов ПТ на Tambur: LegacyWpUserMap, verified AuthorAdmin,
    личный Author (username = User.username, без телеграм-канала).
    """
    if author_ids is None:
        author_ids = pt_imported_post_author_ids()
    if not author_ids:
        return set()

    user_ids: set[int] = set()

    for uid in LegacyWpUserMap.objects.filter(author_id__in=author_ids, user_id__isnull=False).values_list(
        "user_id", flat=True
    ):
        user_ids.add(int(uid))

    for uid in AuthorAdmin.objects.filter(author_id__in=author_ids, verified_at__isnull=False).values_list(
        "user_id", flat=True
    ):
        user_ids.add(int(uid))

    for author in Author.objects.filter(id__in=author_ids).only("id", "username", "channel_url", "channel_id"):
        if (author.channel_url or "").strip() or author.channel_id is not None:
            continue
        username = (author.username or "").strip()
        if not username:
            continue
        match = User.objects.filter(username__iexact=username).only("id").first()
        if match:
            user_ids.add(int(match.id))

    return user_ids


def add_pt_author_moderators(
    comun,
    *,
    dry_run: bool = False,
    author_ids: set[int] | None = None,
) -> dict[str, int]:
    """Добавить в comun.moderators; не снимает существующих."""
    target_ids = user_ids_for_pt_authors(author_ids=author_ids)
    existing = set(comun.moderators.values_list("id", flat=True))
    to_add = sorted(target_ids - existing)
    skipped = len(target_ids & existing)
    if author_ids is None:
        author_ids = pt_imported_post_author_ids()

    if not dry_run and to_add:
        comun.moderators.add(*to_add)

    authors_without_site_user = 0
    for aid in author_ids:
        if not user_ids_for_pt_authors(author_ids={aid}):
            authors_without_site_user += 1

    return {
        "author_count": len(author_ids),
        "user_candidates": len(target_ids),
        "added": len(to_add),
        "already_moderators": skipped,
        "authors_without_site_user": authors_without_site_user,
    }
