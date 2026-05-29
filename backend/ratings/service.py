from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
import math

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from ratings.models import RatingSettings

User = get_user_model()


TOP_AUTHORS_PERIODS: dict[str, int | None] = {
    "week": 7,
    "month": 30,
    "all": None,
}


def _author_model():
    return apps.get_model("feeds", "Author")


def _author_admin_model():
    return apps.get_model("feeds", "AuthorAdmin")


def _author_rating_event_model():
    return apps.get_model("feeds", "AuthorRatingEvent")


def _comun_model():
    return apps.get_model("feeds", "Comun")


def _post_model():
    return apps.get_model("feeds", "Post")


def _post_comment_like_model():
    return apps.get_model("feeds", "PostCommentLike")


def get_rating_settings() -> RatingSettings:
    settings, _created = RatingSettings.objects.get_or_create(pk=1)
    return settings


def _decimal(value: object, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _rating_float(value: Decimal | float | int | None) -> float:
    try:
        normalized = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        normalized = Decimal("0.00")
    return float(normalized)


def serialize_rating_settings(settings: RatingSettings | None = None) -> dict:
    settings = settings or get_rating_settings()
    return {
        "post_vote_weight": _rating_float(settings.post_vote_weight),
        "post_comment_weight": _rating_float(settings.post_comment_weight),
        "post_comment_like_weight": _rating_float(settings.post_comment_like_weight),
        "post_community_rating_weight": _rating_float(settings.post_community_rating_weight),
        "post_author_rating_weight": _rating_float(settings.post_author_rating_weight),
        "community_post_rating_weight": _rating_float(settings.community_post_rating_weight),
        "community_post_rating_days": int(settings.community_post_rating_days or 0),
        "home_posts_per_community_per_day": int(settings.home_posts_per_community_per_day or 0),
        "author_post_rating_weight": _rating_float(settings.author_post_rating_weight),
        "author_comment_like_weight": _rating_float(settings.author_comment_like_weight),
        "updated_at": settings.updated_at.isoformat() if settings.updated_at else None,
    }


def update_rating_settings(payload: dict) -> RatingSettings:
    settings = get_rating_settings()
    decimal_fields = (
        "post_vote_weight",
        "post_comment_weight",
        "post_comment_like_weight",
        "post_community_rating_weight",
        "post_author_rating_weight",
        "community_post_rating_weight",
        "author_post_rating_weight",
        "author_comment_like_weight",
    )
    for field in decimal_fields:
        if field in payload:
            value = _decimal(payload.get(field))
            if value < 0:
                raise ValueError(f"{field} must be greater than or equal to 0")
            setattr(settings, field, value)
    if "community_post_rating_days" in payload:
        try:
            days = int(payload.get("community_post_rating_days"))
        except (TypeError, ValueError):
            raise ValueError("community_post_rating_days must be an integer")
        if days < 1 or days > 365:
            raise ValueError("community_post_rating_days must be between 1 and 365")
        settings.community_post_rating_days = days
    if "home_posts_per_community_per_day" in payload:
        try:
            limit = int(payload.get("home_posts_per_community_per_day"))
        except (TypeError, ValueError):
            raise ValueError("home_posts_per_community_per_day must be an integer")
        if limit < 1 or limit > 100:
            raise ValueError("home_posts_per_community_per_day must be between 1 and 100")
        settings.home_posts_per_community_per_day = limit
    settings.save()
    return settings


def normalize_top_authors_period(raw_value: str | None, *, default: str = "month") -> str:
    value = (raw_value or "").strip().lower()
    if value in TOP_AUTHORS_PERIODS:
        return value
    return default


def parse_top_authors_limit(
    raw_value: str | None,
    *,
    default: int = 5,
    max_limit: int = 1000,
) -> int | None:
    value = (raw_value or "").strip().lower()
    if not value:
        return default
    if value in {"all", "0"}:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return default
    if parsed <= 0:
        return None
    return min(parsed, max_limit)


def author_rating_value(total_rating: int | None) -> float:
    return round((total_rating or 0) * 0.05, 2)


def format_rating_value(value: float | int | None) -> str:
    try:
        normalized = round(float(value or 0), 2)
    except (TypeError, ValueError):
        normalized = 0.0
    if not math.isfinite(normalized) or normalized < 0:
        normalized = 0.0
    return f"{normalized:.2f}".rstrip("0").rstrip(".") or "0"


def public_user_author_ids(user: User) -> tuple[list[int], list[object]]:
    Author = _author_model()
    AuthorAdmin = _author_admin_model()

    author_links = list(
        AuthorAdmin.objects.filter(user=user, verified_at__isnull=False)
        .select_related("author")
        .order_by("author__username")
    )
    author_ids = [link.author_id for link in author_links]
    personal_author = Author.objects.filter(
        username__iexact=(user.username or "").strip(),
        channel_url="",
        channel_id__isnull=True,
    ).first()
    if personal_author and personal_author.id not in author_ids:
        author_ids.append(personal_author.id)
    return author_ids, author_links


def user_max_author_rating(user: User | None) -> float:
    if not user:
        return 0.0
    Author = _author_model()
    author_ids, _author_links = public_user_author_ids(user)
    if not author_ids:
        return 0.0
    settings = get_rating_settings()
    max_author_rating = Decimal("0")
    for author in Author.objects.filter(id__in=author_ids):
        max_author_rating = max(max_author_rating, calculate_author_rating(author, settings=settings))
    return _rating_float(max_author_rating)


def apply_author_rating_delta(
    *,
    author_id: int,
    delta: int,
    event_type: str,
    actor_id: int | None = None,
    post_id: int | None = None,
    comment_id: int | None = None,
) -> None:
    if not delta:
        return

    Author = _author_model()
    AuthorRatingEvent = _author_rating_event_model()

    Author.objects.filter(id=author_id).update(rating_total=F("rating_total") + delta)
    AuthorRatingEvent.objects.create(
        author_id=author_id,
        actor_id=actor_id,
        post_id=post_id,
        comment_id=comment_id,
        event_type=event_type,
        delta=delta,
    )


def public_posts_filter(now=None) -> Q:
    current_time = now or timezone.now()
    return Q(is_blocked=False, is_pending=False, author__is_blocked=False) & (
        Q(publish_at__isnull=True) | Q(publish_at__lte=current_time)
    )


def calculate_post_base_rating(
    post,
    *,
    settings: RatingSettings | None = None,
    comment_likes_count: int | None = None,
) -> Decimal:
    settings = settings or get_rating_settings()
    if comment_likes_count is None:
        PostCommentLike = _post_comment_like_model()
        comment_likes_count = PostCommentLike.objects.filter(
            comment__post_id=post.id,
            comment__is_deleted=False,
        ).count()
    rating = (
        _decimal(getattr(post, "rating", 0)) * _decimal(settings.post_vote_weight)
        + _decimal(getattr(post, "comments_count", 0)) * _decimal(settings.post_comment_weight)
        + _decimal(comment_likes_count) * _decimal(settings.post_comment_like_weight)
    )
    return rating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_posts_base_rating(posts, *, settings: RatingSettings | None = None) -> dict[int, Decimal]:
    settings = settings or get_rating_settings()
    post_list = list(posts)
    if not post_list:
        return {}
    post_ids = [post.id for post in post_list]
    PostCommentLike = _post_comment_like_model()
    like_rows = (
        PostCommentLike.objects.filter(comment__post_id__in=post_ids, comment__is_deleted=False)
        .values("comment__post_id")
        .annotate(total=Count("id"))
    )
    likes_by_post_id = {
        int(row["comment__post_id"]): int(row["total"] or 0)
        for row in like_rows
    }
    return {
        post.id: calculate_post_base_rating(
            post,
            settings=settings,
            comment_likes_count=likes_by_post_id.get(post.id, 0),
        )
        for post in post_list
    }


def _candidate_comun_ids_for_post(post) -> list[int]:
    Comun = _comun_model()
    combined_filter = Q()
    has_filter = False
    raw_data = post.raw_data if isinstance(getattr(post, "raw_data", None), dict) else {}
    comun_slug = str(raw_data.get("comun_slug") or "").strip()
    if comun_slug:
        combined_filter |= Q(slug=comun_slug)
        has_filter = True
    if getattr(post, "author_id", None):
        combined_filter |= Q(telegram_source_author_id=post.author_id)
        has_filter = True
    if not has_filter:
        return []
    return list(
        Comun.objects.filter(combined_filter, is_active=True)
        .exclude(slug__iexact="faq")
        .order_by("-rating_score", "id")
        .values_list("id", flat=True)
    )


def home_feed_community_day_key(post) -> tuple[int, object] | None:
    comun_ids = _candidate_comun_ids_for_post(post)
    if not comun_ids:
        return None
    created_at = getattr(post, "created_at", None)
    if created_at is None:
        return None
    return (int(comun_ids[0]), timezone.localdate(created_at))


def calculate_post_community_rating(post, *, settings: RatingSettings | None = None) -> Decimal:
    settings = settings or get_rating_settings()
    comun_ids = _candidate_comun_ids_for_post(post)
    if not comun_ids:
        return Decimal("0.00")
    Comun = _comun_model()
    value = (
        Comun.objects.filter(id__in=comun_ids)
        .order_by("-rating_score")
        .values_list("rating_score", flat=True)
        .first()
    )
    return (_decimal(value) * _decimal(settings.post_community_rating_weight)).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def calculate_author_rating(author, *, settings: RatingSettings | None = None, cutoff=None, now=None) -> Decimal:
    settings = settings or get_rating_settings()
    Post = _post_model()
    PostCommentLike = _post_comment_like_model()
    posts = Post.objects.filter(author_id=author.id).filter(public_posts_filter(now))
    if cutoff is not None:
        posts = posts.filter(created_at__gte=cutoff)
    post_totals = posts.aggregate(
        votes=Sum("rating"),
        comments=Sum("comments_count"),
    )
    comment_likes_on_posts = PostCommentLike.objects.filter(
        comment__post__in=posts,
        comment__is_deleted=False,
    ).count()
    posts_rating = (
        _decimal(post_totals.get("votes")) * _decimal(settings.post_vote_weight)
        + _decimal(post_totals.get("comments")) * _decimal(settings.post_comment_weight)
        + _decimal(comment_likes_on_posts) * _decimal(settings.post_comment_like_weight)
    )
    comment_likes_by_author = PostCommentLike.objects.filter(
        comment__user__username__iexact=author.username,
        comment__is_deleted=False,
    )
    if cutoff is not None:
        comment_likes_by_author = comment_likes_by_author.filter(created_at__gte=cutoff)
    comment_rating = _decimal(comment_likes_by_author.count()) * _decimal(
        settings.author_comment_like_weight
    )
    rating = posts_rating * _decimal(settings.author_post_rating_weight) + comment_rating
    return rating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_author_ratings(authors, *, settings: RatingSettings | None = None, cutoff=None, now=None) -> dict[int, Decimal]:
    settings = settings or get_rating_settings()
    return {
        author.id: calculate_author_rating(author, settings=settings, cutoff=cutoff, now=now)
        for author in authors
    }


def calculate_post_total_rating(
    post,
    *,
    settings: RatingSettings | None = None,
    author_rating: Decimal | float | int | None = None,
    base_rating: Decimal | float | int | None = None,
) -> Decimal:
    settings = settings or get_rating_settings()
    base = _decimal(base_rating) if base_rating is not None else calculate_post_base_rating(post, settings=settings)
    if author_rating is None:
        author_rating = calculate_author_rating(post.author, settings=settings) if getattr(post, "author", None) else 0
    rating = (
        base
        + calculate_post_community_rating(post, settings=settings)
        + _decimal(author_rating) * _decimal(settings.post_author_rating_weight)
    )
    return rating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_community_rating_for_posts(posts, *, settings: RatingSettings | None = None) -> Decimal:
    settings = settings or get_rating_settings()
    post_list = list(posts)
    if not post_list:
        return Decimal("0.00")
    base_ratings = calculate_posts_base_rating(post_list, settings=settings)
    total = sum(base_ratings.values(), Decimal("0"))
    rating = total * _decimal(settings.community_post_rating_weight)
    return rating.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def list_top_authors(
    *,
    period: str = "month",
    limit: int | None = 5,
    now=None,
) -> tuple[str, list[object], int]:
    Author = _author_model()

    normalized_period = normalize_top_authors_period(period, default="month")
    current_time = now or timezone.now()
    posts_filter = Q(posts__is_blocked=False, posts__is_pending=False) & (
        Q(posts__publish_at__isnull=True) | Q(posts__publish_at__lte=current_time)
    )

    period_days = TOP_AUTHORS_PERIODS.get(normalized_period)
    cutoff = None
    if period_days is not None:
        cutoff = current_time - timedelta(days=period_days)
        posts_filter &= Q(posts__created_at__gte=cutoff)

    authors_qs = (
        Author.objects.filter(is_blocked=False)
        .filter(Q(shadow_banned=False) | Q(force_home=True))
        .annotate(posts_count=Count("posts", filter=posts_filter, distinct=True))
    )

    total_authors = authors_qs.count()
    settings = get_rating_settings()
    authors_with_rating = list(authors_qs)
    for author in authors_with_rating:
        period_rating = calculate_author_rating(
            author,
            settings=settings,
            cutoff=cutoff,
            now=current_time,
        )
        author.period_rating_score = period_rating
        author.rating_score = calculate_author_rating(author, settings=settings, now=current_time)
    authors_with_rating.sort(
        key=lambda author: (
            -float(getattr(author, "period_rating_score", 0) or 0),
            -int(getattr(author, "posts_count", 0) or 0),
            str(getattr(author, "username", "") or "").lower(),
        )
    )
    authors = authors_with_rating if limit is None else authors_with_rating[:limit]
    return normalized_period, authors, total_authors


def list_top_comuns(
    *,
    limit: int | None = 5,
) -> tuple[list[object], int]:
    Comun = _comun_model()
    queryset = (
        Comun.objects.filter(is_active=True)
        .exclude(slug__iexact="faq")
        .select_related("creator", "telegram_source_author")
        .prefetch_related("categories")
        .order_by("-rating_score", "sort_order", "name")
    )
    total_comuns = queryset.count()
    comuns = list(queryset if limit is None else queryset[:limit])
    return comuns, total_comuns


__all__ = [
    "apply_author_rating_delta",
    "author_rating_value",
    "calculate_author_rating",
    "calculate_author_ratings",
    "calculate_community_rating_for_posts",
    "calculate_post_base_rating",
    "calculate_post_total_rating",
    "calculate_posts_base_rating",
    "format_rating_value",
    "get_rating_settings",
    "home_feed_community_day_key",
    "list_top_comuns",
    "list_top_authors",
    "normalize_top_authors_period",
    "parse_top_authors_limit",
    "public_user_author_ids",
    "public_posts_filter",
    "serialize_rating_settings",
    "TOP_AUTHORS_PERIODS",
    "update_rating_settings",
    "user_max_author_rating",
]
