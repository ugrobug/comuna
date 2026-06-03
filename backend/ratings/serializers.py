from __future__ import annotations

from typing import Any

from django.http import HttpRequest
from django.db.models import Sum

from rabotaem_backend.media_urls import public_url
from ratings.service import author_rating_value
from telegram_integration.media import safe_public_url


def _author_avatar_url(request: HttpRequest | None, author: Any) -> str | None:
    avatar_image = getattr(author, "avatar_image", None)
    if avatar_image:
        try:
            return public_url(avatar_image.url, request=request)
        except Exception:
            pass
    return safe_public_url(getattr(author, "avatar_url", None))


def serialize_top_author_item(
    author: Any,
    *,
    request: HttpRequest | None = None,
    period: str = "month",
) -> dict[str, Any]:
    if hasattr(author, "period_rating_score"):
        rating_value = round(float(getattr(author, "period_rating_score", 0) or 0), 2)
    else:
        rating_total = getattr(author, "period_rating_total", 0) or 0
        rating_value = author_rating_value(rating_total)
    posts_count = getattr(author, "posts_count", 0) or 0
    item: dict[str, Any] = {
        "username": author.username,
        "title": getattr(author, "title", ""),
        "avatar_url": _author_avatar_url(request, author),
        "channel_url": getattr(author, "invite_url", "") or getattr(author, "channel_url", ""),
        "rating": rating_value,
        "score": rating_value,
        "posts_count": posts_count,
        "author_rating": round(float(getattr(author, "rating_score", rating_value) or 0), 2),
        "period": period,
    }
    if period == "month":
        item["month_rating"] = rating_value
        item["month_score"] = rating_value
        item["month_posts"] = posts_count
    elif period == "week":
        item["week_rating"] = rating_value
        item["week_score"] = rating_value
        item["week_posts"] = posts_count
    else:
        item["all_time_rating"] = rating_value
        item["all_time_score"] = rating_value
        item["all_time_posts"] = posts_count
    return item


def serialize_top_comun_item(
    comun: Any,
    *,
    request: HttpRequest | None = None,
) -> dict[str, Any]:
    from communities import service as community_service

    posts_count = 0
    comments_count = 0
    try:
        base_posts = community_service._comun_posts_base_queryset(comun)
        posts_count = base_posts.count()
        comments_count = int(
            base_posts.aggregate(total=Sum("comments_count")).get("total")
            or 0
        )
    except Exception:
        posts_count = 0
        comments_count = 0
    try:
        rating_value = round(float(getattr(comun, "rating_score", 0) or 0), 2)
    except (TypeError, ValueError):
        rating_value = 0.0
    return {
        "id": getattr(comun, "id", None),
        "slug": getattr(comun, "slug", ""),
        "name": getattr(comun, "name", ""),
        "title": getattr(comun, "name", ""),
        "logo_url": community_service._comun_logo_url(request, comun),
        "avatar_url": community_service._comun_logo_url(request, comun),
        "rating": rating_value,
        "score": rating_value,
        "posts_count": posts_count,
        "comments_count": comments_count,
    }


__all__ = [
    "serialize_top_comun_item",
    "serialize_top_author_item",
]
