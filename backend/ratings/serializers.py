from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest

from ratings.service import author_rating_value


def _author_avatar_url(request: HttpRequest | None, author: Any) -> str | None:
    avatar_image = getattr(author, "avatar_image", None)
    if avatar_image:
        try:
            site_base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
            if site_base:
                return f"{site_base}{avatar_image.url}"
            if request is not None:
                return request.build_absolute_uri(avatar_image.url)
            return avatar_image.url
        except Exception:
            pass
    return getattr(author, "avatar_url", None) or None


def serialize_top_author_item(
    author: Any,
    *,
    request: HttpRequest | None = None,
    period: str = "month",
) -> dict[str, Any]:
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
        "author_rating": author_rating_value(getattr(author, "rating_total", 0)),
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


__all__ = [
    "serialize_top_author_item",
]
