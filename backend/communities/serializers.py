from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.http import HttpRequest

from communities.models import (
    Comun,
    ComunCategory,
    ComunGlossaryTerm,
    ComunPostCategoryAssignment,
    ComunVote,
)
from editor.models import PostPollVote
from communities import service as community_service
from editor import service as editor_service
from feeds.models import Author, Post, PostComment, PostCommentLike, PostFavorite, PostLike, PostRead, Tag

User = get_user_model()


def _serialize_comun_glossary_term(term: ComunGlossaryTerm) -> dict:
    return {
        "id": term.id,
        "term": term.term,
        "slug": term.slug,
        "definition": term.definition,
        "sort_order": term.sort_order,
    }


def _serialize_author_source_summary(
    request: HttpRequest | None,
    author: Author | None,
) -> dict | None:
    if not author:
        return None
    return {
        "id": author.id,
        "username": author.username,
        "title": (author.title or "").strip() or None,
        "channel_url": (author.invite_url or author.channel_url or "").strip() or None,
        "avatar_url": community_service._author_avatar_url(request, author),
    }


def _serialize_comun_profile_card(
    request: HttpRequest,
    comun: Comun,
    *,
    current_user: User | None = None,
    role: str = "moderator",
) -> dict:
    tags = list(comun.tags.filter(is_active=True).order_by("name"))
    return {
        "id": comun.id,
        "name": comun.name,
        "slug": comun.slug,
        "logo_url": community_service._comun_logo_url(request, comun),
        "product_description": comun.product_description,
        "target_audience": comun.target_audience,
        "website_url": comun.website_url,
        "role": role,
        "can_moderate": community_service._comun_is_moderator(current_user, comun),
        "creator": {
            "id": comun.creator_id,
            "username": comun.creator.username if getattr(comun, "creator", None) else None,
            "display_name": (
                (
                    getattr(
                        getattr(getattr(comun, "creator", None), "site_profile", None),
                        "display_name",
                        "",
                    )
                    or ""
                ).strip()
                or None
            ),
        },
        "tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or community_service._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in tags
        ],
        "categories_count": community_service._comun_categories_count(comun),
    }


def _serialize_comun_category(category: ComunCategory, comun: Comun | None = None) -> dict:
    category_allowed_template_types = community_service._allowed_template_overrides_for_comun_category(category)
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "sort_order": category.sort_order,
        "only_moderators_can_post": bool(getattr(category, "only_moderators_can_post", False)),
        "hide_from_home": bool(getattr(category, "hide_from_home", False)),
        "category_allowed_template_types": category_allowed_template_types,
        "allowed_template_types": community_service._allowed_templates_for_comun_category(comun, category),
        "inherits_comun_template_types": not bool(category_allowed_template_types),
    }


def _serialize_comun_rating(
    comun: Comun,
    *,
    current_user: User | None = None,
    user_vote: int | None = None,
) -> dict:
    if user_vote is None and current_user:
        user_vote = int(
            ComunVote.objects.filter(comun_id=comun.id, user_id=current_user.id)
            .values_list("value", flat=True)
            .first()
            or 0
        )
    try:
        score = round(float(getattr(comun, "rating_score", 0) or 0), 2)
    except (TypeError, ValueError):
        score = 0.0
    if isinstance(getattr(comun, "rating_score", None), Decimal):
        score = float(getattr(comun, "rating_score", 0) or 0)
    return {
        "score": score,
        "upvotes": int(getattr(comun, "votes_up", 0) or 0),
        "downvotes": int(getattr(comun, "votes_down", 0) or 0),
        "user_vote": int(user_vote or 0),
    }


def _serialize_comun_activity(
    request: HttpRequest,
    comun: Comun,
    *,
    top_limit: int = 8,
) -> dict:
    base_posts = community_service._comun_posts_base_queryset(comun)
    if not base_posts.exists():
        return {
            "participants_count": 0,
            "top_members": [],
            "points": dict(community_service._COMUN_ACTIVITY_POINTS),
        }

    points_by_user: dict[int, int] = defaultdict(int)
    stats_by_user: dict[int, dict[str, int]] = defaultdict(dict)

    def _add_points(user_id: int | None, key: str, count: int) -> None:
        if not user_id or count <= 0:
            return
        multiplier = int(community_service._COMUN_ACTIVITY_POINTS.get(key, 0) or 0)
        if multiplier <= 0:
            return
        points_by_user[user_id] += count * multiplier
        stats_by_user[user_id][key] = stats_by_user[user_id].get(key, 0) + count

    for row in (
        PostComment.objects.filter(post__in=base_posts, is_deleted=False)
        .values("user_id")
        .annotate(count=Count("id"))
    ):
        _add_points(row.get("user_id"), "comment", int(row.get("count") or 0))

    for row in (
        PostLike.objects.filter(post__in=base_posts)
        .values("user_id")
        .annotate(count=Count("id"))
    ):
        _add_points(row.get("user_id"), "post_vote", int(row.get("count") or 0))

    for row in (
        PostCommentLike.objects.filter(comment__post__in=base_posts)
        .values("user_id")
        .annotate(count=Count("id"))
    ):
        _add_points(row.get("user_id"), "comment_like", int(row.get("count") or 0))

    for row in (
        PostPollVote.objects.filter(post__in=base_posts)
        .values("user_id")
        .annotate(count=Count("id"))
    ):
        _add_points(row.get("user_id"), "poll_vote", int(row.get("count") or 0))

    for row in (
        PostFavorite.objects.filter(post__in=base_posts)
        .values("user_id")
        .annotate(count=Count("id"))
    ):
        _add_points(row.get("user_id"), "favorite", int(row.get("count") or 0))

    for row in (
        PostRead.objects.filter(post__in=base_posts)
        .values("user_id")
        .annotate(count=Count("id"))
    ):
        _add_points(row.get("user_id"), "read", int(row.get("count") or 0))

    for row in (
        community_service.AuthorAdmin.objects.filter(verified_at__isnull=False, author__posts__in=base_posts)
        .values("user_id")
        .annotate(count=Count("author__posts", distinct=True))
    ):
        _add_points(row.get("user_id"), "post", int(row.get("count") or 0))

    if not points_by_user:
        return {
            "participants_count": 0,
            "top_members": [],
            "points": dict(community_service._COMUN_ACTIVITY_POINTS),
        }

    user_ids_sorted = sorted(points_by_user.keys(), key=lambda uid: (-points_by_user[uid], uid))
    top_user_ids = user_ids_sorted[: max(int(top_limit or 0), 1)]

    users = list(
        User.objects.filter(id__in=top_user_ids)
        .select_related("telegram_account", "vk_account")
        .order_by("id")
    )
    users_by_id = {user.id: user for user in users}

    fallback_author_avatars: dict[int, str | None] = {}
    for link in (
        community_service.AuthorAdmin.objects.select_related("author")
        .filter(user_id__in=top_user_ids, verified_at__isnull=False)
        .order_by("user_id", "id")
    ):
        if link.user_id in fallback_author_avatars:
            continue
        fallback_author_avatars[link.user_id] = community_service._author_avatar_url(request, link.author)

    top_members = []
    rank = 0
    last_points = None
    for index, user_id in enumerate(top_user_ids, start=1):
        user = users_by_id.get(user_id)
        if not user:
            continue
        points = int(points_by_user.get(user_id) or 0)
        if points <= 0:
            continue
        if last_points != points:
            rank = index
            last_points = points
        top_members.append(
            {
                "user_id": user.id,
                "username": user.username,
                "avatar_url": community_service._site_user_avatar_url(
                    request, user, fallback_author_avatars=fallback_author_avatars
                ),
                "points": points,
                "rank": rank,
                "stats": stats_by_user.get(user_id, {}),
            }
        )

    return {
        "participants_count": len(points_by_user),
        "top_members": top_members,
        "points": dict(community_service._COMUN_ACTIVITY_POINTS),
    }


def _serialize_comun(
    request: HttpRequest,
    comun: Comun,
    *,
    current_user: User | None = None,
    include_manage_fields: bool = False,
    include_options: bool = False,
    include_activity: bool = False,
) -> dict:
    categories = community_service._comun_categories_list(comun)
    roadmap_category_ids = set(
        community_service._parse_int_list(getattr(comun, "roadmap_category_ids", []))
    )
    roadmap_categories = [
        category for category in categories if int(category.id) in roadmap_category_ids
    ]
    moderators = list(comun.moderators.select_related("site_profile").order_by("username"))
    excluded_authors = list(comun.excluded_authors.filter(is_blocked=False).order_by("username"))
    telegram_source_author = getattr(comun, "telegram_source_author", None)
    tags = list(comun.tags.filter(is_active=True).order_by("name"))
    blocked_tags = list(comun.blocked_tags.filter(is_active=True).order_by("name"))
    glossary_terms = list(community_service._active_comun_glossary_queryset(comun).order_by("sort_order", "term"))
    welcome_post_payload = None
    if comun.welcome_post_id:
        welcome_post = (
            Post.objects.select_related("author")
            .prefetch_related("tags")
            .filter(id=comun.welcome_post_id, is_blocked=False, author__is_blocked=False)
            .first()
        )
        if welcome_post:
            welcome_post_payload = editor_service._serialize_post_for_user(request, welcome_post, current_user)

    payload = {
        "id": comun.id,
        "name": comun.name,
        "slug": comun.slug,
        "website_url": comun.website_url,
        "logo_url": community_service._comun_logo_url(request, comun),
        "product_description": comun.product_description,
        "rules_text": comun.rules_text,
        "target_audience": comun.target_audience,
        "glossary_enabled": bool(getattr(comun, "glossary_enabled", False)),
        "roadmap_enabled": bool(getattr(comun, "roadmap_enabled", False)),
        "roadmap_category_ids": [category.id for category in roadmap_categories],
        "roadmap_categories": [
            _serialize_comun_category(category, comun) for category in roadmap_categories
        ],
        "glossary_terms": [_serialize_comun_glossary_term(term) for term in glossary_terms],
        "glossary_terms_count": len(glossary_terms),
        "minimum_author_rating_to_post": community_service._comun_minimum_author_rating_value(comun),
        "only_moderators_can_post": bool(getattr(comun, "only_moderators_can_post", False)),
        "forbid_external_links": bool(getattr(comun, "forbid_external_links", False)),
        "rating": _serialize_comun_rating(comun, current_user=current_user),
        "hide_from_home": bool(comun.hide_from_home),
        "is_active": comun.is_active,
        "sort_order": comun.sort_order,
        "allowed_template_types": community_service._allowed_templates_for_comun(comun),
        "template_type_options": editor_service._serialize_post_template_type_options(),
        "template_editor_blocks_by_template": editor_service._template_editor_blocks_by_template(),
        "creator": {
            "id": comun.creator_id,
            "username": comun.creator.username if getattr(comun, "creator", None) else None,
            "display_name": (
                (
                    getattr(
                        getattr(getattr(comun, "creator", None), "site_profile", None),
                        "display_name",
                        "",
                    )
                    or ""
                ).strip()
                or None
            ),
        },
        "moderators": [
            {
                "id": moderator.id,
                "username": moderator.username,
                "display_name": (
                    (getattr(getattr(moderator, "site_profile", None), "display_name", "") or "").strip()
                    or None
                ),
            }
            for moderator in moderators
        ],
        "moderators_count": len(moderators),
        "excluded_authors_count": len(excluded_authors),
        "categories": [_serialize_comun_category(category, comun) for category in categories],
        "categories_count": len(categories),
        "telegram_source_author": _serialize_author_source_summary(request, telegram_source_author),
        "telegram_channel_username": (
            community_service._normalize_telegram_channel_username(
                comun.telegram_channel_username or getattr(telegram_source_author, "username", "")
            )
            or None
        ),
        "tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or community_service._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in tags
        ],
        "blocked_tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or community_service._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in blocked_tags
        ],
        "excluded_tags": [
            {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or community_service._lemmatize_tag(tag.name) or tag.name,
            }
            for tag in blocked_tags
        ],
        "excluded_authors": [
            {
                "id": author.id,
                "username": author.username,
                "title": author.title,
                "avatar_url": community_service._author_avatar_url(request, author),
            }
            for author in excluded_authors
        ],
        "welcome_post_id": comun.welcome_post_id,
        "welcome_post": welcome_post_payload,
        "can_moderate": community_service._comun_is_moderator(current_user, comun),
        "can_manage_moderators": community_service._comun_can_manage_moderators(current_user, comun),
        "can_post": community_service._comun_post_access_state(current_user, comun)[0],
    }
    if include_activity:
        payload["activity"] = _serialize_comun_activity(request, comun)
    if include_manage_fields:
        payload["category_ids"] = [category.id for category in categories]
        payload["roadmap_category_ids"] = [category.id for category in roadmap_categories]
        payload["moderator_ids"] = [moderator.id for moderator in moderators]
        payload["tag_ids"] = [tag.id for tag in tags]
        payload["excluded_author_ids"] = [author.id for author in excluded_authors]
        payload["blocked_tag_ids"] = [tag.id for tag in blocked_tags]
        payload["excluded_tag_ids"] = [tag.id for tag in blocked_tags]
        payload["telegram_source_author_id"] = comun.telegram_source_author_id
        payload["welcome_post_ref"] = str(comun.welcome_post_id or "")
    if include_options:
        verified_telegram_authors = community_service._current_user_verified_telegram_authors(current_user)
        payload["options"] = {
            "categories": [_serialize_comun_category(category, comun) for category in categories],
            "tags": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "lemma": tag.lemma or community_service._lemmatize_tag(tag.name) or tag.name,
                }
                for tag in Tag.objects.filter(is_active=True).order_by("name")
            ],
            "authors": [
                {
                    "id": author.id,
                    "username": author.username,
                    "title": author.title,
                    "avatar_url": community_service._author_avatar_url(request, author),
                }
                for author in Author.objects.filter(is_blocked=False).order_by("username")
            ],
            "telegram_channels": [
                _serialize_author_source_summary(request, author)
                for author in verified_telegram_authors
            ],
            "template_types": editor_service._serialize_post_template_type_options(),
            "template_editor_block_options_by_template": (
                editor_service._serialize_template_editor_block_options_by_template()
            ),
            "template_editor_blocks_by_template": editor_service._template_editor_blocks_by_template(),
        }
        if community_service._comun_can_manage_moderators(current_user, comun):
            payload["options"]["users"] = [
                {
                    "id": user.id,
                    "username": user.username,
                    "display_name": (
                        (getattr(getattr(user, "site_profile", None), "display_name", "") or "").strip()
                        or None
                    ),
                }
                for user in User.objects.filter(is_active=True)
                .select_related("site_profile")
                .order_by("username")
            ]
    return payload


__all__ = [
    "_serialize_author_source_summary",
    "_serialize_comun",
    "_serialize_comun_activity",
    "_serialize_comun_category",
    "_serialize_comun_glossary_term",
    "_serialize_comun_profile_card",
    "_serialize_comun_rating",
]
