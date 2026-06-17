"""Импорт меты WP: комментарии, лайки, просмотры."""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Sum
from django.utils import timezone

from feeds.models import Post, PostComment, PostCommentLike, PostLike
from legacy_migration.models import (
    LegacyWpCommentMap,
    LegacyWpPostMap,
    WpComments,
    WpPostViews,
    WpUlike,
    WpUlikeComments,
)
from legacy_migration.wp_import import (
    resolve_user_for_ulike_voter,
    resolve_user_for_wp_comment,
    wp_comment_body_to_text,
)

APPROVED_COMMENT = "1"
SKIP_COMMENT_TYPES = ("pingback", "trackback", "spam")


def wp_post_total_views(wp_post_id: int) -> int | None:
    row = (
        WpPostViews.objects.filter(id=wp_post_id, type=4, period="total")
        .order_by("-count")
        .first()
    )
    if row and row.count is not None:
        return int(row.count)
    row = (
        WpPostViews.objects.filter(id=wp_post_id, type=0)
        .order_by("-period")
        .first()
    )
    if row and row.count is not None:
        return int(row.count)
    return None


@dataclass
class ImportMetaStats:
    comments_created: int = 0
    comments_skipped: int = 0
    comment_likes_created: int = 0
    post_likes_created: int = 0
    post_likes_skipped: int = 0
    users_touched: int = 0


def import_comments_for_post(
    *,
    post: Post,
    wp_post_id: int,
    force: bool = False,
) -> tuple[ImportMetaStats, dict[int, PostComment]]:
    stats = ImportMetaStats()
    wp_to_comment: dict[int, PostComment] = {}

    if force:
        LegacyWpCommentMap.objects.filter(wp_post_id=wp_post_id).delete()
        PostComment.objects.filter(post=post).delete()
    elif LegacyWpCommentMap.objects.filter(wp_post_id=wp_post_id).exists():
        for row in LegacyWpCommentMap.objects.filter(wp_post_id=wp_post_id).select_related("comment"):
            if row.comment_id:
                wp_to_comment[int(row.wp_comment_id)] = row.comment
        stats.comments_skipped = len(wp_to_comment)
        return stats, wp_to_comment

    qs = (
        WpComments.objects.filter(
            comment_post_id=wp_post_id,
            comment_approved=APPROVED_COMMENT,
        )
        .exclude(comment_type__in=SKIP_COMMENT_TYPES)
        .order_by("comment_date", "comment_id")
    )

    pending_parent: list[tuple[WpComments, PostComment]] = []

    for wp_comment in qs:
        wp_cid = int(wp_comment.comment_id)
        if LegacyWpCommentMap.objects.filter(wp_comment_id=wp_cid).exists():
            stats.comments_skipped += 1
            continue

        user = resolve_user_for_wp_comment(
            wp_user_id=int(wp_comment.user_id or 0),
            comment_author=wp_comment.comment_author or "",
            comment_author_email=wp_comment.comment_author_email or "",
        )
        stats.users_touched += 1

        parent = None
        wp_parent = int(wp_comment.comment_parent or 0)
        if wp_parent:
            parent = wp_to_comment.get(wp_parent)

        body = wp_comment_body_to_text(wp_comment.comment_content or "")
        if not body:
            body = "(пустой комментарий)"

        created_at = wp_comment.comment_date
        if created_at and timezone.is_naive(created_at):
            created_at = timezone.make_aware(created_at, timezone.get_current_timezone())

        comment = PostComment.objects.create(
            post=post,
            user=user,
            parent=parent,
            body=body[:2000],
        )
        if created_at:
            PostComment.objects.filter(pk=comment.pk).update(created_at=created_at)

        if wp_parent and parent is None:
            pending_parent.append((wp_comment, comment))

        LegacyWpCommentMap.objects.create(
            wp_comment_id=wp_cid,
            wp_post_id=wp_post_id,
            comment=comment,
            imported_at=timezone.now(),
        )
        wp_to_comment[wp_cid] = comment
        stats.comments_created += 1

    for wp_comment, comment in pending_parent:
        wp_parent = int(wp_comment.comment_parent or 0)
        parent = wp_to_comment.get(wp_parent)
        if parent and comment.parent_id != parent.id:
            comment.parent = parent
            comment.save(update_fields=["parent", "updated_at"])

    return stats, wp_to_comment


def import_comment_likes(
    *,
    wp_to_comment: dict[int, PostComment],
    stats: ImportMetaStats,
) -> None:
    for wp_cid, comment in wp_to_comment.items():
        rows = WpUlikeComments.objects.filter(
            comment_id=wp_cid,
            status="like",
        )
        for row in rows:
            user = resolve_user_for_ulike_voter(row.user_id)
            stats.users_touched += 1
            _, created = PostCommentLike.objects.get_or_create(
                comment=comment,
                user=user,
            )
            if created:
                stats.comment_likes_created += 1


def import_post_likes(
    *,
    post: Post,
    wp_post_id: int,
    stats: ImportMetaStats,
    force: bool = False,
) -> None:
    if force:
        PostLike.objects.filter(post=post).delete()
        post.rating = 0

    existing_users = set(PostLike.objects.filter(post=post).values_list("user_id", flat=True))

    for row in WpUlike.objects.filter(post_id=wp_post_id, status="like"):
        user = resolve_user_for_ulike_voter(row.user_id)
        stats.users_touched += 1
        if user.id in existing_users:
            stats.post_likes_skipped += 1
            continue
        PostLike.objects.create(post=post, user=user, value=1)
        existing_users.add(user.id)
        stats.post_likes_created += 1

    total = (
        PostLike.objects.filter(post=post).aggregate(total=Sum("value")).get("total") or 0
    )
    post.rating = int(total)


def apply_views_and_counts(
    *,
    post: Post,
    wp_post_id: int,
    wp_to_comment: dict[int, PostComment],
) -> None:
    views = wp_post_total_views(wp_post_id)
    comments_count = PostComment.objects.filter(post=post, is_deleted=False).count()

    raw = dict(post.raw_data or {})
    if views is not None:
        raw["legacy_views_total"] = views
        post.real_views_count = views

    post.comments_count = comments_count
    post.fake_views_target = 0
    post.raw_data = raw
    post.save(
        update_fields=[
            "real_views_count",
            "comments_count",
            "fake_views_target",
            "raw_data",
            "rating",
            "updated_at",
        ]
    )


def import_post_meta(
    *,
    wp_post_id: int,
    force: bool = False,
) -> ImportMetaStats:
    map_row = LegacyWpPostMap.objects.filter(wp_post_id=wp_post_id).select_related("post").first()
    if not map_row or not map_row.post_id:
        raise LookupError(f"wp:{wp_post_id} — нет импортированного Post")

    post = map_row.post
    assert post is not None

    stats, wp_to_comment = import_comments_for_post(
        post=post,
        wp_post_id=wp_post_id,
        force=force,
    )
    import_comment_likes(wp_to_comment=wp_to_comment, stats=stats)
    import_post_likes(post=post, wp_post_id=wp_post_id, stats=stats, force=force)
    apply_views_and_counts(post=post, wp_post_id=wp_post_id, wp_to_comment=wp_to_comment)
    return stats
