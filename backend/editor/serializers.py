from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count
from django.http import HttpRequest

from editor import service as editor_service
from editor.models import (
    POST_TEMPLATE_TYPE_BUG_REPORT,
    POST_TEMPLATE_TYPE_POST_VOTE_POLL,
    PostBugReportConfirmation,
    PostRatingVote,
    PostTemplateConfig,
    default_enabled_template_editor_blocks,
    normalize_template_editor_blocks_for_template,
)
from feeds.models import Post, PostFavorite
from communities.models import Comun, ComunPostCategoryAssignment
from rabotaem_backend.media_urls import rewrite_public_media_payload, rewrite_public_media_urls

User = get_user_model()


def _fv():
    from feeds import views as feed_views

    return feed_views


def _serialize_post_template(post: Post) -> dict | None:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    normalized_template, _template_error = editor_service._normalize_post_template_payload(
        raw_data.get("template")
    )
    return rewrite_public_media_payload(normalized_template)


def _content_with_live_poll(post: Post, user: User | None = None) -> tuple[str, dict | None]:
    content = post.content or ""
    content = _fv()._replace_legacy_audio_embed(post, content)
    live_poll = _fv()._live_poll_for_post(post, user)
    if not live_poll:
        return rewrite_public_media_urls(content), None

    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    template_payload = _serialize_post_template(post)
    template_type = (
        str(template_payload.get("type") or "").strip().lower() if isinstance(template_payload, dict) else ""
    )
    if template_type == POST_TEMPLATE_TYPE_POST_VOTE_POLL:
        return rewrite_public_media_urls(content), live_poll["poll"]

    if _fv()._content_contains_inline_poll(content):
        return rewrite_public_media_urls(content), live_poll["poll"]

    poll_html = live_poll["html"]
    stored_poll_html = raw_data.get("poll_html")
    if isinstance(stored_poll_html, str) and stored_poll_html and stored_poll_html in content:
        return rewrite_public_media_urls(content.replace(stored_poll_html, poll_html, 1)), live_poll["poll"]
    if not content:
        return rewrite_public_media_urls(poll_html), live_poll["poll"]
    if '<div class="post-poll"' not in content and poll_html not in content:
        return rewrite_public_media_urls(f"{content}<br><br>{poll_html}"), live_poll["poll"]
    return rewrite_public_media_urls(content), live_poll["poll"]


def _serialize_post_rating_block(
    post: Post,
    user: User | None,
    block_id: str,
    *,
    include_legacy_votes: bool = False,
) -> dict:
    current_votes = PostRatingVote.objects.filter(post=post, block_id=block_id)
    current_aggregate = current_votes.aggregate(
        average_value=Avg("value"),
        votes_count=Count("id"),
    )

    votes_count = max(int(current_aggregate.get("votes_count") or 0), 0)
    average_raw = current_aggregate.get("average_value")
    weighted_sum = float(average_raw) * votes_count if average_raw is not None else 0.0

    user_vote = None
    if user:
        user_vote = current_votes.filter(user=user).values_list("value", flat=True).first()
        if user_vote is not None:
            user_vote = int(user_vote)

    if include_legacy_votes:
        legacy_votes = PostRatingVote.objects.filter(post=post, block_id="")
        legacy_aggregate = legacy_votes.aggregate(
            average_value=Avg("value"),
            votes_count=Count("id"),
        )
        legacy_votes_count = max(int(legacy_aggregate.get("votes_count") or 0), 0)
        legacy_average_raw = legacy_aggregate.get("average_value")
        if legacy_average_raw is not None and legacy_votes_count > 0:
            weighted_sum += float(legacy_average_raw) * legacy_votes_count
            votes_count += legacy_votes_count
        if user and user_vote is None:
            legacy_user_vote = legacy_votes.filter(user=user).values_list("value", flat=True).first()
            if legacy_user_vote is not None:
                user_vote = int(legacy_user_vote)

    average_value = round(weighted_sum / votes_count, 1) if votes_count > 0 else None
    return {
        "block_id": block_id,
        "scale_min": 1,
        "scale_max": 10,
        "average_value": average_value,
        "votes_count": votes_count,
        "user_vote": user_vote,
    }


def _serialize_post_ratings(post: Post, user: User | None = None) -> dict[str, dict]:
    block_ids = editor_service._extract_inline_post_rating_blocks(post.content or "")
    if not block_ids:
        return {}

    include_legacy_votes = len(block_ids) == 1
    return {
        block_id: _serialize_post_rating_block(
            post,
            user,
            block_id,
            include_legacy_votes=include_legacy_votes and index == 0,
        )
        for index, block_id in enumerate(block_ids)
    }


def _serialize_post_rating(
    post: Post,
    user: User | None = None,
    *,
    template_payload: dict | None = None,
) -> dict | None:
    del template_payload
    ratings = _serialize_post_ratings(post, user)
    if not ratings:
        return None
    first_key = next(iter(ratings.keys()), "")
    return ratings.get(first_key)


def _serialize_enabled_template_editor_blocks(
    template_payload: dict | None = None,
) -> list[str]:
    template_type = editor_service._template_type_from_payload(template_payload)
    config = (
        PostTemplateConfig.objects.filter(template_type=template_type, is_active=True)
        .values("enabled_editor_blocks")
        .first()
    )
    if not config:
        return default_enabled_template_editor_blocks(template_type)
    return normalize_template_editor_blocks_for_template(
        template_type, config.get("enabled_editor_blocks")
    )


def _user_can_manage_bug_report_status(user: User | None, post: Post) -> bool:
    if not user:
        return False
    template_payload = _serialize_post_template(post)
    if (
        not isinstance(template_payload, dict)
        or str(template_payload.get("type") or "").strip() != POST_TEMPLATE_TYPE_BUG_REPORT
    ):
        return False
    if bool(getattr(user, "is_staff", False)):
        return True
    comun = _fv().community_service._post_comun(post)
    if not comun:
        return False
    return _fv().community_service._comun_is_moderator(user, comun)


def _serialize_bug_report_confirmation(post: Post, user: User | None) -> dict | None:
    template_payload = _serialize_post_template(post)
    if (
        not isinstance(template_payload, dict)
        or str(template_payload.get("type") or "").strip() != POST_TEMPLATE_TYPE_BUG_REPORT
    ):
        return None
    confirmations = PostBugReportConfirmation.objects.filter(post=post)
    return {
        "count": confirmations.count(),
        "confirmed": confirmations.filter(user=user).exists() if user else False,
    }


def _serialize_post_for_user(request: HttpRequest, post: Post, user: User | None = None) -> dict:
    author_channel_url, author_title = _fv()._author_display_fields(
        request, post.author, post.channel_url
    )
    content, poll_payload = _content_with_live_poll(post, user)
    template_payload = _serialize_post_template(post)
    is_favorite = PostFavorite.objects.filter(post=post, user=user).exists() if user else False
    is_draft = editor_service._is_post_draft(post)
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    comun = None
    comun_slug = str(raw_data.get("comun_slug") or "").strip()
    if comun_slug:
        comun = Comun.objects.filter(slug=comun_slug).first()
    assignment = None
    if comun:
        assignment = (
            ComunPostCategoryAssignment.objects.select_related("category")
            .filter(comun=comun, post=post)
            .first()
        )
    else:
        assignment = (
            ComunPostCategoryAssignment.objects.select_related("category", "comun")
            .filter(post=post)
            .first()
        )
        if assignment:
            comun = assignment.comun
            comun_slug = comun.slug
    payload = {
        "id": post.id,
        "title": _fv()._post_display_title(post),
        "template": template_payload,
        "enabled_template_editor_blocks": _serialize_enabled_template_editor_blocks(template_payload),
        "content": content,
        "poll": poll_payload,
        "post_ratings": _serialize_post_ratings(post, user),
        "post_rating": _serialize_post_rating(post, user, template_payload=template_payload),
        **_fv()._serialize_post_preview_image_fields(request, post, template_payload),
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat(),
        "is_pending": post.is_pending,
        "is_draft": is_draft,
        "publish_at": post.publish_at.isoformat() if post.publish_at else None,
        "comun_slug": comun_slug or None,
        "comun": (
            {
                "id": comun.id,
                "name": comun.name,
                "slug": comun.slug,
                "logo_url": _fv().community_service._comun_logo_url(request, comun),
            }
            if comun
            else None
        ),
        "comun_category_id": assignment.category_id if assignment and assignment.category_id else raw_data.get("comun_category_id"),
        "comun_category": (
            {
                "id": assignment.category.id,
                "name": assignment.category.name,
                "slug": assignment.category.slug,
            }
            if assignment and assignment.category_id
            else None
        ),
        "comments_count": post.comments_count,
        "likes_count": post.rating,
        "views_count": _fv()._post_total_views(post),
        "tags": _fv()._serialize_tags(post.tags.all()),
        "is_favorite": is_favorite,
        "can_manage": editor_service._user_can_manage_site_post(user, post),
        "can_manage_bug_report_status": _user_can_manage_bug_report_status(user, post),
        "bug_report_confirmation": _serialize_bug_report_confirmation(post, user),
        "author": {
            "username": post.author.username,
            "title": author_title,
            "channel_url": author_channel_url,
            "avatar_url": _fv()._author_avatar_for_display(request, post.author),
            **_fv()._author_admin_fields_for_user(user, post.author),
        },
    }
    if is_draft and editor_service._user_can_manage_site_post(user, post):
        payload["draft_share_token"] = editor_service._post_draft_share_token(post)
    return payload


__all__ = [
    "_content_with_live_poll",
    "_serialize_enabled_template_editor_blocks",
    "_serialize_post_for_user",
    "_serialize_bug_report_confirmation",
    "_serialize_post_rating",
    "_serialize_post_rating_block",
    "_serialize_post_ratings",
    "_serialize_post_template",
    "_user_can_manage_bug_report_status",
]
