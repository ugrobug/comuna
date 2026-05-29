from __future__ import annotations

import json
from datetime import datetime, time, timedelta

from django.db.models import Q, Sum
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from communities.models import Comun
from feeds.models import Author, Post, PostComment, PostCommentLike, PostLike
from ratings.service import (
    get_rating_settings,
    serialize_rating_settings,
    update_rating_settings,
)
from users.service import _get_user_from_request

_SITE_POST_SOURCES = {"manual", "manual_comun"}
_DEFAULT_PERIOD_DAYS = 30
_MAX_DISPLAY_VIEWS_TARGET = 1_000_000


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


def _telegram_channel_post_query() -> Q:
    return (
        Q(raw_data__chat__type="channel")
        | Q(author__channel_id__isnull=False)
        | Q(source_url__icontains="t.me/")
    )


def _staff_user_or_response(request: HttpRequest):
    user = _get_user_from_request(request)
    if not user:
        return None, JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if not user.is_staff:
        return None, JsonResponse({"ok": False, "error": "forbidden"}, status=403)
    return user, None


def _public_posts_queryset():
    return Post.objects.filter(
        is_blocked=False,
        is_pending=False,
        author__is_blocked=False,
    )


def _serialize_post_view_settings(post: Post, now=None) -> dict:
    from feeds.views import _post_display_views_current, _post_total_views

    if now is None:
        now = timezone.now()
    return {
        "id": post.id,
        "title": (post.title or "").strip() or f"Пост #{post.id}",
        "author": {
            "id": post.author_id,
            "username": post.author.username,
            "title": (post.author.title or "").strip() or None,
        },
        "created_at": post.created_at.isoformat(),
        "real_views_count": int(post.real_views_count or 0),
        "display_views_target": int(post.display_views_target or 0),
        "display_views_current": _post_display_views_current(post, now=now),
        "views_total": _post_total_views(post, now=now),
    }


def moderator_analytics(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    _user, auth_response = _staff_user_or_response(request)
    if auth_response is not None:
        return auth_response

    try:
        starts_at, ends_at = _analytics_period(request)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    post_period = _created_between("created_at", starts_at, ends_at)
    public_posts = _public_posts_queryset().filter(**post_period)
    site_posts = public_posts.filter(raw_data__source__in=_SITE_POST_SOURCES)
    telegram_posts = public_posts.exclude(raw_data__source__in=_SITE_POST_SOURCES).filter(
        _telegram_channel_post_query()
    )
    public_posts_count = public_posts.count()
    post_real_views = int(public_posts.aggregate(total=Sum("real_views_count"))["total"] or 0)
    average_real_views_per_post = (
        round(post_real_views / public_posts_count, 2) if public_posts_count else 0
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
        "post_real_views": post_real_views,
        "average_real_views_per_post": average_real_views_per_post,
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


def moderator_post_view_settings(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    _user, auth_response = _staff_user_or_response(request)
    if auth_response is not None:
        return auth_response

    try:
        limit = min(max(int(request.GET.get("limit", "20")), 1), 100)
    except ValueError:
        limit = 20
    query = (request.GET.get("q") or "").strip()

    posts = _public_posts_queryset().select_related("author").order_by("-created_at", "-id")
    if query:
        filters = (
            Q(title__icontains=query)
            | Q(author__username__icontains=query)
            | Q(author__title__icontains=query)
        )
        if query.isdigit():
            filters |= Q(id=int(query))
        posts = posts.filter(filters)

    now = timezone.now()
    return JsonResponse(
        {
            "ok": True,
            "posts": [_serialize_post_view_settings(post, now=now) for post in posts[:limit]],
        }
    )


@csrf_exempt
def moderator_post_view_setting_update(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method not in {"PATCH", "POST"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    _user, auth_response = _staff_user_or_response(request)
    if auth_response is not None:
        return auth_response

    post = _public_posts_queryset().select_related("author").filter(id=post_id).first()
    if not post:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
        display_views_target = int(payload.get("display_views_target"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "error": "invalid display_views_target"}, status=400)

    if display_views_target < 0 or display_views_target > _MAX_DISPLAY_VIEWS_TARGET:
        return JsonResponse(
            {
                "ok": False,
                "error": f"display_views_target must be between 0 and {_MAX_DISPLAY_VIEWS_TARGET}",
            },
            status=400,
        )

    post.set_display_views_target(display_views_target, save=True)
    return JsonResponse({"ok": True, "post": _serialize_post_view_settings(post)})


def moderator_rating_settings(request: HttpRequest) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    _user, auth_response = _staff_user_or_response(request)
    if auth_response is not None:
        return auth_response

    return JsonResponse(
        {
            "ok": True,
            "settings": serialize_rating_settings(get_rating_settings()),
        }
    )


@csrf_exempt
def moderator_rating_settings_update(request: HttpRequest) -> HttpResponse:
    if request.method not in {"PATCH", "POST"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    _user, auth_response = _staff_user_or_response(request)
    if auth_response is not None:
        return auth_response

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    try:
        settings = update_rating_settings(payload)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    from communities import service as community_service

    recalculated = 0
    for comun_id in Comun.objects.filter(is_active=True).values_list("id", flat=True):
        community_service._recalculate_comun_rating(comun_id)
        recalculated += 1

    return JsonResponse(
        {
            "ok": True,
            "settings": serialize_rating_settings(settings),
            "recalculated_comuns": recalculated,
        }
    )


__all__ = [
    "moderator_analytics",
    "moderator_post_view_settings",
    "moderator_post_view_setting_update",
    "moderator_rating_settings",
    "moderator_rating_settings_update",
]
