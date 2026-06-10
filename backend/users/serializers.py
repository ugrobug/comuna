from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from communities import service as community_service
from ratings.service import calculate_author_rating
from users.avatar_media import public_cached_avatar_url
from users.models import AuthorAdmin

User = get_user_model()


def _fv():
    from feeds import views as feeds_views

    return feeds_views


def _serialize_user(user: User) -> dict:
    site_profile = None
    try:
        site_profile = user.site_profile
    except Exception:
        site_profile = None

    author_links = (
        AuthorAdmin.objects.select_related("author")
        .filter(user=user, verified_at__isnull=False)
        .order_by("author__username")
    )
    authors = []
    avatar_url = None
    for link in author_links:
        author = link.author
        if not avatar_url:
            avatar_url = _fv()._author_avatar_url(None, author)
        linked_comun = community_service._author_telegram_source_comun(author)
        authors.append(
            {
                "id": author.id,
                "username": author.username,
                "title": author.title,
                "channel_url": author.invite_url or author.channel_url,
                "avatar_url": _fv()._author_avatar_url(None, author),
                "auto_publish": author.auto_publish,
                "publish_delay_days": author.publish_delay_days,
                "notify_comments": author.notify_comments,
                "invite_url": author.invite_url,
                "author_rating": round(float(calculate_author_rating(author)), 2),
                "linked_comun_slug": linked_comun.slug if linked_comun and linked_comun.is_active else None,
                "linked_comun_name": linked_comun.name if linked_comun and linked_comun.is_active else None,
            }
        )
    can_create_comun, create_comun_min_author_rating, max_author_rating = (
        community_service._comun_creation_access_state(user)
    )
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "email_verified": bool(
            getattr(site_profile, "email_verified_at", None) if site_profile else None
        ),
        "telegram_linked": hasattr(user, "telegram_account"),
        "telegram_username": (
            getattr(getattr(user, "telegram_account", None), "username", "") or None
            if hasattr(user, "telegram_account")
            else None
        ),
        "vk_linked": hasattr(user, "vk_account"),
        "vk_username": (
            getattr(getattr(user, "vk_account", None), "username", "") or None
            if hasattr(user, "vk_account")
            else None
        ),
        "display_name": (site_profile.display_name if site_profile else "") or None,
        "avatar_url": public_cached_avatar_url(site_profile.avatar_url if site_profile else "") or avatar_url,
        "is_staff": user.is_staff,
        "is_author": bool(authors),
        "authors": authors,
        "max_author_rating": max_author_rating,
        "can_create_comun": can_create_comun,
        "create_comun_min_author_rating": create_comun_min_author_rating,
    }


def _serialize_public_site_user_profile(
    request: HttpRequest,
    user: User,
    *,
    author_links: list[AuthorAdmin] | None = None,
    posts_count: int = 0,
    comuns_count: int = 0,
) -> dict:
    try:
        deleted_at = getattr(user.site_profile, "deleted_at", None)
    except Exception:
        deleted_at = None
    if not user.is_active or deleted_at:
        return {
            "id": user.id,
            "username": "deleted",
            "display_name": "Удаленный пользователь",
            "avatar_url": None,
            "posts_count": int(posts_count or 0),
            "comuns_count": int(comuns_count or 0),
            "authors_count": 0,
            "is_staff": False,
            "first_name": None,
            "last_name": None,
            "is_deleted": True,
        }

    author_links = author_links or []
    fallback_author_avatars: dict[int, str | None] = {}
    for link in author_links:
        if link.user_id in fallback_author_avatars:
            continue
        fallback_author_avatars[link.user_id] = _fv()._author_avatar_url(request, link.author)
    return {
        "id": user.id,
        "username": user.username,
        "display_name": (
            (getattr(getattr(user, "site_profile", None), "display_name", "") or "").strip()
            or None
        ),
        "avatar_url": community_service._site_user_avatar_url(
            request, user, fallback_author_avatars=fallback_author_avatars
        ),
        "posts_count": int(posts_count or 0),
        "comuns_count": int(comuns_count or 0),
        "authors_count": len(author_links),
        "is_staff": bool(user.is_staff),
        "first_name": (getattr(user, "first_name", "") or "").strip() or None,
        "last_name": (getattr(user, "last_name", "") or "").strip() or None,
    }


def _serialize_public_site_user_author_card(request: HttpRequest, link: AuthorAdmin) -> dict:
    author = link.author
    return {
        "id": author.id,
        "username": author.username,
        "title": (author.title or "").strip() or None,
        "channel_url": (author.invite_url or author.channel_url or "").strip() or None,
        "avatar_url": _fv()._author_avatar_url(request, author),
        "description": (author.description or "").strip() or None,
    }


__all__ = [
    "_serialize_public_site_user_author_card",
    "_serialize_public_site_user_profile",
    "_serialize_user",
]
