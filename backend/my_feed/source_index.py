from __future__ import annotations

from collections.abc import Iterable

from django.db.utils import OperationalError, ProgrammingError

from communities.models import Comun, ComunPostCategoryAssignment
from feeds.models import Post
from my_feed.models import FeedSourcePost


def _bulk_create_source_rows(rows: Iterable[FeedSourcePost]) -> None:
    FeedSourcePost.objects.bulk_create(
        list(rows),
        batch_size=500,
        ignore_conflicts=True,
    )


def _source_keys_for_post(post: Post) -> set[tuple[str, int]]:
    source_keys: set[tuple[str, int]] = set()
    if post.author_id:
        source_keys.add((FeedSourcePost.SOURCE_AUTHOR, int(post.author_id)))

    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    comun_slug = str(raw_data.get("comun_slug") or "").strip()
    if raw_data.get("source") == "manual_comun" and comun_slug:
        comun_id = (
            Comun.objects.filter(slug=comun_slug)
            .values_list("id", flat=True)
            .first()
        )
        if comun_id:
            source_keys.add((FeedSourcePost.SOURCE_COMUN, int(comun_id)))

    for comun_id, category_id in (
        ComunPostCategoryAssignment.objects.filter(post_id=post.id)
        .values_list("comun_id", "category_id")
    ):
        if comun_id:
            source_keys.add((FeedSourcePost.SOURCE_COMUN, int(comun_id)))
        if category_id:
            source_keys.add((FeedSourcePost.SOURCE_COMUN_CATEGORY, int(category_id)))

    if post.author_id:
        for comun_id in Comun.objects.filter(
            telegram_source_author_id=post.author_id
        ).values_list("id", flat=True):
            source_keys.add((FeedSourcePost.SOURCE_COMUN, int(comun_id)))

    for tag_id in post.tags.values_list("id", flat=True):
        source_keys.add((FeedSourcePost.SOURCE_TAG, int(tag_id)))

    return source_keys


def sync_feed_sources_for_post_id(post_id: int | None) -> None:
    if not post_id:
        return
    post = Post.objects.filter(id=post_id).only(
        "id",
        "author_id",
        "created_at",
        "raw_data",
    ).first()
    if not post:
        try:
            FeedSourcePost.objects.filter(post_id=post_id).delete()
        except (OperationalError, ProgrammingError):
            return
        return

    source_keys = _source_keys_for_post(post)
    try:
        FeedSourcePost.objects.filter(post_id=post.id).delete()
        _bulk_create_source_rows(
            FeedSourcePost(
                source_type=source_type,
                source_id=source_id,
                post_id=post.id,
                post_created_at=post.created_at,
            )
            for source_type, source_id in source_keys
        )
    except (OperationalError, ProgrammingError):
        return


def sync_feed_sources_for_posts(post_ids: Iterable[int]) -> None:
    for post_id in post_ids:
        sync_feed_sources_for_post_id(int(post_id))


def sync_feed_sources_for_author_posts(author_id: int | None) -> None:
    if not author_id:
        return
    sync_feed_sources_for_posts(
        Post.objects.filter(author_id=author_id).values_list("id", flat=True).iterator()
    )


def sync_feed_sources_for_manual_comun_slug(slug: str | None) -> None:
    normalized_slug = str(slug or "").strip()
    if not normalized_slug:
        return
    sync_feed_sources_for_posts(
        Post.objects.filter(
            raw_data__source="manual_comun",
            raw_data__comun_slug=normalized_slug,
        )
        .values_list("id", flat=True)
        .iterator()
    )
