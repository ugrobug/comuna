from __future__ import annotations

from django.db.models import Exists, OuterRef, Q, QuerySet
from django.db.models.fields.json import KeyTextTransform
from django.utils import timezone

from communities.models import Comun
from feeds.language_detection import post_language_text
from feeds.models import Post, PostComment


MIN_POST_TEXT_LENGTH = 200
MIN_LONG_COMMENT_LENGTH = 200
MIN_COMUN_POSTS = 2


def plain_text_length(value: str) -> int:
    return len(post_language_text("", value or ""))


def public_posts_queryset(queryset: QuerySet | None = None, *, now=None) -> QuerySet:
    current_time = now or timezone.now()
    base_queryset = queryset if queryset is not None else Post.objects.all()
    return (
        base_queryset.filter(
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(Q(publish_at__isnull=True) | Q(publish_at__lte=current_time))
        .filter(
            Q(raw_data__special_project__slug__isnull=True)
            | ~Q(raw_data__special_project__slug="book")
        )
    )


def _exclude_posts_from_inactive_comuns(queryset: QuerySet) -> QuerySet:
    inactive_comuns = Comun.objects.filter(is_active=False)
    queryset = queryset.annotate(
        _seo_comun_slug=KeyTextTransform("comun_slug", "raw_data")
    )
    return queryset.exclude(
        Q(
            _seo_comun_slug__isnull=False,
            _seo_comun_slug__in=inactive_comuns.values("slug"),
        )
        | Q(
            author_id__in=inactive_comuns.exclude(
                telegram_source_author_id__isnull=True
            ).values("telegram_source_author_id"),
        )
        | Q(comun_category_assignments__comun__is_active=False)
    ).distinct()


def seo_indexable_posts_queryset(
    queryset: QuerySet | None = None,
    *,
    now=None,
) -> QuerySet:
    long_comment = PostComment.objects.filter(
        post_id=OuterRef("pk"),
        is_deleted=False,
        seo_text_length__gte=MIN_LONG_COMMENT_LENGTH,
    )
    public_posts = public_posts_queryset(queryset, now=now).annotate(
        _seo_has_long_comment=Exists(long_comment)
    )
    public_posts = public_posts.filter(
        Q(seo_text_length__gte=MIN_POST_TEXT_LENGTH)
        | Q(_seo_has_long_comment=True)
    )
    return _exclude_posts_from_inactive_comuns(public_posts)


def post_is_seo_indexable(post: Post, *, now=None) -> bool:
    current_time = now or timezone.now()
    if post.is_blocked or post.is_pending or getattr(post.author, "is_blocked", False):
        return False
    if post.publish_at and post.publish_at > current_time:
        return False

    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    special_project = raw_data.get("special_project")
    if isinstance(special_project, dict) and special_project.get("slug") == "book":
        return False

    text_length = int(getattr(post, "seo_text_length", 0) or 0)
    if not text_length and post.content:
        text_length = plain_text_length(post.content)
    if text_length < MIN_POST_TEXT_LENGTH and not PostComment.objects.filter(
        post_id=post.id,
        is_deleted=False,
        seo_text_length__gte=MIN_LONG_COMMENT_LENGTH,
    ).exists():
        return False

    inactive_comuns = Comun.objects.filter(is_active=False)
    comun_slug = str(raw_data.get("comun_slug") or "").strip()
    blocked_filter = Q(post_category_assignments__post_id=post.id)
    if comun_slug:
        blocked_filter |= Q(slug=comun_slug)
    if post.author_id:
        blocked_filter |= Q(telegram_source_author_id=post.author_id)
    return not inactive_comuns.filter(blocked_filter).exists()


def comun_public_posts_queryset(comun: Comun, *, now=None) -> QuerySet:
    membership_filter = Q(
        raw_data__source="manual_comun",
        raw_data__comun_slug=comun.slug,
    ) | Q(comun_category_assignments__comun_id=comun.id)
    if comun.telegram_source_author_id:
        membership_filter |= Q(author_id=comun.telegram_source_author_id)
    return public_posts_queryset(now=now).filter(membership_filter).distinct()


def comun_public_posts_count(comun: Comun, *, limit: int = MIN_COMUN_POSTS) -> int:
    if not comun.is_active:
        return 0
    return len(
        list(
            comun_public_posts_queryset(comun)
            .order_by()
            .values_list("id", flat=True)[: max(1, int(limit))]
        )
    )


def comun_is_seo_indexable(comun: Comun) -> bool:
    return bool(
        comun.is_active
        and comun_public_posts_count(comun, limit=MIN_COMUN_POSTS) >= MIN_COMUN_POSTS
    )


def seo_indexable_comuns_queryset() -> QuerySet:
    eligible_ids = [
        comun.id
        for comun in Comun.objects.filter(is_active=True)
        .only("id", "slug", "is_active", "telegram_source_author_id")
        .iterator()
        if comun_is_seo_indexable(comun)
    ]
    return Comun.objects.filter(id__in=eligible_ids)
