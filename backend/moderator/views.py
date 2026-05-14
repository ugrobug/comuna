from __future__ import annotations

from datetime import datetime, time, timedelta

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone

from communities.models import Comun
from feeds.models import Author, Post, PostComment, PostCommentLike, PostLike
from users.service import _get_user_from_request

_SITE_POST_SOURCES = {"manual", "manual_comun"}
_DEFAULT_PERIOD_DAYS = 30


def _parse_date_param(value: str | None, *, end_of_day: bool = False):
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("date must use YYYY-MM-DD")
    moment = time.max if end_of_day else time.min
    return timezone.make_aware(datetime.combine(parsed, moment), timezone.get_current_timezone())


def _analytics_period(request: HttpRequest) -> tuple[datetime, datetime]:
    now = timezone.now()
    starts_at = _parse_date_param(request.GET.get("from"))
    ends_at = _parse_date_param(request.GET.get("to"), end_of_day=True)

    if starts_at is None and ends_at is None:
        ends_at = now
        starts_at = ends_at - timedelta(days=_DEFAULT_PERIOD_DAYS)
    elif starts_at is None:
        starts_at = ends_at - timedelta(days=_DEFAULT_PERIOD_DAYS)
    elif ends_at is None:
        ends_at = now

    if starts_at > ends_at:
        raise ValueError("from must be before to")

    return starts_at, ends_at


def _created_between(field_name: str, starts_at: datetime, ends_at: datetime) -> dict[str, datetime]:
    return {
        f"{field_name}__gte": starts_at,
        f"{field_name}__lte": ends_at,
    }


def _serialize_period(starts_at: datetime, ends_at: datetime) -> dict[str, str]:
    return {
        "from": starts_at.date().isoformat(),
        "to": ends_at.date().isoformat(),
    }


def moderator_analytics(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if not user.is_staff:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        starts_at, ends_at = _analytics_period(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    post_period = _created_between("created_at", starts_at, ends_at)
    public_posts = Post.objects.filter(
        is_blocked=False,
        is_pending=False,
        author__is_blocked=False,
        **post_period,
    )
    site_posts = public_posts.filter(raw_data__source__in=_SITE_POST_SOURCES)
    telegram_posts = public_posts.filter(source_url__icontains="t.me/").exclude(
        raw_data__source__in=_SITE_POST_SOURCES
    )

    post_likes_count = PostLike.objects.filter(
        value__gt=0,
        **_created_between("created_at", starts_at, ends_at),
    ).count()
    comment_likes_count = PostCommentLike.objects.filter(
        **_created_between("created_at", starts_at, ends_at),
    ).count()

    totals = {
        "communities": Comun.objects.filter(
            is_active=True,
            **_created_between("created_at", starts_at, ends_at),
        ).count(),
        "authors": Author.objects.filter(
            is_blocked=False,
            **_created_between("created_at", starts_at, ends_at),
        ).count(),
        "comments": PostComment.objects.filter(
            is_deleted=False,
            **_created_between("created_at", starts_at, ends_at),
        ).count(),
        "likes": post_likes_count + comment_likes_count,
        "posts_telegram": telegram_posts.count(),
        "posts_site": site_posts.count(),
    }

    return JsonResponse(
        {
            "ok": True,
            "period": _serialize_period(starts_at, ends_at),
            "totals": totals,
            "breakdown": {
                "post_likes": post_likes_count,
                "comment_likes": comment_likes_count,
            },
        }
    )


__all__ = ["moderator_analytics"]
