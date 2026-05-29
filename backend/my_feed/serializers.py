from __future__ import annotations

from django.http import HttpRequest

from feeds.models import Post


def _fv():
    from feeds import views as feeds_views

    return feeds_views


def _serialize_feed_post_card(
    request: HttpRequest,
    post: Post,
    current_user,
    *,
    now,
    is_favorite: bool = False,
) -> dict:
    return _fv()._serialize_backend_post_card(
        request,
        post,
        current_user,
        now=now,
        is_favorite=is_favorite,
    )


__all__ = [
    "_serialize_feed_post_card",
]
