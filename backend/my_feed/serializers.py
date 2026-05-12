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
    content, poll_payload = _fv()._content_with_live_poll(post, current_user)
    template_payload = _fv()._serialize_post_template(post)
    author_channel_url, author_title = _fv()._author_display_fields(
        request,
        post.author,
        post.channel_url,
    )
    return {
        "id": post.id,
        "title": _fv()._post_display_title(post),
        "template": template_payload,
        "comun": _fv().community_service._serialize_post_comun(request, post),
        "content": content,
        "poll": poll_payload,
        **_fv()._serialize_post_preview_image_fields(request, post, template_payload),
        "source_url": post.source_url,
        "channel_url": author_channel_url,
        "created_at": post.created_at.isoformat(),
        "author": {
            "username": post.author.username,
            "title": author_title,
            "channel_url": author_channel_url,
            "avatar_url": _fv()._author_avatar_for_display(request, post.author),
            **_fv()._author_admin_fields_for_user(current_user, post.author),
        },
        "tags": _fv()._serialize_tags(post.tags.all()),
        "is_favorite": is_favorite,
        "score": post.rating + post.comments_count * 5,
        "rating": post.rating,
        "comments_count": post.comments_count,
        "likes_count": post.rating,
        "views_count": _fv()._post_total_views(post, now),
    }


__all__ = [
    "_serialize_feed_post_card",
]
