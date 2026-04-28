from __future__ import annotations

from django.http import HttpRequest

from feeds.models import Post
from my_feed.models import ThematicFeed


def _fv():
    from feeds import views as feeds_views

    return feeds_views


def _serialize_thematic_feed(
    feed: ThematicFeed,
    *,
    include_manage_fields: bool = False,
) -> dict:
    moderators = list(feed.moderators.order_by("username"))
    authors = list(feed.authors.filter(is_blocked=False).order_by("username"))
    excluded_authors = list(feed.excluded_authors.filter(is_blocked=False).order_by("username"))
    rubrics = list(feed.rubrics.filter(is_active=True, is_hidden=False).order_by("sort_order", "name"))
    tags = list(feed.tags.filter(is_active=True).order_by("name"))
    blocked_tags = list(feed.blocked_tags.filter(is_active=True).order_by("name"))

    payload = {
        "id": feed.id,
        "name": feed.name,
        "slug": feed.slug,
        "description": feed.description,
        "is_active": feed.is_active,
        "sort_order": feed.sort_order,
        "moderators_count": len(moderators),
        "authors_count": len(authors),
        "excluded_authors_count": len(excluded_authors),
        "rubrics_count": len(rubrics),
        "tags_count": len(tags),
        "blocked_tags_count": len(blocked_tags),
        "moderators": [{"id": moderator.id, "username": moderator.username} for moderator in moderators],
        "authors": [{"id": author.id, "username": author.username, "title": author.title} for author in authors],
        "excluded_authors": [
            {"id": author.id, "username": author.username, "title": author.title}
            for author in excluded_authors
        ],
        "tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in tags
        ],
        "rubrics": [
            {
                "id": rubric.id,
                "name": rubric.name,
                "slug": rubric.slug,
                "description": rubric.description,
            }
            for rubric in rubrics
        ],
        "blocked_tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in blocked_tags
        ],
        "excluded_tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or _fv()._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in blocked_tags
        ],
    }
    if include_manage_fields:
        payload["moderator_ids"] = [moderator.id for moderator in moderators]
        payload["author_ids"] = [author.id for author in authors]
        payload["excluded_author_ids"] = [author.id for author in excluded_authors]
        payload["rubric_ids"] = [rubric.id for rubric in rubrics]
        payload["tag_ids"] = [tag.id for tag in tags]
        payload["excluded_tag_ids"] = [tag.id for tag in blocked_tags]
    return payload


def _serialize_feed_post_card(
    request: HttpRequest,
    post: Post,
    current_user,
    *,
    now,
    is_favorite: bool = False,
) -> dict:
    rubric = post.rubric
    content, poll_payload = _fv()._content_with_live_poll(post, current_user)
    author_channel_url, author_title = _fv()._author_display_fields(
        request,
        post.author,
        rubric,
        post.channel_url,
    )
    return {
        "id": post.id,
        "title": _fv()._post_display_title(post),
        "template": _fv()._serialize_post_template(post),
        "rubric": rubric.name if rubric else None,
        "rubric_slug": rubric.slug if rubric else None,
        "rubric_icon_url": _fv()._rubric_icon_url(request, rubric),
        "comun": _fv().community_service._serialize_post_comun(request, post),
        "content": content,
        "poll": poll_payload,
        "source_url": post.source_url,
        "channel_url": author_channel_url,
        "created_at": post.created_at.isoformat(),
        "author": {
            "username": post.author.username,
            "title": author_title,
            "channel_url": author_channel_url,
            "avatar_url": _fv()._author_avatar_for_rubric(request, post.author, rubric),
            **_fv()._author_admin_fields_for_user(current_user, post.author, rubric),
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
    "_serialize_thematic_feed",
]
