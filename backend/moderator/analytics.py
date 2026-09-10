from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db.models import Sum
from django.http import HttpRequest
from django.utils import timezone

from communities import service as community_service
from communities.models import Comun
from feeds.models import Author, Post, PostComment, PostCommentLike, PostLike
from my_feed.models import ComunSubscriptionEvent
from users.models import SiteUserProfile


SITE_POST_SOURCES = {"manual", "manual_comun"}
DEFAULT_PERIOD_DAYS = 30


def parse_date_param(value: str | None, *, end_of_day: bool = False):
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    moment = time.max if end_of_day else time.min
    return timezone.make_aware(datetime.combine(parsed, moment), timezone.get_current_timezone())


def analytics_period(request: HttpRequest) -> tuple[datetime, datetime]:
    now = timezone.now()
    starts_at = parse_date_param(request.GET.get("from"))
    ends_at = parse_date_param(request.GET.get("to"), end_of_day=True)

    if starts_at is None and ends_at is None:
        ends_at = now
        starts_at = ends_at - timedelta(days=DEFAULT_PERIOD_DAYS)
    elif starts_at is None:
        starts_at = ends_at - timedelta(days=DEFAULT_PERIOD_DAYS)
    elif ends_at is None:
        ends_at = now

    if starts_at > ends_at:
        raise ValueError("from must be before to")
    return starts_at, ends_at


def created_between(field_name: str, starts_at: datetime, ends_at: datetime) -> dict[str, datetime]:
    return {
        f"{field_name}__gte": starts_at,
        f"{field_name}__lte": ends_at,
    }


def serialize_period(starts_at: datetime, ends_at: datetime) -> dict[str, str]:
    return {
        "from": starts_at.date().isoformat(),
        "to": ends_at.date().isoformat(),
    }


def public_posts_queryset():
    return Post.objects.filter(
        is_blocked=False,
        is_pending=False,
        author__is_blocked=False,
    )


def build_moderator_analytics(
    request: HttpRequest,
    *,
    starts_at: datetime,
    ends_at: datetime,
) -> dict:
    post_period = created_between("created_at", starts_at, ends_at)
    public_posts = public_posts_queryset().filter(**post_period)
    site_posts = public_posts.filter(raw_data__source__in=SITE_POST_SOURCES)
    public_posts_count = public_posts.count()
    post_real_views = int(public_posts.aggregate(total=Sum("real_views_count"))["total"] or 0)
    average_real_views_per_post = (
        round(post_real_views / public_posts_count, 2) if public_posts_count else 0
    )

    post_likes_count = PostLike.objects.filter(
        value__gt=0,
        **created_between("created_at", starts_at, ends_at),
    ).count()
    comment_likes_count = PostCommentLike.objects.filter(
        **created_between("created_at", starts_at, ends_at),
    ).count()

    totals = {
        "communities": Comun.objects.filter(
            is_active=True,
            **created_between("created_at", starts_at, ends_at),
        ).count(),
        "authors": Author.objects.filter(
            is_blocked=False,
            **created_between("created_at", starts_at, ends_at),
        ).count(),
        "comments": PostComment.objects.filter(
            is_deleted=False,
            **created_between("created_at", starts_at, ends_at),
        ).count(),
        "likes": post_likes_count + comment_likes_count,
        "registered_users": SiteUserProfile.objects.filter(
            deleted_at__isnull=True,
            registration_source__gt="",
            **created_between("created_at", starts_at, ends_at),
        ).count(),
        "community_subscriptions": ComunSubscriptionEvent.objects.filter(
            **created_between("created_at", starts_at, ends_at),
        ).count(),
        "posts_site": site_posts.count(),
        "post_real_views": post_real_views,
        "average_real_views_per_post": average_real_views_per_post,
    }
    recent_communities = list(
        Comun.objects.filter(is_active=True).order_by("-created_at", "-id")[:10]
    )

    return {
        "ok": True,
        "period": serialize_period(starts_at, ends_at),
        "totals": totals,
        "breakdown": {
            "post_likes": post_likes_count,
            "comment_likes": comment_likes_count,
        },
        "recent_communities": [
            {
                "id": comun.id,
                "name": comun.name,
                "slug": comun.slug,
                "url": f"/comuns/{comun.slug}",
                "logo_url": community_service._comun_logo_url(request, comun),
                "description": (comun.product_description or "").strip(),
                "created_at": comun.created_at.isoformat(),
            }
            for comun in recent_communities
        ],
    }
