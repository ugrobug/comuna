from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from communities import service as community_service
from communities.models import Comun
from feeds.models import PostComment, PostDailyView
from my_feed.models import ComunSubscriptionEvent


def build_community_analytics(comun: Comun) -> dict:
    today = timezone.localdate()
    first_date = today - timedelta(days=29)
    tracking_started_at = timezone.localtime(comun.analytics_tracking_started_at)
    tracking_started_date = tracking_started_at.date()
    dates = [first_date + timedelta(days=offset) for offset in range(30)]
    posts_queryset = community_service._comun_posts_base_queryset(comun)
    post_ids = posts_queryset.values_list("id", flat=True)
    all_time_views = int(
        posts_queryset.aggregate(value=Sum("real_views_count"))["value"] or 0
    )
    all_time_comments = PostComment.objects.filter(
        post_id__in=post_ids,
        is_deleted=False,
    ).count()

    views_by_date = {
        row["date"]: int(row["value"] or 0)
        for row in (
            PostDailyView.objects.filter(post_id__in=post_ids, date__gte=first_date)
            .values("date")
            .annotate(value=Sum("views_count"))
        )
    }
    comments_by_date = {
        row["date"]: int(row["value"] or 0)
        for row in (
            PostComment.objects.filter(
                post_id__in=post_ids,
                is_deleted=False,
                created_at__date__gte=first_date,
            )
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(value=Count("id"))
        )
    }
    subscription_rows = (
        ComunSubscriptionEvent.objects.filter(
            comun=comun,
            created_at__date__gte=max(first_date, tracking_started_date),
        )
        .annotate(date=TruncDate("created_at"))
        .values("date", "action")
        .annotate(value=Count("id"))
    )
    subscribers_gained_by_date: dict = defaultdict(int)
    subscribers_lost_by_date: dict = defaultdict(int)
    for row in subscription_rows:
        target = (
            subscribers_lost_by_date
            if row["action"] == ComunSubscriptionEvent.ACTION_UNSUBSCRIBE
            else subscribers_gained_by_date
        )
        target[row["date"]] += int(row["value"] or 0)

    series = [
        {
            "date": day.isoformat(),
            "views": views_by_date.get(day, 0),
            "comments": comments_by_date.get(day, 0),
            "subscribers_gained": subscribers_gained_by_date.get(day, 0),
            "subscribers_lost": subscribers_lost_by_date.get(day, 0),
            "subscribers_net": (
                subscribers_gained_by_date.get(day, 0)
                - subscribers_lost_by_date.get(day, 0)
            ),
        }
        for day in dates
    ]

    def period_totals(days: int) -> dict:
        start = today - timedelta(days=days - 1)
        rows = [row for row in series if row["date"] >= start.isoformat()]
        gained = sum(row["subscribers_gained"] for row in rows)
        lost = sum(row["subscribers_lost"] for row in rows)
        return {
            "views": sum(row["views"] for row in rows),
            "comments": sum(row["comments"] for row in rows),
            "subscribers_gained": gained,
            "subscribers_lost": lost,
            "subscribers_net": gained - lost,
        }

    return {
        "ok": True,
        "comun": {
            "id": comun.id,
            "slug": comun.slug,
            "name": comun.name,
            "subscribers_count": int(comun.subscribers_count or 0),
        },
        "periods": {
            "all_time": {
                "views": all_time_views,
                "comments": all_time_comments,
            },
            "day": period_totals(1),
            "week": period_totals(7),
            "month": period_totals(30),
        },
        "series": series,
        "tracking": {
            "started_at": tracking_started_at.isoformat(),
        },
    }
