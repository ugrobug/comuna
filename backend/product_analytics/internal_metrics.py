from __future__ import annotations

import json
import statistics
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any, Iterable

from django.contrib.auth import get_user_model
from django.db.models import Max, QuerySet, Sum
from django.utils import timezone

from editor.models import PostPollVote, PostRatingVote
from feeds.models import (
    Post,
    PostComment,
    PostCommentLike,
    PostDailyView,
    PostFavorite,
    PostLike,
    PostRead,
)
from my_feed.models import ComunSubscriptionEvent
from users.models import SiteUserProfile

from .yandex_metrika import BACKEND_DIR


SITE_POST_SOURCES = {"manual", "manual_comun"}
BASELINE_KEYS = [
    "registered_users",
    "value_users_authenticated",
    "core_value_users",
    "site_posts",
    "comments",
    "positive_likes",
    "votes",
    "reads_marked",
    "favorites",
    "subscriptions_gained",
    "subscriptions_lost",
    "subscriptions_net",
    "real_post_views",
    "same_week_activation_rate",
]


def _period_bounds(period: Any) -> tuple[datetime, datetime]:
    zone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(period.start, time.min), zone)
    end = timezone.make_aware(
        datetime.combine(period.end + timedelta(days=1), time.min), zone
    )
    return start, end


def _between(field: str, start: datetime, end: datetime) -> dict[str, datetime]:
    return {f"{field}__gte": start, f"{field}__lt": end}


def _user_ids(queryset: QuerySet, field: str = "user_id") -> set[int]:
    return {int(value) for value in queryset.values_list(field, flat=True) if value}


def _rate(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round(numerator / denominator * 100, 2)


def _percent_change(current: float | int | None, previous: float | int | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 2)


def period_internal_metrics(period: Any) -> dict[str, Any]:
    start, end = _period_bounds(period)

    registrations = SiteUserProfile.objects.filter(
        deleted_at__isnull=True,
        registration_source__gt="",
        **_between("created_at", start, end),
    )
    site_posts = Post.objects.filter(
        is_blocked=False,
        is_pending=False,
        raw_data__source__in=SITE_POST_SOURCES,
        **_between("created_at", start, end),
    )
    comments = PostComment.objects.filter(
        is_deleted=False,
        **_between("created_at", start, end),
    )
    post_likes = PostLike.objects.filter(
        value__gt=0,
        **_between("created_at", start, end),
    )
    comment_likes = PostCommentLike.objects.filter(
        **_between("created_at", start, end)
    )
    poll_votes = PostPollVote.objects.filter(**_between("created_at", start, end))
    rating_votes = PostRatingVote.objects.filter(**_between("updated_at", start, end))
    reads = PostRead.objects.filter(**_between("read_at", start, end))
    favorites = PostFavorite.objects.filter(**_between("created_at", start, end))
    subscriptions = ComunSubscriptionEvent.objects.filter(
        **_between("created_at", start, end)
    )
    subscriptions_gained = subscriptions.filter(
        action=ComunSubscriptionEvent.ACTION_SUBSCRIBE
    )
    subscriptions_lost = subscriptions.filter(
        action=ComunSubscriptionEvent.ACTION_UNSUBSCRIBE
    )

    comment_user_ids = _user_ids(comments)
    like_user_ids = _user_ids(post_likes) | _user_ids(comment_likes)
    vote_user_ids = _user_ids(poll_votes) | _user_ids(rating_votes)
    read_user_ids = _user_ids(reads)
    favorite_user_ids = _user_ids(favorites)
    subscription_user_ids = _user_ids(subscriptions_gained)
    value_user_ids = (
        comment_user_ids
        | like_user_ids
        | vote_user_ids
        | read_user_ids
        | favorite_user_ids
        | subscription_user_ids
    )
    core_value_user_ids = (
        comment_user_ids
        | vote_user_ids
        | favorite_user_ids
        | subscription_user_ids
    )
    registration_user_ids = _user_ids(registrations)
    activated_registration_ids = registration_user_ids & value_user_ids

    positive_likes = post_likes.count() + comment_likes.count()
    votes = poll_votes.count() + rating_votes.count()
    gained = subscriptions_gained.count()
    lost = subscriptions_lost.count()
    real_views = int(
        PostDailyView.objects.filter(date__gte=period.start, date__lte=period.end)
        .aggregate(value=Sum("views_count"))["value"]
        or 0
    )

    return {
        "start": period.start.isoformat(),
        "end": period.end.isoformat(),
        "registered_users": registrations.count(),
        "registered_users_activated_same_week": len(activated_registration_ids),
        "same_week_activation_rate": _rate(
            len(activated_registration_ids), len(registration_user_ids)
        ),
        "value_users_authenticated": len(value_user_ids),
        "core_value_users": len(core_value_user_ids),
        "site_posts": site_posts.count(),
        "site_post_authors": site_posts.values("author_id").distinct().count(),
        "comments": comments.count(),
        "commenting_users": len(comment_user_ids),
        "positive_likes": positive_likes,
        "liking_users": len(like_user_ids),
        "votes": votes,
        "voting_users": len(vote_user_ids),
        "reads_marked": reads.count(),
        "reading_users": len(read_user_ids),
        "favorites": favorites.count(),
        "favoriting_users": len(favorite_user_ids),
        "subscriptions_gained": gained,
        "subscriptions_lost": lost,
        "subscriptions_net": gained - lost,
        "subscribing_users": len(subscription_user_ids),
        "real_post_views": real_views,
    }


def _latest_activity_at() -> str | None:
    candidates: Iterable[datetime | None] = (
        SiteUserProfile.objects.aggregate(value=Max("created_at"))["value"],
        Post.objects.aggregate(value=Max("created_at"))["value"],
        PostComment.objects.aggregate(value=Max("created_at"))["value"],
        PostLike.objects.aggregate(value=Max("created_at"))["value"],
        PostCommentLike.objects.aggregate(value=Max("created_at"))["value"],
        PostPollVote.objects.aggregate(value=Max("created_at"))["value"],
        PostRatingVote.objects.aggregate(value=Max("updated_at"))["value"],
        PostRead.objects.aggregate(value=Max("read_at"))["value"],
        PostFavorite.objects.aggregate(value=Max("created_at"))["value"],
        ComunSubscriptionEvent.objects.aggregate(value=Max("created_at"))["value"],
    )
    latest = max((value for value in candidates if value), default=None)
    return latest.isoformat() if latest else None


def build_internal_product_report(periods: list[Any]) -> dict[str, Any]:
    weekly = [period_internal_metrics(period) for period in reversed(periods)]
    current = weekly[-1]
    previous = weekly[-2] if len(weekly) > 1 else {}
    latest_activity_at = _latest_activity_at()
    latest_date = datetime.fromisoformat(latest_activity_at).date() if latest_activity_at else None
    status = "fresh" if latest_date and latest_date >= periods[0].start else "stale_or_empty"

    baseline_rows = weekly[-5:-1]
    baseline = {
        key: (
            round(
                statistics.median(
                    float(row[key]) for row in baseline_rows if row.get(key) is not None
                ),
                4,
            )
            if any(row.get(key) is not None for row in baseline_rows)
            else None
        )
        for key in BASELINE_KEYS
    }

    return {
        "status": status,
        "source": "Tambur database via Django ORM",
        "latest_activity_at": latest_activity_at,
        "north_star": {
            "name": "Authenticated Weekly Value Users",
            "users": current["value_users_authenticated"] if status == "fresh" else None,
            "definition": "Уникальные авторизованные пользователи с комментарием, лайком, голосом, отметкой прочтения, избранным или подпиской за неделю.",
            "caveat": "Не включает анонимное meaningful_read; публикации считаются отдельно, потому что Author не всегда однозначно связан с SiteUser.",
        },
        "summary": current,
        "previous_summary": previous,
        "week_over_week_percent": {
            key: _percent_change(current.get(key), previous.get(key))
            for key in BASELINE_KEYS
        },
        "previous_four_weeks_median": baseline,
        "versus_four_week_median_percent": {
            key: _percent_change(current.get(key), baseline.get(key))
            for key in BASELINE_KEYS
        },
        "weekly": weekly,
        "data_notes": [
            "Регистрация не считается ценностным действием сама по себе; отдельно считается same-week activation.",
            "PostLike хранит текущее состояние, поэтому снятые лайки не восстанавливаются как исторические события.",
            "PostRead — серверная отметка прочитанного, но не эквивалент клиентскому meaningful_read 60с/70%.",
        ],
    }


def write_internal_report(
    report: dict[str, Any], output: str | Path | None = None
) -> Path:
    period_end = report["summary"]["end"]
    path = (
        Path(output)
        if output
        else BACKEND_DIR / "var" / "product-analytics" / f"{period_end}-internal.json"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
