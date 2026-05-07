from __future__ import annotations

from datetime import timedelta
import math

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import Count, F, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Cast, Coalesce
from django.utils import timezone

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
    max_author_rating = 0.0
    for total_rating in Author.objects.filter(id__in=author_ids).values_list("rating_total", flat=True):
        max_author_rating = max(max_author_rating, author_rating_value(total_rating))
    return round(max_author_rating, 2)


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


def list_top_authors(
    *,
    period: str = "month",
    limit: int | None = 5,
    now=None,
) -> tuple[str, list[object], int]:
    Author = _author_model()
    AuthorRatingEvent = _author_rating_event_model()

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

    if normalized_period == "all":
        authors_qs = authors_qs.annotate(
            period_rating_total=Cast(F("rating_total"), IntegerField())
        ).order_by("-period_rating_total", "-posts_count", "username")
    else:
        period_rating_total_subquery = (
            AuthorRatingEvent.objects.filter(
                author_id=OuterRef("pk"),
                created_at__gte=cutoff,
            )
            .values("author_id")
            .annotate(total=Coalesce(Sum("delta"), Value(0)))
            .values("total")[:1]
        )
        authors_qs = authors_qs.annotate(
            period_rating_total=Coalesce(
                Subquery(period_rating_total_subquery, output_field=IntegerField()),
                Value(0),
            )
        ).order_by("-period_rating_total", "-rating_total", "-posts_count", "username")

    total_authors = authors_qs.count()
    authors = list(authors_qs if limit is None else authors_qs[:limit])
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
    "format_rating_value",
    "list_top_comuns",
    "list_top_authors",
    "normalize_top_authors_period",
    "parse_top_authors_limit",
    "public_user_author_ids",
    "TOP_AUTHORS_PERIODS",
    "user_max_author_rating",
]
