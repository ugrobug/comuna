"""Пересчёт кэша счётчиков коммуны — только для этапа миграции ПТ (management-команда)."""

from __future__ import annotations

from django.utils import timezone

from communities import service as community_service
from communities.models import Comun
from my_feed.models import UserFeedSettings


def compute_comun_cached_counts(comun: Comun, *, now=None) -> dict[str, int]:
    """
    Фактические subscribers_count и authors_count без записи в БД.

    Подписчики: UserFeedSettings (my_feed_comuns / my_feed_comun_categories).
    Авторы: distinct site-user авторы постов в ленте коммуны (как feeds.0134 backfill),
    минимум 1 если в коммуне есть посты, но нет «сайтовых» авторов.
    """
    now = now or timezone.now()
    slug = str(comun.slug or "").strip()
    subscribers_count = 0
    if slug:
        for settings in UserFeedSettings.objects.all().iterator(chunk_size=500):
            subscribed = community_service._subscribed_comun_slugs_from_settings(
                {
                    "my_feed_comuns": settings.my_feed_comuns,
                    "my_feed_comun_categories": settings.my_feed_comun_categories,
                }
            )
            if slug in subscribed:
                subscribers_count += 1

    site_authors_count = (
        community_service._comun_site_user_posts_queryset(comun, now)
        .exclude(author_id__isnull=True)
        .values("author_id")
        .distinct()
        .count()
    )
    posts_exist = community_service._comun_posts_base_queryset(comun, now).exists()
    authors_count = site_authors_count or (1 if posts_exist else 0)
    return {
        "subscribers_count": int(subscribers_count or 0),
        "authors_count": int(authors_count or 0),
    }


def recalculate_comun_cached_counts(comun: Comun, *, now=None) -> dict[str, int]:
    counts = compute_comun_cached_counts(comun, now=now)
    Comun.objects.filter(id=comun.id).update(
        subscribers_count=counts["subscribers_count"],
        authors_count=counts["authors_count"],
    )
    comun.subscribers_count = counts["subscribers_count"]
    comun.authors_count = counts["authors_count"]
    return counts
