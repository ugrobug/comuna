from __future__ import annotations

import json
import hmac
import hashlib
import math
import os
import re
import secrets
import base64
import time
import inspect
try:
    import pymorphy2
except ImportError:  # optional dependency for lemmatization
    pymorphy2 = None
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils.text import get_valid_filename
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime as dt_datetime, timedelta, timezone as dt_timezone
from math import ceil
from html import escape, unescape
from xml.sax.saxutils import escape as xml_escape
from django.db import transaction
from django.db.models import Avg, Count, Exists, F, IntegerField, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Cast, Coalesce

from django.conf import settings
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from PIL import Image, UnidentifiedImageError
from django.contrib.auth import get_user_model

from communities import views as community_views
from communities import service as community_service
from communities import serializers as community_serializers
from communities.models import (
    Comun,
    ComunCategory,
    ComunGlossaryTerm,
    ComunPostCategoryAssignment,
    ComunVote,
)
from editor.models import (
    POST_TEMPLATE_TYPE_BASIC as MODEL_POST_TEMPLATE_TYPE_BASIC,
    POST_TEMPLATE_TYPE_CHOICES as MODEL_POST_TEMPLATE_TYPE_CHOICES,
    POST_TEMPLATE_TYPE_MOVIE_REVIEW as MODEL_POST_TEMPLATE_TYPE_MOVIE_REVIEW,
    POST_TEMPLATE_TYPE_MUSIC_RELEASE as MODEL_POST_TEMPLATE_TYPE_MUSIC_RELEASE,
    POST_TEMPLATE_TYPE_POST_VOTE_POLL as MODEL_POST_TEMPLATE_TYPE_POST_VOTE_POLL,
    PostPollVote,
    PostRatingVote,
    PostTemplateConfig,
    default_enabled_template_editor_blocks,
    normalize_allowed_post_templates,
    normalize_allowed_post_templates_override,
    normalize_template_editor_blocks_for_template,
    template_editor_block_choices_for_template,
)
from editor.serializers import (
    _content_with_live_poll,
    _serialize_enabled_template_editor_blocks,
    _serialize_post_for_user,
    _serialize_post_rating,
    _serialize_post_rating_block,
    _serialize_post_ratings,
    _serialize_post_template,
)
from editor.service import (
    _allowed_template_overrides_for_comun_category,
    _allowed_templates_for_comun,
    _allowed_templates_for_comun_category,
    _build_post_vote_poll_raw_poll,
    _decode_editor_payload,
    _extract_editor_payload_title,
    _extract_inline_post_rating_blocks,
    _get_or_create_personal_author,
    _get_personal_author_for_user,
    _is_post_draft,
    _normalize_editor_block_identifier,
    _normalize_movie_review_template_data,
    _normalize_music_release_template_data,
    _normalize_post_template_payload,
    _normalize_post_vote_poll_template_data,
    _normalize_template_bool,
    _normalize_template_datetime,
    _normalize_template_http_url,
    _normalize_template_text,
    _post_draft_share_token,
    _requested_template_type,
    _resolve_manual_post_author,
    _resolve_site_post_author_context,
    _serialize_post_template_type_options,
    _serialize_template_editor_block_options_by_template,
    _set_post_draft_state,
    _sync_template_derived_raw_data,
    _template_editor_blocks_by_template,
    _template_not_allowed_error,
    _template_type_from_payload,
    _user_can_manage_site_post,
)
from ratings.models import AuthorRatingEvent
from .models import (
    Author,
    Post,
    PostComment,
    PostCommentLike,
    PostFavorite,
    PostLike,
    PostRead,
    StaticPageContent,
    Tag,
)
from notifications.service import create_user_notification
from ratings.service import (
    apply_author_rating_delta as _apply_author_rating_delta,
    author_rating_value as _author_rating_value,
    format_rating_value as _format_rating_value,
    user_max_author_rating as _user_max_author_rating,
)
from telegram_integration.media import download_telegram_file_by_path
from users.models import (
    AuthorAdmin,
    AuthorVerificationCode,
    SiteUserProfile,
)

User = get_user_model()

_FAKE_VIEWS_RAMP_SECONDS = 48 * 60 * 60
_COMUN_CREATION_MIN_AUTHOR_RATING = 0.0
_COMUN_ACTIVITY_POINTS = {
    "post": 10,
    "comment": 5,
    "post_vote": 2,
    "comment_like": 1,
    "poll_vote": 2,
    "favorite": 2,
    "read": 1,
}
_COMMENT_PERSONAS = (
    {"key": "persona_1", "username": "anna_m", "display_name": "Анна М.", "bio": "Часто обсуждает новые релизы и сериалы."},
    {"key": "persona_2", "username": "igor_p", "display_name": "Игорь П.", "bio": "Любит спорить о киноиндустрии и трендах."},
    {"key": "persona_3", "username": "olga_v", "display_name": "Ольга В.", "bio": "Следит за фестивалями, кастом и премьерами."},
    {"key": "persona_4", "username": "sergey_k", "display_name": "Сергей К.", "bio": "Собирает новости о продакшене и сериалах."},
    {"key": "persona_5", "username": "maria_t", "display_name": "Мария Т.", "bio": "Комментирует актерские работы и сценарии."},
    {"key": "persona_6", "username": "nikita_l", "display_name": "Никита Л.", "bio": "Следит за анонсами, кассой и стримингами."},
    {"key": "persona_7", "username": "elena_s", "display_name": "Елена С.", "bio": "Пишет о любимых франшизах и премьерах."},
    {"key": "persona_8", "username": "denis_r", "display_name": "Денис Р.", "bio": "Смотрит новинки и обсуждает их без спойлеров."},
    {"key": "persona_9", "username": "kate_n", "display_name": "Катя Н.", "bio": "Любит разговоры про жанры, актеров и сериалы."},
    {"key": "persona_10", "username": "alex_b", "display_name": "Алекс Б.", "bio": "Следит за индустрией и громкими релизами."},
)
_COMMENT_PERSONAS_BY_KEY = {item["key"]: item for item in _COMMENT_PERSONAS}
_COMMENT_PERSONAS_BY_USERNAME = {
    str(item["username"]).strip().lower(): item for item in _COMMENT_PERSONAS
}
_POST_TEMPLATE_TYPE_BASIC = MODEL_POST_TEMPLATE_TYPE_BASIC
_POST_TEMPLATE_TYPE_MOVIE_REVIEW = MODEL_POST_TEMPLATE_TYPE_MOVIE_REVIEW
_POST_TEMPLATE_TYPE_POST_VOTE_POLL = MODEL_POST_TEMPLATE_TYPE_POST_VOTE_POLL
_POST_TEMPLATE_TYPE_MUSIC_RELEASE = MODEL_POST_TEMPLATE_TYPE_MUSIC_RELEASE
_POST_TEMPLATE_TYPE_OPTIONS = tuple(
    (str(value), str(label)) for value, label in MODEL_POST_TEMPLATE_TYPE_CHOICES
)
_POST_TEMPLATE_TYPES = {value for value, _label in _POST_TEMPLATE_TYPE_OPTIONS}
_EXTERNAL_URL_RE = re.compile(r"""https?://[^\s<>"')\]]+|www\.[^\s<>"')\]]+""", re.IGNORECASE)
_INTERNAL_COMUNA_HOSTS = {"comuna.ru", "www.comuna.ru", "localhost", "127.0.0.1"}
_COMUN_EXTERNAL_LINKS_FORBIDDEN_ERROR = (
    "В этом сообществе запрещены внешние ссылки. Удалите ссылки из текста и шаблона публикации."
)
_EDITABLE_STATIC_PAGE_TITLES = {
    "about": "О проекте",
    "advertisement": "Реклама",
    "authors": "Авторам",
    "privacy": "Политика обработки персональных данных",
    "rules": "Правила",
}

def _site_user_display_name(user: User) -> str:
    display_name = (
        (getattr(getattr(user, "site_profile", None), "display_name", "") or "").strip()
    )
    if display_name:
        return display_name
    full_name = " ".join(
        part for part in [(user.first_name or "").strip(), (user.last_name or "").strip()] if part
    ).strip()
    if full_name:
        return full_name
    return (user.username or "").strip()


def _site_user_for_personal_author(
    request: HttpRequest | None,
    author: Author,
) -> User | None:
    if not author or author.channel_url or author.channel_id is not None:
        return None

    cache: dict[int, User | None] | None = None
    author_id = int(getattr(author, "id", 0) or 0)
    if request is not None:
        cache = getattr(request, "_personal_author_site_user_cache", None)
        if cache is None:
            cache = {}
            setattr(request, "_personal_author_site_user_cache", cache)
        if author_id in cache:
            return cache[author_id]

    site_user = None
    site_user_id = _site_user_id_for_author(author)
    if site_user_id:
        site_user = (
            User.objects.filter(id=site_user_id)
            .select_related("site_profile", "telegram_account", "vk_account")
            .first()
        )

    if cache is not None:
        cache[author_id] = site_user
    return site_user


def _author_display_fields(
    request: HttpRequest | None,
    author: Author,
    post_channel_url: str | None = None,
) -> tuple[str | None, str]:
    channel_url = author.invite_url or author.channel_url
    title = author.title or author.username
    if not channel_url:
        channel_url = post_channel_url
    site_user = _site_user_for_personal_author(request, author)
    if site_user:
        site_user_name = _site_user_display_name(site_user)
        if site_user_name:
            title = site_user_name
    return channel_url, title


def _author_avatar_for_display(
    request: HttpRequest | None,
    author: Author,
) -> str | None:
    site_user = _site_user_for_personal_author(request, author)
    if site_user:
        site_avatar = _site_user_avatar_url(request, site_user)
        if site_avatar:
            return site_avatar
    return _author_avatar_url(request, author)


def _author_admin_fields_for_user(
    user: User | None,
    author: Author,
) -> dict[str, bool]:
    if not user or not user.is_staff:
        return {}
    return {"notify_comments_enabled": bool(author.notify_comments)}

def _site_user_id_for_author(author: Author | None) -> int | None:
    if not author:
        return None
    if author.channel_url or author.channel_id is not None:
        return None

    linked_user_id = (
        AuthorAdmin.objects.filter(author=author, verified_at__isnull=False)
        .order_by("created_at", "id")
        .values_list("user_id", flat=True)
        .first()
    )
    if linked_user_id:
        return int(linked_user_id)

    matching_user = User.objects.filter(
        username__iexact=(author.username or "").strip()
    ).only("id").first()
    return int(matching_user.id) if matching_user else None


def _serialize_static_page_content(page: StaticPageContent | None, slug: str) -> dict:
    normalized_slug = str(slug or "").strip().lower()
    fallback_title = _EDITABLE_STATIC_PAGE_TITLES.get(normalized_slug, normalized_slug)
    if not page:
        return {
            "slug": normalized_slug,
            "title": fallback_title,
            "content": "",
            "exists": False,
            "updated_at": None,
            "updated_by": None,
        }
    updated_by = page.updated_by
    return {
        "slug": page.slug,
        "title": page.title or fallback_title,
        "content": page.content or "",
        "exists": True,
        "updated_at": page.updated_at.isoformat() if page.updated_at else None,
        "updated_by": (
            {
                "id": updated_by.id,
                "username": updated_by.username,
            }
            if updated_by
            else None
        ),
    }


def _generate_manual_message_id(author: Author) -> int:
    for _ in range(10):
        candidate = -secrets.randbelow(2_000_000_000) - 1
        if not Post.objects.filter(author=author, message_id=candidate).exists():
            return candidate
    raise ValueError("failed to generate message id")


def _maybe_notify_new_author(author: Author, post: Post) -> None:
    if author.first_post_notified:
        return
    if post.is_pending or post.is_blocked:
        return
    already_published = (
        Post.objects.filter(author=author, is_pending=False, is_blocked=False)
        .exclude(id=post.id)
        .exists()
    )
    if already_published:
        author.first_post_notified = True
        author.save(update_fields=["first_post_notified", "updated_at"])
        return

    admin_chat = settings.TELEGRAM_ADMIN_CHAT_ID
    if not admin_chat:
        return

    site_base = settings.SITE_BASE_URL.rstrip("/")
    author_url = f"{site_base}/{author.username}"
    post_url = f"{site_base}/b/post/{post.id}"
    telegram_bot._send_bot_message(
        int(admin_chat),
        "Новый автор опубликовал первый пост.\n"
        f"Канал: @{author.username}\n"
        f"Автор: {author_url}\n"
        f"Пост: {post_url}",
    )
    author.first_post_notified = True
    author.save(update_fields=["first_post_notified", "updated_at"])


def _comment_preview(text: str, max_length: int = 220) -> str:
    preview = re.sub(r"\s+", " ", text or "").strip()
    if len(preview) <= max_length:
        return preview
    return preview[: max_length - 1].rstrip() + "…"


def _comment_display_username(comment: PostComment) -> str:
    masked = (getattr(comment, "persona_username", "") or "").strip()
    if masked:
        return masked
    try:
        display_name = (getattr(comment.user.site_profile, "display_name", "") or "").strip()
        if display_name:
            return display_name
    except Exception:
        pass
    username = (getattr(comment.user, "username", "") or "").strip()
    return username or "user"


def _comment_persona_by_username(username: str | None) -> dict | None:
    key = (username or "").strip().lower()
    if not key:
        return None
    return _COMMENT_PERSONAS_BY_USERNAME.get(key)


def _split_persona_display_name(display_name: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", str(display_name or "").strip())
    if not normalized:
        return "", ""
    parts = normalized.split(" ", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _ensure_comment_persona_user(persona: dict | None) -> User | None:
    if not persona:
        return None

    username = str(persona.get("username") or "").strip()
    if not username:
        return None

    display_name = str(persona.get("display_name") or username).strip() or username
    first_name, last_name = _split_persona_display_name(display_name)
    email = f"{username}.mask@comuna.local"

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "is_active": True,
        },
    )
    updates: list[str] = []
    if created:
        user.set_unusable_password()
        updates.append("password")
    if email and (user.email or "").strip() != email:
        user.email = email
        updates.append("email")
    if first_name and (user.first_name or "").strip() != first_name:
        user.first_name = first_name
        updates.append("first_name")
    if (user.last_name or "").strip() != last_name:
        user.last_name = last_name
        updates.append("last_name")
    if not user.is_active:
        user.is_active = True
        updates.append("is_active")
    if updates:
        user.save(update_fields=updates)

    profile, _ = SiteUserProfile.objects.get_or_create(user=user)
    profile_updates: list[str] = []
    if (profile.display_name or "").strip() != display_name:
        profile.display_name = display_name
        profile_updates.append("display_name")
    if profile_updates:
        profile.save(update_fields=profile_updates + ["updated_at"])

    return user


def _serialize_comment_user(comment: PostComment) -> dict:
    persona = _comment_persona_by_username(getattr(comment, "persona_username", ""))
    if persona:
        persona_user = _ensure_comment_persona_user(persona)
        persona_user_id = getattr(persona_user, "id", None)
        return {
            "id": persona_user_id,
            "username": (getattr(persona_user, "username", "") or persona["username"]).strip(),
            "display_name": (
                getattr(getattr(persona_user, "site_profile", None), "display_name", "") or persona.get("display_name") or persona["username"]
            ),
            "avatar_url": _site_user_avatar_url(None, persona_user) if persona_user else None,
            "profile_url": f"/id{persona_user_id}" if persona_user_id else None,
            "is_mask": True,
        }

    display_name = ""
    try:
        display_name = (getattr(comment.user.site_profile, "display_name", "") or "").strip()
    except Exception:
        display_name = ""

    return {
        "id": comment.user_id,
        "username": (getattr(comment.user, "username", "") or "").strip() or "user",
        "display_name": display_name or None,
        "avatar_url": _site_user_avatar_url(None, comment.user),
        "profile_url": f"/id{comment.user_id}" if comment.user_id else None,
        "is_mask": False,
    }


def _serialize_site_comment(comment: PostComment, *, liked_by_me: bool = False, likes_count: int = 0, can_edit: bool = False) -> dict:
    return {
        "id": comment.id,
        "body": "" if comment.is_deleted else comment.body,
        "created_at": comment.created_at.isoformat(),
        "updated_at": comment.updated_at.isoformat(),
        "parent_id": comment.parent_id,
        "is_deleted": comment.is_deleted,
        "likes_count": likes_count,
        "liked_by_me": liked_by_me,
        "can_edit": can_edit,
        "user": _serialize_comment_user(comment),
    }


def _comment_personas_for_user(user: User | None) -> list[dict]:
    if not user or not user.is_staff:
        return []
    personas: list[dict] = []
    for item in _COMMENT_PERSONAS:
        persona_user = _ensure_comment_persona_user(item)
        personas.append(
            {
                "key": item["key"],
                "username": (getattr(persona_user, "username", "") or item["username"]).strip(),
            }
        )
    return personas


def _can_edit_site_comment(user: User | None, comment: PostComment) -> bool:
    if not user or comment.is_deleted:
        return False
    if comment.user_id == user.id:
        return True
    return bool(user.is_staff and getattr(comment, "persona_key", ""))


def _maybe_notify_author_comment(post: Post, comment: PostComment) -> None:
    author = post.author
    if not author.notify_comments or not author.admin_chat_id:
        return

    # Do not notify if the comment was left by this channel's verified owner.
    if AuthorAdmin.objects.filter(
        author=author, user_id=comment.user_id, verified_at__isnull=False
    ).exists():
        return

    site_base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    post_link = f"{site_base}/b/post/{post.id}#comments" if site_base else ""
    commenter_name = _comment_display_username(comment)
    commenter = f"@{commenter_name}" if commenter_name else "Пользователь"
    text = (
        "Новый комментарий к вашему посту на Comuna.\n"
        f"Пост: {_post_display_title(post)}\n"
        f"Пользователь: {commenter}\n"
        f"Комментарий: {_comment_preview(comment.body)}"
    )
    if post_link:
        text += f"\nСсылка: {post_link}"

    telegram_bot._send_bot_message(int(author.admin_chat_id), text)


def _site_comment_link(post: Post, comment: PostComment | None = None) -> str:
    base_path = _post_public_path(post)
    if comment and getattr(comment, "id", None):
        return f"{base_path}#site-comment-{comment.id}"
    return f"{base_path}#comments"


def _author_owner_users_for_notifications(author: Author) -> list[User]:
    user_ids = set(
        AuthorAdmin.objects.filter(author=author, verified_at__isnull=False).values_list(
            "user_id", flat=True
        )
    )
    if not author.channel_url and author.channel_id is None:
        personal_user = User.objects.filter(
            username__iexact=(author.username or "").strip()
        ).first()
        if personal_user:
            user_ids.add(personal_user.id)
    if not user_ids:
        return []
    return list(User.objects.filter(id__in=user_ids))


def _maybe_notify_post_comment(post: Post, comment: PostComment) -> None:
    recipients = _author_owner_users_for_notifications(post.author)
    if not recipients:
        return

    commenter_name = _comment_display_username(comment) or "Пользователь"
    post_title = _post_display_title(post)
    comment_preview = _comment_preview(comment.body)
    link_url = _site_comment_link(post, comment)
    payload = {
        "post_id": post.id,
        "comment_id": comment.id,
        "comment_parent_id": comment.parent_id,
        "commenter_user_id": comment.user_id,
        "commenter_name": commenter_name,
        "post_author_id": post.author_id,
    }
    message = (
        f"Пользователь {commenter_name} оставил комментарий к вашему посту "
        f"«{post_title}»: {comment_preview}"
    )

    for recipient in recipients:
        if recipient.id == comment.user_id:
            continue
        create_user_notification(
            user=recipient,
            event_key="post_comment",
            title="Новый комментарий к вашему посту",
            message=message,
            link_url=link_url,
            payload=payload,
        )


def _maybe_notify_comment_reply(
    post: Post,
    parent: PostComment | None,
    comment: PostComment,
) -> None:
    if not parent:
        return
    if parent.is_deleted:
        return
    if getattr(parent, "persona_key", ""):
        return
    if not parent.user_id or parent.user_id == comment.user_id:
        return

    replier_name = _comment_display_username(comment) or "Пользователь"
    post_title = _post_display_title(post)
    comment_preview = _comment_preview(comment.body)
    link_url = _site_comment_link(post, comment)
    payload = {
        "post_id": post.id,
        "comment_id": comment.id,
        "parent_comment_id": parent.id,
        "replier_user_id": comment.user_id,
        "replier_name": replier_name,
    }
    message = (
        f"Пользователь {replier_name} ответил на ваш комментарий "
        f"в посте «{post_title}»: {comment_preview}"
    )

    create_user_notification(
        user=parent.user,
        event_key="comment_reply",
        title="Ответ на ваш комментарий",
        message=message,
        link_url=link_url,
        payload=payload,
    )


def _is_voting_comun_category(category: ComunCategory | None) -> bool:
    if not category:
        return False
    slug = (category.slug or "").strip().lower()
    name = (category.name or "").strip().lower()
    tokens = (slug, name)
    voting_markers = (
        "vote",
        "voting",
        "poll",
        "голос",
        "голосован",
        "опрос",
    )
    return any(marker in value for value in tokens for marker in voting_markers if value)


def _maybe_notify_post_added_to_voting(
    *,
    post: Post,
    comun: Comun,
    category: ComunCategory | None,
    actor: User | None = None,
    previous_category: ComunCategory | None = None,
) -> None:
    if not _is_voting_comun_category(category):
        return
    if _is_voting_comun_category(previous_category):
        return

    recipients = _author_owner_users_for_notifications(post.author)
    if not recipients:
        return

    post_title = _post_display_title(post)
    comun_title = (comun.name or comun.slug or "").strip() or "коммуна"
    category_title = (category.name or "").strip() if category else "голосование"
    message = (
        f"Пост «{post_title}» добавлен в категорию «{category_title}» "
        f"в комуне «{comun_title}»."
    )
    link_url = f"/b/post/{post.id}"
    payload = {
        "post_id": post.id,
        "author_id": post.author_id,
        "comun_id": comun.id,
        "comun_slug": comun.slug,
        "category_id": category.id if category else None,
        "category_slug": category.slug if category else "",
        "actor_user_id": actor.id if actor else None,
    }

    for recipient in recipients:
        if actor and recipient.id == actor.id:
            continue
        create_user_notification(
            user=recipient,
            event_key="post_added_to_voting",
            title="Ваш пост добавили в голосование",
            message=message,
            link_url=link_url,
            payload=payload,
        )


def _media_url(request: HttpRequest | None, field) -> str | None:
    if not field:
        return None
    site_base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    if site_base:
        try:
            return f"{site_base}{field.url}"
        except Exception:
            pass
    if request is None:
        return None
    try:
        return request.build_absolute_uri(field.url)
    except Exception:
        return None


def _author_avatar_url(request: HttpRequest | None, author: Author) -> str | None:
    return _media_url(request, author.avatar_image) or author.avatar_url


def _stable_unit_float(*parts: object) -> float:
    key = ":".join(str(part) for part in parts).encode("utf-8", "ignore")
    digest = hashlib.sha256(key).digest()
    raw = int.from_bytes(digest[:8], "big")
    return raw / float((1 << 64) - 1)


def _post_fake_views_current(post: Post, now=None) -> int:
    target = max(int(getattr(post, "fake_views_target", 0) or 0), 0)
    if target <= 0:
        return 0

    created_at = getattr(post, "created_at", None)
    if not created_at:
        return target
    if now is None:
        now = timezone.now()
    if timezone.is_naive(created_at):
        created_at = timezone.make_aware(created_at, dt_timezone.utc)

    age_seconds = max((now - created_at).total_seconds(), 0.0)
    if age_seconds <= 0:
        return 0
    if age_seconds >= _FAKE_VIEWS_RAMP_SECONDS:
        return target

    t = min(max(age_seconds / _FAKE_VIEWS_RAMP_SECONDS, 0.0), 1.0)
    seed_base = getattr(post, "id", 0) or getattr(post, "message_id", 0) or 0
    u1 = _stable_unit_float("v1", seed_base, target)
    u2 = _stable_unit_float("v2", seed_base, target)
    u3 = _stable_unit_float("v3", seed_base, target)
    u4 = _stable_unit_float("v4", seed_base, target)
    u5 = _stable_unit_float("v5", seed_base, target)
    u6 = _stable_unit_float("v6", seed_base, target)

    fast = 1.0 - math.pow(1.0 - t, 1.35 + u1 * 2.25)
    smooth = t * t * (3.0 - 2.0 * t)
    late = math.pow(t, 1.4 + u2 * 2.2)
    slower_tail = 1.0 - math.pow(1.0 - t, 0.8 + u3 * 0.7)

    w_fast = 0.35 + u4 * 0.25
    w_smooth = 0.15 + u5 * 0.20
    w_late = 0.10 + u6 * 0.20
    w_tail = 1.0 - (w_fast + w_smooth + w_late)
    if w_tail < 0.05:
        w_tail = 0.05
        total = w_fast + w_smooth + w_late + w_tail
        w_fast /= total
        w_smooth /= total
        w_late /= total
        w_tail /= total

    progress = w_fast * fast + w_smooth * smooth + w_late * late + w_tail * slower_tail
    progress = min(max(progress, 0.0), 1.0)
    fake_views = int(target * progress)
    return min(max(fake_views, 0), target)


def _post_total_views(post: Post, now=None) -> int:
    real_views = max(int(getattr(post, "real_views_count", 0) or 0), 0)
    return real_views + _post_fake_views_current(post, now=now)


def _author_posts_rating_filter(now) -> Q:
    return (
        Q(posts__is_blocked=False, posts__is_pending=False)
        & (Q(posts__publish_at__isnull=True) | Q(posts__publish_at__lte=now))
    )


def _format_lastmod(value) -> str | None:
    if not value:
        return None
    if timezone.is_naive(value):
        value = timezone.make_aware(value, dt_timezone.utc)
    return value.astimezone(dt_timezone.utc).date().isoformat()


def _publish_ready_filter(now) -> Q:
    return Q(publish_at__isnull=True) | Q(publish_at__lte=now)


def _sitemap_base_url(request: HttpRequest) -> str:
    base = (getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if base:
        return base
    return request.build_absolute_uri("/").rstrip("/")


def _build_title(text: str) -> str:
    if not text:
        return ""
    first_line = text.strip().splitlines()[0].strip()
    positions = []
    for separator in (".", "!", "?"):
        idx = first_line.find(separator)
        if idx > 0:
            positions.append((idx, separator))
    if positions:
        idx, separator = min(positions, key=lambda item: item[0])
        if separator == ".":
            return first_line[:idx].strip()
        return first_line[: idx + 1].strip()
    if len(first_line) <= 120:
        return first_line
    return first_line[:117].strip() + "..."


def _post_display_title(post: Post) -> str:
    direct_title = (post.title or "").strip()
    if direct_title:
        return direct_title

    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    poll = raw_data.get("poll") if isinstance(raw_data, dict) else None
    if isinstance(poll, dict):
        question = str(poll.get("question") or "").strip()
        if question:
            poll_title = _build_title(question)
            if poll_title:
                return poll_title

    content = post.content or ""
    editor_payload = _decode_editor_payload(content)
    if editor_payload:
        editor_payload_title = _extract_editor_payload_title(content)
        if editor_payload_title:
            return editor_payload_title
        return "Пост"

    content_text = _strip_html(content).strip()
    if content_text:
        content_title = _build_title(content_text)
        if content_title:
            return content_title

    return "Пост"


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return unescape(re.sub(r"<[^>]+>", "", text))


def _normalize_tag_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


_MORPH_ANALYZER = None


def _ensure_pymorphy2_compat():
    if pymorphy2 is None:
        return
    if not hasattr(inspect, "getargspec"):
        from collections import namedtuple
        ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")

        def getargspec(func):  # type: ignore
            spec = inspect.getfullargspec(func)
            return ArgSpec(spec.args, spec.varargs, spec.varkw, spec.defaults)
        inspect.getargspec = getargspec  # type: ignore[attr-defined]


def _get_morph_analyzer():
    global _MORPH_ANALYZER
    if pymorphy2 is None:
        return None
    if _MORPH_ANALYZER is None:
        _ensure_pymorphy2_compat()
        try:
            _MORPH_ANALYZER = pymorphy2.MorphAnalyzer()
        except Exception:
            _MORPH_ANALYZER = None
    return _MORPH_ANALYZER


def _lemmatize_tag(value: str) -> str:
    morph = _get_morph_analyzer()
    if not morph:
        return ""
    text = _normalize_tag_value(value).lower()
    if not text:
        return ""
    words = text.split()
    lemmas: list[str] = []
    for word in words:
        parts = [part for part in word.split("-") if part]
        if not parts:
            continue
        lemma_parts: list[str] = []
        for part in parts:
            parsed = morph.parse(part)
            if parsed:
                lemma_parts.append(parsed[0].normal_form)
            else:
                lemma_parts.append(part)
        lemmas.append("-".join(lemma_parts))
    return " ".join(lemmas).strip()


def _parse_tag_payload(raw) -> list[str]:
    if not raw:
        return []
    if isinstance(raw, str):
        parts = re.split(r"[,\n]", raw)
    elif isinstance(raw, (list, tuple)):
        parts = raw
    else:
        return []
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if part is None:
            continue
        value = _normalize_tag_value(str(part))
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(value)
    return normalized


def _http_json_request(
    url: str,
    *,
    method: str = "GET",
    payload: dict | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 6.0,
) -> dict | list | None:
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "ComunaBot/1.0 (+https://comuna.ru)",
    }
    if headers:
        request_headers.update(headers)

    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")

    request = urllib.request.Request(
        url,
        data=data,
        headers=request_headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return None

    if not body:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _http_json_get(
    url: str, *, headers: dict[str, str] | None = None, timeout: float = 6.0
) -> dict | list | None:
    return _http_json_request(url, method="GET", headers=headers, timeout=timeout)


def _http_json_post(
    url: str,
    payload: dict,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 6.0,
) -> dict | list | None:
    return _http_json_request(
        url, method="POST", payload=payload, headers=headers, timeout=timeout
    )


_TEMPLATE_POLL_SOURCE_POST_VOTE = "template_post_vote_poll"
_CONTENT_POLL_SOURCE_INLINE = "content_inline_poll"


def _extract_inline_poll_from_content(raw_content: str) -> dict | None:
    payload = _decode_editor_payload(raw_content)
    if not payload:
        return None

    for block in payload.get("blocks") or []:
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").strip().lower()
        if block_type != "poll":
            continue
        block_data = block.get("data")
        if not isinstance(block_data, dict):
            continue

        question = str(block_data.get("question") or "").strip()
        raw_options = block_data.get("options")
        if not question or not isinstance(raw_options, list):
            return None

        option_items: list[dict[str, object]] = []
        for raw_option in raw_options[:10]:
            text = str(raw_option or "").strip()
            if not text:
                continue
            option_items.append(
                {
                    "text": text,
                    "voter_count": 0,
                }
            )
        if len(option_items) < 2:
            return None

        uid = str(block_data.get("uid") or "").strip()
        raw_poll: dict[str, object] = {
            "question": question,
            "options": option_items,
            "is_anonymous": False,
            "allows_multiple_answers": bool(block_data.get("allows_multiple_answers")),
            "is_closed": False,
            "total_voter_count": 0,
        }
        if uid:
            raw_poll["id"] = uid
        return raw_poll

    return None


def _content_contains_inline_poll(raw_content: str) -> bool:
    return _extract_inline_poll_from_content(raw_content) is not None


def _sync_template_derived_raw_data(
    raw_data: dict, template_payload: dict | None, content: str | None = None
) -> None:
    template_type = str(template_payload.get("type") or "").strip().lower() if template_payload else ""
    if template_type == _POST_TEMPLATE_TYPE_POST_VOTE_POLL:
        poll_payload = _build_post_vote_poll_raw_poll(template_payload.get("data"))
        if poll_payload:
            raw_data["poll"] = poll_payload
            raw_data["poll_source"] = _TEMPLATE_POLL_SOURCE_POST_VOTE
            raw_data.pop("poll_html", None)
        return

    inline_poll_payload = _extract_inline_poll_from_content(content or "")
    if inline_poll_payload:
        raw_data["poll"] = inline_poll_payload
        raw_data["poll_source"] = _CONTENT_POLL_SOURCE_INLINE
        raw_data.pop("poll_html", None)
        return

    if str(raw_data.get("poll_source") or "") in {
        _TEMPLATE_POLL_SOURCE_POST_VOTE,
        _CONTENT_POLL_SOURCE_INLINE,
    }:
        raw_data.pop("poll", None)
        raw_data.pop("poll_source", None)
        raw_data.pop("poll_html", None)


def _count_tag_occurrences(text_lower: str, tag_lower: str) -> int:
    if not text_lower or not tag_lower:
        return 0
    if re.fullmatch(r"[\w\-]+", tag_lower):
        pattern = re.compile(rf"(?<!\w){re.escape(tag_lower)}(?!\w)")
        return len(pattern.findall(text_lower))
    return text_lower.count(tag_lower)


def _extract_hashtags(text: str) -> list[str]:
    if not text:
        return []
    tags: list[str] = []
    seen: set[str] = set()
    for match in re.findall(r"#([\w\-]+)", text, flags=re.UNICODE):
        value = _normalize_tag_value(match)
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(value)
    return tags


def _tag_key(tag: Tag) -> str:
    if tag.lemma:
        return tag.lemma.strip().lower()
    lemma = _lemmatize_tag(tag.name)
    return (lemma or tag.name).strip().lower()


def _serialize_tag(tag: Tag) -> dict:
    lemma = tag.lemma or _lemmatize_tag(tag.name) or tag.name
    return {"name": tag.name, "lemma": lemma}


def _serialize_tags(tags) -> list[dict]:
    return [_serialize_tag(tag) for tag in tags]


def _apply_post_tags(post: Post, explicit_tags: list[str] | None = None) -> None:
    explicit_tags = explicit_tags or []
    existing_tags = {}
    for tag in Tag.objects.all():
        key = _tag_key(tag)
        if key and key not in existing_tags:
            existing_tags[key] = tag
    selected_tags: list[Tag] = []
    seen_ids: set[int] = set()

    for tag_name in explicit_tags:
        normalized = _normalize_tag_value(tag_name)
        if not normalized:
            continue
        lemma = _lemmatize_tag(normalized) or normalized
        key = lemma.lower()
        tag = existing_tags.get(key)
        if not tag:
            tag = Tag.objects.create(name=normalized, lemma=lemma)
            existing_tags[key] = tag
        if tag.id not in seen_ids:
            selected_tags.append(tag)
            seen_ids.add(tag.id)
            if len(selected_tags) >= 5:
                break

    if len(selected_tags) < 5 and existing_tags:
        text = _strip_html(f"{post.title} {post.content}").lower()
        candidates: list[tuple[int, int, str, Tag]] = []
        for tag in existing_tags.values():
            if not tag.is_active or tag.id in seen_ids:
                continue
            count = _count_tag_occurrences(text, tag.name.lower())
            if count:
                candidates.append((count, len(tag.name), tag.name.lower(), tag))
        candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
        for _, __, ___, tag in candidates:
            selected_tags.append(tag)
            if len(selected_tags) >= 5:
                break

    if selected_tags:
        post.tags.set(selected_tags)
    else:
        post.tags.clear()


def _slugify_title(text: str) -> str:
    if not text:
        return ""
    translit_map = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "e",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "ts",
        "ч": "ch",
        "ш": "sh",
        "щ": "shch",
        "ы": "y",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        "ъ": "",
        "ь": "",
    }
    lowered = text.lower()
    translit = "".join(translit_map.get(ch, ch) for ch in lowered)
    slug = re.sub(r"[^a-z0-9]+", "-", translit).strip("-")
    return slug


def _extract_plain_text(message: dict) -> str:
    return (message.get("text") or message.get("caption") or "").strip()


def _is_telegram_service_message(message: dict) -> bool:
    service_keys = (
        "new_chat_members",
        "left_chat_member",
        "new_chat_title",
        "new_chat_photo",
        "delete_chat_photo",
        "group_chat_created",
        "supergroup_chat_created",
        "channel_chat_created",
        "message_auto_delete_timer_changed",
        "pinned_message",
        "video_chat_started",
        "video_chat_ended",
        "video_chat_participants_invited",
        "video_chat_scheduled",
        "forum_topic_created",
        "forum_topic_edited",
        "forum_topic_closed",
        "forum_topic_reopened",
        "general_forum_topic_hidden",
        "general_forum_topic_unhidden",
        "write_access_allowed",
        "giveaway",
        "giveaway_created",
        "giveaway_completed",
        "giveaway_winners",
        "chat_shared",
        "user_shared",
        "proximity_alert_triggered",
        "migrate_to_chat_id",
        "migrate_from_chat_id",
        "connected_website",
    )
    return any(key in message for key in service_keys)


def _extract_entities(message: dict) -> list[dict]:
    if message.get("text"):
        return message.get("entities") or []
    if message.get("caption"):
        return message.get("caption_entities") or []
    return []


def _utf16_offset_to_index(text: str, offset: int) -> int:
    if offset <= 0:
        return 0
    units = 0
    for index, ch in enumerate(text):
        codepoint = ord(ch)
        units += 2 if codepoint > 0xFFFF else 1
        if units > offset:
            return index + 1
        if units == offset:
            return index + 1
    return len(text)


def _entity_tags(entity: dict, segment: str) -> tuple[str, str] | None:
    entity_type = entity.get("type")
    if entity_type == "bold":
        return "<b>", "</b>"
    if entity_type == "italic":
        return "<i>", "</i>"
    if entity_type == "underline":
        return "<u>", "</u>"
    if entity_type == "strikethrough":
        return "<s>", "</s>"
    if entity_type == "spoiler":
        return '<span class="tg-spoiler">', "</span>"
    if entity_type == "code":
        return "<code>", "</code>"
    if entity_type == "pre":
        language = entity.get("language")
        class_attr = f' class="language-{escape(language)}"' if language else ""
        return f"<pre><code{class_attr}>", "</code></pre>"
    if entity_type == "blockquote":
        return "<blockquote>", "</blockquote>"
    if entity_type == "text_link":
        url = entity.get("url") or ""
        return f'<a href="{escape(url)}" target="_blank" rel="noopener">', "</a>"
    if entity_type == "url":
        href = segment.strip()
        return f'<a href="{escape(href)}" target="_blank" rel="noopener">', "</a>"
    if entity_type == "mention":
        username = segment.lstrip("@")
        return f'<a href="https://t.me/{escape(username)}" target="_blank" rel="noopener">', "</a>"
    return None


def _format_telegram_text(text: str, entities: list[dict]) -> str:
    if not text:
        return ""
    normalized = text.replace("\r\n", "\n")
    if not entities:
        return escape(normalized).replace("\n", "<br>")

    start_tags: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    end_tags: dict[int, list[tuple[int, str]]] = defaultdict(list)

    for entity in entities:
        offset = entity.get("offset")
        length = entity.get("length")
        if offset is None or length is None:
            continue
        start = _utf16_offset_to_index(normalized, offset)
        end = _utf16_offset_to_index(normalized, offset + length)
        if start >= end:
            continue
        segment = normalized[start:end]
        tags = _entity_tags(entity, segment)
        if not tags:
            continue
        open_tag, close_tag = tags
        start_tags[start].append((end, open_tag, close_tag))
        end_tags[end].append((start, close_tag))

    for index in start_tags:
        start_tags[index].sort(key=lambda item: item[0], reverse=True)
    for index in end_tags:
        end_tags[index].sort(key=lambda item: item[0], reverse=True)

    out: list[str] = []
    text_len = len(normalized)
    for index, ch in enumerate(normalized):
        if index in start_tags:
            for _, open_tag, _ in start_tags[index]:
                out.append(open_tag)
        out.append(escape(ch))
        if index + 1 in end_tags:
            for _, close_tag in end_tags[index + 1]:
                out.append(close_tag)

    return "".join(out).replace("\n", "<br>")


def _extract_photo_file_id(message: dict) -> str | None:
    photos = message.get("photo") or []
    if not photos:
        return None
    largest = max(
        photos,
        key=lambda item: (item.get("file_size", 0), item.get("width", 0) * item.get("height", 0)),
    )
    return largest.get("file_id")


def _extract_photo_url(message: dict, token: str) -> str | None:
    file_id = _extract_photo_file_id(message)
    if not file_id:
        return None
    file_info = _fetch_telegram_json("getFile", token, {"file_id": file_id})
    if not file_info or not file_info.get("ok") or not file_info.get("result"):
        return None
    file_path = file_info["result"].get("file_path")
    if not file_path:
        return None
    return download_telegram_file_by_path(file_path, token)


def _extract_audio_file_id(message: dict) -> str | None:
    for key in ("audio", "voice"):
        payload = message.get(key)
        if isinstance(payload, dict):
            file_id = payload.get("file_id")
            if file_id:
                return str(file_id)

    document = message.get("document") or {}
    if isinstance(document, dict):
        mime_type = (document.get("mime_type") or "").lower()
        if mime_type.startswith("audio/"):
            file_id = document.get("file_id")
            if file_id:
                return str(file_id)
    return None


def _extract_audio_url(message: dict, token: str | None) -> str:
    if not token:
        return ""

    existing_url = message.get("audio_url")
    if isinstance(existing_url, str) and existing_url.strip():
        return existing_url.strip()

    file_id = _extract_audio_file_id(message)
    if not file_id:
        return ""

    file_info = _fetch_telegram_json("getFile", token, {"file_id": file_id})
    if not file_info or not file_info.get("ok") or not file_info.get("result"):
        return ""

    file_path = file_info["result"].get("file_path")
    if not file_path:
        return ""

    audio_url = download_telegram_file_by_path(file_path, token) or ""
    if audio_url:
        message["audio_url"] = audio_url
    return audio_url


def _build_content_with_images(
    text_html: str,
    image_urls: list[str],
    embed_html: str = "",
    poll_html: str = "",
) -> str:
    parts: list[str] = []
    if image_urls:
        if len(image_urls) == 1:
            media_html = f'<img src="{image_urls[0]}" alt="" />'
        else:
            gallery_imgs = "".join(f'<img src="{url}" alt="" />' for url in image_urls)
            media_html = f'<div class="post-gallery">{gallery_imgs}</div>'
        parts.append(media_html)
    if embed_html:
        parts.append(embed_html)
    if poll_html:
        parts.append(poll_html)
    if text_html:
        parts.append(text_html)
    return "<br><br>".join([part for part in parts if part])


def _build_telegram_embed_html(username: str, message_id: int, height: int) -> str:
    src = f"https://t.me/{username}/{message_id}?embed=1&single=1"
    return (
        '<div class="post-embed">'
        f'<iframe class="telegram-embed" src="{src}" '
        f'width="100%" height="{height}" frameborder="0" '
        'allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" '
        'allowfullscreen loading="lazy" referrerpolicy="no-referrer"></iframe>'
        "</div>"
    )


def _build_telegram_audio_html(audio_url: str) -> str:
    return (
        '<div class="post-audio">'
        f'<audio controls preload="metadata" src="{escape(audio_url, quote=True)}"></audio>'
        "</div>"
    )


def _build_telegram_audio_fallback_html(username: str, message_id: int) -> str:
    # Telegram Bot API cannot download files larger than 20MB.
    # For such audios we fall back to Telegram widget so playback still works.
    return _build_telegram_embed_html(username, message_id, 200)


def _extract_telegram_embed(
    message: dict, username: str, token: str | None = None
) -> tuple[str, str]:
    message_id = message.get("message_id")
    if not message_id or not username:
        return "", ""

    document = message.get("document") or {}
    mime_type = (document.get("mime_type") or "").lower()
    has_video = any(
        message.get(key) for key in ("video", "video_note", "animation")
    ) or mime_type.startswith("video/")
    has_audio = any(message.get(key) for key in ("audio", "voice")) or mime_type.startswith(
        "audio/"
    )

    if has_video:
        return _build_telegram_embed_html(username, message_id, 420), "Видео"
    if has_audio:
        audio_url = _extract_audio_url(message, token)
        if audio_url:
            return _build_telegram_audio_html(audio_url), "Аудио"
        return _build_telegram_audio_fallback_html(username, message_id), "Аудио"
    return "", ""


def _replace_legacy_audio_embed(post: Post, content: str) -> str:
    if not content:
        return content
    if "telegram-embed" not in content and "post-audio-fallback" not in content:
        return content

    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    has_audio = any(raw_data.get(key) for key in ("audio", "voice"))
    if not has_audio:
        document = raw_data.get("document") or {}
        if not isinstance(document, dict):
            return content
        mime_type = (document.get("mime_type") or "").lower()
        has_audio = mime_type.startswith("audio/")
    if not has_audio:
        return content

    token = settings.TELEGRAM_BOT_TOKEN
    had_audio_url = bool(raw_data.get("audio_url"))
    audio_url = _extract_audio_url(raw_data, token)
    if audio_url and not had_audio_url:
        post.raw_data = raw_data
        post.save(update_fields=["raw_data"])

    if audio_url:
        replacement = _build_telegram_audio_html(audio_url)
    else:
        message_id = raw_data.get("message_id")
        username = getattr(post.author, "username", "") or ""
        if not username or not message_id:
            return content
        replacement = _build_telegram_audio_fallback_html(username, message_id)

    stored_embed_html = raw_data.get("embed_html")
    if (
        isinstance(stored_embed_html, str)
        and "telegram-embed" in stored_embed_html
        and stored_embed_html in content
    ):
        return content.replace(stored_embed_html, replacement, 1)

    if "post-audio-fallback" in content:
        return re.sub(
            r'<div class="post-audio-fallback">[\s\S]*?</div>',
            replacement,
            content,
            count=1,
        )

    return re.sub(
        r'<div class="post-embed">\s*<iframe class="telegram-embed"[\s\S]*?</iframe>\s*</div>',
        replacement,
        content,
        count=1,
    )


def _extract_poll_options(raw_poll: dict) -> list[dict]:
    raw_options = raw_poll.get("options") or []
    options: list[dict] = []
    if not isinstance(raw_options, list):
        return options
    for option in raw_options:
        if not isinstance(option, dict):
            continue
        text = str(option.get("text") or "").strip()
        if not text:
            continue
        try:
            count = int(option.get("voter_count", 0))
        except (TypeError, ValueError):
            count = 0
        post_id = _parse_post_reference_to_id(option.get("post_id") or option.get("post_ref"))
        post_path = str(option.get("post_path") or option.get("path") or "").strip()
        if post_path and not post_path.startswith("/"):
            post_path = ""
        option_payload: dict[str, object] = {
            "text": text,
            "voter_count": max(count, 0),
        }
        if post_id is not None:
            option_payload["post_id"] = post_id
        if post_path:
            option_payload["post_path"] = post_path
        options.append(option_payload)
    return options


def _parse_poll_close_at(value: object) -> dt_datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized_raw = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        parsed = dt_datetime.fromisoformat(normalized_raw)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        try:
            parsed = timezone.make_aware(parsed, dt_timezone.utc)
        except Exception:
            return None
    return parsed


def _poll_is_closed(raw_poll: dict) -> bool:
    if bool(raw_poll.get("is_closed")):
        return True
    close_at = _parse_poll_close_at(
        raw_poll.get("close_at") or raw_poll.get("ends_at") or raw_poll.get("expires_at")
    )
    if not close_at:
        return False
    return timezone.now() >= close_at


def _format_poll_close_at_label(value: str | None) -> str:
    if not value:
        return ""
    close_at = _parse_poll_close_at(value)
    if not close_at:
        return ""
    localized = timezone.localtime(close_at)
    return localized.strftime("%d.%m.%Y %H:%M")


def _normalize_poll_selection(value: object, options_count: int) -> list[int]:
    if not isinstance(value, list):
        return []
    normalized: list[int] = []
    for raw in value:
        try:
            index = int(raw)
        except (TypeError, ValueError):
            continue
        if index < 0 or index >= options_count:
            continue
        if index in normalized:
            continue
        normalized.append(index)
    return normalized


def _parse_poll_selection_payload(value: object, options_count: int) -> list[int] | None:
    if not isinstance(value, list):
        return None
    parsed: list[int] = []
    for raw in value:
        try:
            index = int(raw)
        except (TypeError, ValueError):
            return None
        if index < 0 or index >= options_count:
            return None
        if index in parsed:
            continue
        parsed.append(index)
    return parsed


def _build_poll_payload(
    raw_poll: dict,
    *,
    option_counts: list[int] | None = None,
    user_selection: list[int] | None = None,
    extra_voters: int = 0,
) -> dict | None:
    if not isinstance(raw_poll, dict):
        return None
    question = str(raw_poll.get("question") or "").strip()
    options = _extract_poll_options(raw_poll)
    if not question and not options:
        return None

    resolved_counts = (
        list(option_counts[: len(options)])
        if option_counts is not None
        else [int(option.get("voter_count") or 0) for option in options]
    )
    if len(resolved_counts) < len(options):
        resolved_counts.extend([0] * (len(options) - len(resolved_counts)))

    total_voters_raw = raw_poll.get("total_voter_count")
    if isinstance(total_voters_raw, int):
        total_voters = max(total_voters_raw, 0)
    else:
        total_voters = 0
    total_voters += max(extra_voters, 0)

    option_payload = []
    for idx, option in enumerate(options):
        option_item: dict[str, object] = {
            "index": idx,
            "text": str(option.get("text") or "").strip(),
            "voter_count": max(int(resolved_counts[idx]), 0),
        }
        post_id = _parse_post_reference_to_id(option.get("post_id"))
        if post_id is not None:
            option_item["post_id"] = post_id
        post_path = str(option.get("post_path") or "").strip()
        if post_path.startswith("/"):
            option_item["post_path"] = post_path
        option_payload.append(option_item)

    normalized_selection = _normalize_poll_selection(user_selection or [], len(option_payload))
    poll_id = str(raw_poll.get("id") or "").strip()
    close_at_raw = (
        str(raw_poll.get("close_at") or raw_poll.get("ends_at") or raw_poll.get("expires_at") or "")
        .strip()
    )
    close_at_parsed = _parse_poll_close_at(close_at_raw) if close_at_raw else None
    close_at = (
        close_at_parsed.astimezone(dt_timezone.utc).isoformat().replace("+00:00", "Z")
        if close_at_parsed
        else None
    )
    is_closed = _poll_is_closed(raw_poll)
    return {
        "id": poll_id or None,
        "question": question,
        "is_anonymous": bool(raw_poll.get("is_anonymous")),
        "allows_multiple_answers": bool(raw_poll.get("allows_multiple_answers")),
        "is_closed": is_closed,
        "close_at": close_at,
        "total_voter_count": total_voters,
        "options": option_payload,
        "user_selection": normalized_selection,
    }


def _render_poll_html_from_payload(payload: dict) -> str:
    options = payload.get("options") or []
    total_voters = max(int(payload.get("total_voter_count") or 0), 0)
    selected_set = set(payload.get("user_selection") or [])

    option_items: list[str] = []
    for option in options:
        idx = int(option.get("index", -1))
        post_id = _parse_post_reference_to_id(option.get("post_id"))
        text = str(option.get("text") or "").strip()
        decoded_option_title = _extract_editor_payload_title(text)
        if decoded_option_title:
            text = decoded_option_title
        elif post_id and len(text) >= 48 and re.fullmatch(r"[A-Za-z0-9_\-+/=]+", text):
            text = f"Пост #{post_id}"
        count = max(int(option.get("voter_count") or 0), 0)
        value_label = str(count)
        if total_voters > 0:
            percent = round((count / total_voters) * 100)
            value_label = f"{count} ({percent}%)"
        option_class = "post-poll-option is-selected" if idx in selected_set else "post-poll-option"
        marker = "✓ " if idx in selected_set else ""
        option_items.append(
            f'<li class="{option_class}" data-option-index="{idx}">{marker}{escape(text)} <b>{value_label}</b></li>'
        )
    options_html = (
        f'<ul class="post-poll-options">{"".join(option_items)}</ul>' if option_items else ""
    )

    meta_parts: list[str] = []
    if payload.get("is_anonymous"):
        meta_parts.append("Анонимный опрос")
    if payload.get("allows_multiple_answers"):
        meta_parts.append("Можно выбрать несколько вариантов")
    if payload.get("is_closed"):
        meta_parts.append("Опрос завершен")
    else:
        meta_parts.append("Нажмите вариант, чтобы проголосовать")
    close_at_label = _format_poll_close_at_label(payload.get("close_at"))
    if close_at_label:
        meta_parts.append(f"До {close_at_label}")
    meta_parts.append(f"Голосов: {total_voters}")
    meta_html = f'<div class="post-poll-meta">{" · ".join(meta_parts)}</div>'

    question = str(payload.get("question") or "").strip()
    question_html = f'<div class="post-poll-question"><b>{escape(question)}</b></div>' if question else ""
    poll_attrs = [
        f'data-poll-multiple="{"1" if payload.get("allows_multiple_answers") else "0"}"',
        f'data-poll-closed="{"1" if payload.get("is_closed") else "0"}"',
    ]
    poll_id = payload.get("id")
    if poll_id:
        poll_attrs.append(f'data-poll-id="{escape(str(poll_id))}"')
    attrs = " ".join(poll_attrs)
    return (
        f'<div class="post-poll" {attrs}>'
        + "".join(part for part in (question_html, options_html, meta_html) if part)
        + "</div>"
    )


def _live_poll_for_post(post: Post, user: User | None = None) -> dict | None:
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    raw_poll = raw_data.get("poll")
    payload = _build_poll_payload(raw_poll)
    if not payload:
        return None

    options = payload.get("options") or []
    options_count = len(options)
    counts = [int(option.get("voter_count") or 0) for option in options]
    user_selection: list[int] = []
    site_voters: set[int] = set()

    votes = PostPollVote.objects.filter(post=post).values_list("user_id", "selected_options")
    for vote_user_id, selected_options in votes:
        normalized = _normalize_poll_selection(selected_options, options_count)
        if not normalized:
            continue
        site_voters.add(vote_user_id)
        for index in normalized:
            counts[index] += 1
        if user and vote_user_id == user.id:
            user_selection = normalized

    live_payload = _build_poll_payload(
        raw_poll,
        option_counts=counts,
        user_selection=user_selection,
        extra_voters=len(site_voters),
    )
    if not live_payload:
        return None
    return {
        "poll": live_payload,
        "html": _render_poll_html_from_payload(live_payload),
    }


def _extract_telegram_poll(message: dict) -> tuple[str, str]:
    poll = message.get("poll")
    payload = _build_poll_payload(poll)
    if not payload:
        return "", ""

    question = str(payload.get("question") or "").strip()
    poll_html = _render_poll_html_from_payload(payload)
    title = _build_title(question) if question else ""
    if not title:
        title = "Опрос"
    return poll_html, title


def _fetch_telegram_json(method: str, token: str, payload: dict) -> dict | None:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode("utf-8")
    try:
        timeout = 30 if method == "getUpdates" else 5
        with urllib.request.urlopen(url, data=data, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


@csrf_exempt
def content_page_manage(request: HttpRequest, slug: str) -> HttpResponse:
    page_slug = str(slug or "").strip().lower()
    if page_slug not in _EDITABLE_STATIC_PAGE_TITLES:
        return JsonResponse({"ok": False, "error": "page not found"}, status=404)

    page = (
        StaticPageContent.objects.select_related("updated_by")
        .filter(slug=page_slug)
        .first()
    )

    if request.method == "GET":
        return JsonResponse({"ok": True, "page": _serialize_static_page_content(page, page_slug)})

    if request.method not in ("PATCH", "POST"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if not user.is_staff:
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    if "content" not in payload:
        return JsonResponse({"ok": False, "error": "content is required"}, status=400)
    content = str(payload.get("content") or "").strip()
    if len(content) > 200000:
        return JsonResponse({"ok": False, "error": "content too long"}, status=400)

    title = str(payload.get("title") or "").strip()
    if not title:
        title = _EDITABLE_STATIC_PAGE_TITLES[page_slug]
    if len(title) > 160:
        title = title[:160].strip()

    if not page:
        page = StaticPageContent(slug=page_slug)
    page.title = title
    page.content = content
    page.updated_by = user
    page.save()

    return JsonResponse({"ok": True, "page": _serialize_static_page_content(page, page_slug)})


def _post_public_path(post: Post) -> str:
    post_title = _post_display_title(post)
    post_slug = _slugify_title(post_title)
    return f"/b/post/{post.id}-{post_slug}" if post_slug else f"/b/post/{post.id}"


def _serialize_post_vote_poll_participations(
    post: Post,
    *,
    limit: int = 3,
) -> list[dict]:
    post_id = int(getattr(post, "id", 0) or 0)
    if post_id <= 0 or limit <= 0:
        return []

    now = timezone.now()
    candidate_limit = min(max(limit * 4, 12), 40)
    try:
        candidates = list(
            Post.objects.filter(
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .filter(_publish_ready_filter(now))
            .exclude(id=post_id)
            .filter(raw_data__poll__options__contains=[{"post_id": post_id}])
            .order_by("-created_at")[:candidate_limit]
        )
    except Exception:
        return []

    result: list[dict] = []
    seen_poll_post_ids: set[int] = set()
    for candidate in candidates:
        raw_data = candidate.raw_data if isinstance(candidate.raw_data, dict) else {}
        raw_poll = raw_data.get("poll")
        if not isinstance(raw_poll, dict):
            continue

        has_target_post = any(
            _parse_post_reference_to_id(option.get("post_id") or option.get("post_ref")) == post_id
            for option in _extract_poll_options(raw_poll)
        )
        if not has_target_post:
            continue

        poll_payload = _build_poll_payload(raw_poll)
        if not poll_payload or bool(poll_payload.get("is_closed")):
            continue

        poll_post_id = int(candidate.id)
        if poll_post_id in seen_poll_post_ids:
            continue
        seen_poll_post_ids.add(poll_post_id)

        poll_post_title = _post_display_title(candidate)
        poll_question = str(poll_payload.get("question") or "").strip() or poll_post_title
        result.append(
            {
                "poll_post_id": poll_post_id,
                "poll_post_title": poll_post_title,
                "poll_post_path": _post_public_path(candidate),
                "question": poll_question,
                "close_at": poll_payload.get("close_at"),
            }
        )
        if len(result) >= limit:
            break

    return result


def _favorite_post_ids_for_user(posts: list[Post], user: User | None) -> set[int]:
    if not user or not posts:
        return set()
    post_ids = [post.id for post in posts if post and post.id]
    if not post_ids:
        return set()
    return set(
        PostFavorite.objects.filter(user=user, post_id__in=post_ids).values_list(
            "post_id", flat=True
        )
    )


@csrf_exempt
def post_comments(request: HttpRequest, post_id: int) -> HttpResponse:
    try:
        now = timezone.now()
        post = (
            Post.objects.select_related("author")
            .filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    if request.method == "GET":
        user = _get_user_from_request(request)
        comments = (
            PostComment.objects.filter(post=post)
            .select_related("user")
            .annotate(likes_count=Count("likes", distinct=True))
            .order_by("created_at")
        )
        liked_ids = set()
        if user:
            liked_ids = set(
                PostCommentLike.objects.filter(user=user, comment__post=post).values_list(
                    "comment_id", flat=True
                )
            )
        serialized = [
            _serialize_site_comment(
                comment,
                liked_by_me=comment.id in liked_ids,
                likes_count=comment.likes_count,
                can_edit=_can_edit_site_comment(user, comment),
            )
            for comment in comments
        ]
        return JsonResponse(
            {
                "ok": True,
                "comments": serialized,
                "comment_masks": _comment_personas_for_user(user),
            }
        )

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    body = (payload.get("body") or "").strip()
    parent_id = payload.get("parent_id")
    mask_key = str(payload.get("mask_key") or "").strip()
    if not body:
        return JsonResponse({"ok": False, "error": "comment is empty"}, status=400)
    if len(body) > 2000:
        return JsonResponse({"ok": False, "error": "comment too long"}, status=400)

    parent = None
    if parent_id:
        try:
            parent = PostComment.objects.get(id=int(parent_id), post=post, is_deleted=False)
        except (PostComment.DoesNotExist, ValueError, TypeError):
            return JsonResponse({"ok": False, "error": "parent comment not found"}, status=404)

    persona = None
    comment_user = user
    if mask_key:
        if not user.is_staff:
            return JsonResponse({"ok": False, "error": "forbidden"}, status=403)
        persona = _COMMENT_PERSONAS_BY_KEY.get(mask_key)
        if not persona:
            return JsonResponse({"ok": False, "error": "invalid comment mask"}, status=400)
        persona_user = _ensure_comment_persona_user(persona)
        if not persona_user:
            return JsonResponse({"ok": False, "error": "comment mask unavailable"}, status=500)
        comment_user = persona_user

    comment = PostComment.objects.create(
        post=post,
        user=comment_user,
        body=body,
        parent=parent,
        persona_key=(persona or {}).get("key", ""),
        persona_username=(persona or {}).get("username", ""),
    )
    Post.objects.filter(id=post.id).update(comments_count=F("comments_count") + 1)
    post.refresh_from_db(fields=["comments_count"])
    community_service._recalculate_comun_ratings_for_post(post)
    _maybe_notify_post_comment(post, comment)
    _maybe_notify_comment_reply(post, parent, comment)
    _maybe_notify_author_comment(post, comment)

    return JsonResponse(
        {
            "ok": True,
            "comment": _serialize_site_comment(
                comment,
                liked_by_me=False,
                likes_count=0,
                can_edit=True,
            ),
            "comments_count": post.comments_count,
        }
    )


@csrf_exempt
def comment_detail(request: HttpRequest, comment_id: int) -> HttpResponse:
    if request.method not in ("PATCH", "DELETE"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        comment = PostComment.objects.select_related("post", "user").get(id=comment_id)
    except PostComment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    if comment.is_deleted:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    if not _can_edit_site_comment(user, comment):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    if request.method == "PATCH":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

        body = (payload.get("body") or "").strip()
        if not body:
            return JsonResponse({"ok": False, "error": "comment is empty"}, status=400)
        if len(body) > 2000:
            return JsonResponse({"ok": False, "error": "comment too long"}, status=400)

        comment.body = body
        comment.save(update_fields=["body", "updated_at"])
        likes_count = PostCommentLike.objects.filter(comment=comment).count()
        liked_by_me = PostCommentLike.objects.filter(comment=comment, user=user).exists()

        return JsonResponse(
            {
                "ok": True,
                "comment": _serialize_site_comment(
                    comment,
                    liked_by_me=liked_by_me,
                    likes_count=likes_count,
                    can_edit=True,
                ),
            }
        )

    comment.is_deleted = True
    comment.save(update_fields=["is_deleted", "updated_at"])
    Post.objects.filter(id=comment.post_id, comments_count__gt=0).update(
        comments_count=F("comments_count") - 1
    )
    community_service._recalculate_comun_ratings_for_post(comment.post_id)

    return JsonResponse({"ok": True, "comment_id": comment.id})


@csrf_exempt
def comment_like(request: HttpRequest, comment_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        now = timezone.now()
        comment = (
            PostComment.objects.select_related("post", "post__author")
            .filter(
                id=comment_id,
                is_deleted=False,
                post__is_blocked=False,
                post__is_pending=False,
                post__author__is_blocked=False,
            )
            .filter(Q(post__publish_at__isnull=True) | Q(post__publish_at__lte=now))
            .get()
        )
    except PostComment.DoesNotExist:
        return JsonResponse({"ok": False, "error": "comment not found"}, status=404)

    existing = PostCommentLike.objects.filter(comment=comment, user=user).first()
    delta = 0
    if existing:
        existing.delete()
        liked = False
        delta = -1
    else:
        PostCommentLike.objects.create(comment=comment, user=user)
        liked = True
        delta = 1

    if delta:
        _apply_author_rating_delta(
            author_id=comment.post.author_id,
            delta=delta,
            event_type=AuthorRatingEvent.EVENT_TYPE_COMMENT_LIKE,
            actor_id=user.id,
            post_id=comment.post_id,
            comment_id=comment.id,
        )

    likes_count = PostCommentLike.objects.filter(comment=comment).count()

    return JsonResponse({"ok": True, "liked": liked, "likes_count": likes_count})


@csrf_exempt
def post_like(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        now = timezone.now()
        post = (
            Post.objects.select_related("author")
            .filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    vote_value = 1
    if request.body:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            vote_value = int(payload.get("value", payload.get("vote", payload.get("score", 1))))

    if vote_value not in (-1, 0, 1):
        return JsonResponse({"ok": False, "error": "invalid vote value"}, status=400)

    existing = PostLike.objects.filter(post=post, user=user).first()
    delta = 0
    new_vote = 0
    if existing:
        if vote_value == 0 or existing.value == vote_value:
            delta = -existing.value
            existing.delete()
            new_vote = 0
        else:
            delta = vote_value - existing.value
            existing.value = vote_value
            existing.save(update_fields=["value"])
            new_vote = vote_value
    else:
        if vote_value != 0:
            PostLike.objects.create(post=post, user=user, value=vote_value)
            delta = vote_value
            new_vote = vote_value

    if delta:
        Post.objects.filter(id=post.id).update(rating=F("rating") + delta)
        _apply_author_rating_delta(
            author_id=post.author_id,
            delta=delta,
            event_type=AuthorRatingEvent.EVENT_TYPE_POST_LIKE,
            actor_id=user.id,
            post_id=post.id,
        )
        community_service._recalculate_comun_ratings_for_post(post.id)

    liked = new_vote == 1

    post.refresh_from_db(fields=["rating"])
    return JsonResponse(
        {
            "ok": True,
            "liked": liked,
            "vote": new_vote,
            "likes_count": post.rating,
                "views_count": _post_total_views(post, now),
        }
    )


@csrf_exempt
def post_favorite(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    try:
        now = timezone.now()
        post = (
            Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    favorite_requested: bool | None = None
    if request.body:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict) and "favorite" in payload:
            favorite_requested = bool(payload.get("favorite"))

    existing = PostFavorite.objects.filter(post=post, user=user).first()
    if favorite_requested is None:
        favorite_requested = existing is None

    if favorite_requested:
        if not existing:
            PostFavorite.objects.create(post=post, user=user)
        favorited = True
    else:
        if existing:
            existing.delete()
        favorited = False

    favorites_count = PostFavorite.objects.filter(post=post).count()
    return JsonResponse(
        {
            "ok": True,
            "favorited": favorited,
            "is_favorite": favorited,
            "favorites_count": favorites_count,
        }
    )


def recent_comments(request: HttpRequest) -> HttpResponse:
    limit_raw = request.GET.get("limit", "5")
    try:
        limit = min(max(int(limit_raw), 1), 20)
    except ValueError:
        limit = 5

    now = timezone.now()
    comments = (
        PostComment.objects.filter(
            is_deleted=False,
            post__is_blocked=False,
            post__is_pending=False,
            post__author__is_blocked=False,
        )
        .filter(Q(post__publish_at__isnull=True) | Q(post__publish_at__lte=now))
        .select_related("user", "post")
        .order_by("-created_at")[:limit]
    )

    serialized = [
        {
            "id": comment.id,
            "body": comment.body,
            "created_at": comment.created_at.isoformat(),
            "user": _serialize_comment_user(comment),
            "post": {"id": comment.post_id, "title": _post_display_title(comment.post)},
        }
        for comment in comments
    ]

    return JsonResponse({"ok": True, "comments": serialized})


def author_posts(request: HttpRequest, username: str) -> HttpResponse:
    try:
        author = Author.objects.get(username__iexact=username)
    except Author.DoesNotExist:
        return JsonResponse({"ok": False, "error": "author not found"}, status=404)

    if author.is_blocked:
        return JsonResponse({"ok": False, "error": "author not found"}, status=404)

    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 10
    offset_raw = request.GET.get("offset", "0")
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0
    current_user = _get_user_from_request(request)

    now = timezone.now()
    posts = list(
        Post.objects.filter(author=author, is_blocked=False, is_pending=False)
        .filter(_publish_ready_filter(now))
        .prefetch_related("tags")
        .order_by("-created_at")
        .all()[offset : offset + limit]
    )
    favorite_post_ids = _favorite_post_ids_for_user(posts, current_user)

    posts_count = (
        Post.objects.filter(author=author, is_blocked=False, is_pending=False)
        .filter(_publish_ready_filter(now))
        .count()
    )
    linked_comun = community_views._author_telegram_source_comun(author)
    site_user_id = _site_user_id_for_author(author)
    author_channel_url = author.invite_url or author.channel_url
    serialized = []
    for post in posts:
        content, poll_payload = _content_with_live_poll(post, current_user)
        author_channel_url, author_title = _author_display_fields(
            request, author, post.channel_url
        )
        serialized.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "template": _serialize_post_template(post),
                "comun": community_service._serialize_post_comun(request, post),
                "content": content,
                "poll": poll_payload,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "views_count": _post_total_views(post, now),
                "tags": _serialize_tags(post.tags.all()),
                "is_favorite": post.id in favorite_post_ids,
                "author": {
                    "username": author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_display(request, author),
                    "description": author.description,
                    "subscribers_count": author.subscribers_count,
                    **_author_admin_fields_for_user(current_user, author),
                },
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "author": {
                "username": author.username,
                "title": author.title,
                "channel_url": author_channel_url,
                "avatar_url": _author_avatar_url(request, author),
                "description": author.description,
                "subscribers_count": author.subscribers_count,
                "posts_count": posts_count,
                "author_rating": _author_rating_value(author.rating_total),
                "site_user_id": site_user_id,
                "linked_comun_slug": linked_comun.slug if linked_comun and linked_comun.is_active else None,
                "linked_comun_name": linked_comun.name if linked_comun and linked_comun.is_active else None,
            },
            "posts": serialized,
        }
    )


def tags_list(request: HttpRequest) -> HttpResponse:
    tags = Tag.objects.filter(is_active=True).order_by("name")
    return JsonResponse(
        {
            "ok": True,
            "tags": [
                {"name": tag.name, "lemma": tag.lemma or _lemmatize_tag(tag.name) or tag.name, "mood": tag.mood}
                for tag in tags
            ],
        }
    )


def _ensure_tag_by_name(raw_name: str) -> tuple[Tag | None, bool]:
    normalized = _normalize_tag_value(raw_name).lstrip("#").strip()
    if not normalized:
        return None, False
    lemma = _lemmatize_tag(normalized) or normalized
    tag = (
        Tag.objects.filter(Q(name__iexact=normalized) | Q(lemma__iexact=lemma))
        .order_by("name")
        .first()
    )
    if tag:
        if not tag.is_active:
            tag.is_active = True
            tag.save(update_fields=["is_active"])
        if not tag.lemma:
            tag.lemma = lemma
            tag.save(update_fields=["lemma"])
        return tag, False
    return Tag.objects.create(name=normalized, lemma=lemma), True


@csrf_exempt
def tags_ensure(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    current_user = _get_user_from_request(request)
    if not current_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    tag, created = _ensure_tag_by_name(str(body.get("name") or ""))
    if not tag:
        return JsonResponse({"ok": False, "error": "tag name required"}, status=400)

    return JsonResponse(
        {
            "ok": True,
            "created": created,
            "tag": {
                "id": tag.id,
                "name": tag.name,
                "lemma": tag.lemma or _lemmatize_tag(tag.name) or tag.name,
            },
        }
    )


def tag_posts(request: HttpRequest, tag: str) -> HttpResponse:
    if not tag:
        return JsonResponse({"ok": False, "error": "tag not found"}, status=404)

    normalized = _normalize_tag_value(tag)
    lemma = _lemmatize_tag(normalized) or normalized
    tags_qs = Tag.objects.filter(is_active=True).filter(
        Q(lemma__iexact=lemma) | Q(name__iexact=normalized)
    )
    if not tags_qs.exists():
        return JsonResponse({"ok": False, "error": "tag not found"}, status=404)
    tag_obj = (
        tags_qs.filter(name__iexact=normalized).first()
        or tags_qs.filter(lemma__iexact=lemma).first()
        or tags_qs.first()
    )

    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 10
    offset_raw = request.GET.get("offset", "0")
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0
    current_user = _get_user_from_request(request)

    now = timezone.now()
    posts = list(
        Post.objects.filter(
            tags__in=tags_qs,
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .prefetch_related("tags")
        .select_related("author")
        .order_by("-created_at")
        .all()[offset : offset + limit]
    )
    favorite_post_ids = _favorite_post_ids_for_user(posts, current_user)

    serialized = []
    for post in posts:
        content, poll_payload = _content_with_live_poll(post, current_user)
        author_channel_url, author_title = _author_display_fields(
            request, post.author, post.channel_url
        )
        serialized.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "template": _serialize_post_template(post),
                "comun": community_service._serialize_post_comun(request, post),
                "content": content,
                "poll": poll_payload,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "views_count": _post_total_views(post, now),
                "tags": _serialize_tags(post.tags.all()),
                "is_favorite": post.id in favorite_post_ids,
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_display(request, post.author),
                    **_author_admin_fields_for_user(current_user, post.author),
                },
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "tag": {
                "name": tag_obj.name,
                "lemma": tag_obj.lemma or _lemmatize_tag(tag_obj.name) or tag_obj.name,
            },
            "posts": serialized,
        }
    )


def post_detail(request: HttpRequest, post_id: int) -> HttpResponse:
    try:
        now = timezone.now()
        post = (
            Post.objects.select_related("author")
            .prefetch_related("tags")
            .filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)
    current_user = _get_user_from_request(request)
    content, poll_payload = _content_with_live_poll(post, current_user)
    author_channel_url, author_title = _author_display_fields(
        request, post.author, post.channel_url
    )
    return JsonResponse(
        {
            "ok": True,
            "post": {
                "id": post.id,
                "title": _post_display_title(post),
                "template": _serialize_post_template(post),
                "vote_poll_participations": _serialize_post_vote_poll_participations(post),
                "comun": community_service._serialize_post_comun(request, post),
                "content": content,
                "poll": poll_payload,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "views_count": _post_total_views(post, now),
                "tags": _serialize_tags(post.tags.all()),
                "is_favorite": (
                    PostFavorite.objects.filter(post=post, user=current_user).exists()
                    if current_user
                    else False
                ),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_display(request, post.author),
                    **_author_admin_fields_for_user(current_user, post.author),
                },
            },
        }
    )


@csrf_exempt
def post_read(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    try:
        post = Post.objects.get(id=post_id, is_blocked=False, author__is_blocked=False)
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)
    PostRead.objects.get_or_create(post=post, user=user)
    return JsonResponse({"ok": True})


@csrf_exempt
def post_view(request: HttpRequest, post_id: int) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    try:
        now = timezone.now()
        post = (
            Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
            .filter(_publish_ready_filter(now))
            .get(id=post_id)
        )
    except Post.DoesNotExist:
        return JsonResponse({"ok": False, "error": "post not found"}, status=404)

    Post.objects.filter(id=post.id).update(real_views_count=F("real_views_count") + 1)
    post.real_views_count = (post.real_views_count or 0) + 1
    return JsonResponse({"ok": True, "views_count": _post_total_views(post, now)})


def home_feed(request: HttpRequest) -> HttpResponse:
    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 200)
    except ValueError:
        limit = 10
    offset_raw = request.GET.get("offset", "0")
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    hide_read = request.GET.get("hide_read") in {"1", "true", "True"}
    only_read = request.GET.get("only_read") in {"1", "true", "True"}
    now = timezone.now()
    read_user = (
        _get_user_from_request(request) if (hide_read or only_read) else None
    )
    current_user = read_user or _get_user_from_request(request)
    if only_read and not read_user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    target_count = limit + offset
    fetch_size = max(target_count * 5, limit * 5)
    combined_scaled = Cast(F("rating"), IntegerField()) * Value(20) + Cast(
        F("author__rating_total"), IntegerField()
    )
    hidden_home_tag_qs = Tag.objects.filter(
        posts__id=OuterRef("pk"),
        hide_from_home=True,
    )
    hidden_home_comun_slugs = list(
        Comun.objects.filter(hide_from_home=True).values_list("slug", flat=True)
    )
    hidden_home_comun_category_post_ids = ComunPostCategoryAssignment.objects.filter(
        category__hide_from_home=True,
    ).values("post_id")
    base_query = (
        Post.objects.filter(
            is_blocked=False,
            is_pending=False,
            author__is_blocked=False,
        )
        .filter(_publish_ready_filter(now))
        .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
        .annotate(combined_scaled=combined_scaled)
        .annotate(has_hidden_home_tag=Exists(hidden_home_tag_qs))
        .filter(has_hidden_home_tag=False)
        .filter(combined_scaled__gte=0)
        .exclude(id__in=hidden_home_comun_category_post_ids)
    )
    if hidden_home_comun_slugs:
        hidden_home_comun_post_ids = Post.objects.filter(
            raw_data__source="manual_comun",
            raw_data__comun_slug__in=hidden_home_comun_slugs,
        ).exclude(
            comun_category_assignments__category_id__isnull=False,
        ).values("id")
        base_query = base_query.exclude(id__in=hidden_home_comun_post_ids)
    hidden_read_count = 0
    if hide_read and read_user:
        hidden_read_count = base_query.filter(reads__user=read_user).count()

    if only_read:
        posts_page = list(
            base_query.filter(reads__user=read_user)
            .select_related("author")
            .prefetch_related("tags")
            .order_by("-created_at")[offset : offset + limit]
        )
        favorite_post_ids = _favorite_post_ids_for_user(posts_page, current_user)
        serialized = []
        for post in posts_page:
            author_rating = _author_rating_value(post.author.rating_total)
            content, poll_payload = _content_with_live_poll(post, current_user)
            author_channel_url, author_title = _author_display_fields(
                request, post.author, post.channel_url
            )
            serialized.append(
                {
                    "id": post.id,
                    "title": _post_display_title(post),
                    "template": _serialize_post_template(post),
                    "comun": community_service._serialize_post_comun(request, post),
                    "content": content,
                    "poll": poll_payload,
                    "source_url": post.source_url,
                    "channel_url": author_channel_url,
                    "created_at": post.created_at.isoformat(),
                    "author": {
                        "username": post.author.username,
                        "title": author_title,
                        "channel_url": author_channel_url,
                        "avatar_url": _author_avatar_for_display(request, post.author),
                        **_author_admin_fields_for_user(current_user, post.author),
                    },
                    "tags": _serialize_tags(post.tags.all()),
                    "is_favorite": post.id in favorite_post_ids,
                    "score": post.rating + post.comments_count * 5 + author_rating,
                    "rating": post.rating,
                    "comments_count": post.comments_count,
                    "likes_count": post.rating,
                "views_count": _post_total_views(post, now),
                }
            )
        return JsonResponse(
            {"ok": True, "posts": serialized, "hidden_read_count": hidden_read_count}
        )

    posts_query = base_query
    if hide_read and read_user:
        posts_query = posts_query.exclude(reads__user=read_user)
    posts = list(
        posts_query.select_related("author")
        .prefetch_related("tags")
        .order_by("-created_at")[:fetch_size]
    )
    favorite_post_ids = _favorite_post_ids_for_user(posts, current_user)
    author_ids = {post.author_id for post in posts}
    author_rating_map = {}
    if author_ids:
        author_rating_map = {
            row["id"]: _author_rating_value(row["rating_total"])
            for row in Author.objects.filter(id__in=author_ids).values(
                "id", "rating_total"
            )
        }

    serialized_posts = []
    remaining = posts[:]
    last_author_id = None

    while remaining and len(serialized_posts) < target_count:
        next_index = None
        for idx, candidate in enumerate(remaining):
            if candidate.author_id != last_author_id:
                next_index = idx
                break
        if next_index is None:
            next_index = 0
        post = remaining.pop(next_index)
        author_rating = author_rating_map.get(post.author_id, 0)
        content, poll_payload = _content_with_live_poll(post, current_user)
        combined_rating = post.rating + author_rating
        if combined_rating < 0:
            continue
        author_channel_url, author_title = _author_display_fields(
            request, post.author, post.channel_url
        )
        serialized_posts.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "template": _serialize_post_template(post),
                "comun": community_service._serialize_post_comun(request, post),
                "content": content,
                "poll": poll_payload,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_display(request, post.author),
                    **_author_admin_fields_for_user(current_user, post.author),
                },
                "tags": _serialize_tags(post.tags.all()),
                "is_favorite": post.id in favorite_post_ids,
                "score": post.rating + post.comments_count * 5 + author_rating,
                "rating": post.rating,
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "views_count": _post_total_views(post, now),
            }
        )
        last_author_id = post.author_id

    return JsonResponse(
        {
            "ok": True,
            "posts": serialized_posts[offset : offset + limit],
            "hidden_read_count": hidden_read_count,
        }
    )


def favorites_feed(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    limit_raw = request.GET.get("limit", "10")
    try:
        limit = min(max(int(limit_raw), 1), 200)
    except ValueError:
        limit = 10
    offset_raw = request.GET.get("offset", "0")
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    now = timezone.now()
    hide_read = request.GET.get("hide_read") in ("1", "true", "yes")
    only_read = request.GET.get("only_read") in ("1", "true", "yes")

    favorites_qs = (
        PostFavorite.objects.filter(
            user=user,
            post__is_blocked=False,
            post__is_pending=False,
            post__author__is_blocked=False,
        )
        .filter(Q(post__publish_at__isnull=True) | Q(post__publish_at__lte=now))
        .filter(Q(post__author__shadow_banned=False) | Q(post__author__force_home=True))
        .select_related("post__author")
        .prefetch_related("post__tags")
        .order_by("-created_at")
    )

    # "Favorites" always shows all favorited posts, regardless of read-status filters.
    hidden_read_count = 0
    filtered_favorites = favorites_qs

    favorite_rows = list(filtered_favorites[offset : offset + limit])
    posts = [row.post for row in favorite_rows]
    favorite_post_ids = {post.id for post in posts}

    serialized = []
    for post in posts:
        content, poll_payload = _content_with_live_poll(post, user)
        author_channel_url, author_title = _author_display_fields(
            request, post.author, post.channel_url
        )
        serialized.append(
            {
                "id": post.id,
                "title": _post_display_title(post),
                "template": _serialize_post_template(post),
                "comun": community_service._serialize_post_comun(request, post),
                "content": content,
                "poll": poll_payload,
                "source_url": post.source_url,
                "channel_url": author_channel_url,
                "created_at": post.created_at.isoformat(),
                "author": {
                    "username": post.author.username,
                    "title": author_title,
                    "channel_url": author_channel_url,
                    "avatar_url": _author_avatar_for_display(request, post.author),
                    **_author_admin_fields_for_user(user, post.author),
                },
                "tags": _serialize_tags(post.tags.all()),
                "is_favorite": post.id in favorite_post_ids,
                "score": post.rating + post.comments_count * 5,
                "rating": post.rating,
                "comments_count": post.comments_count,
                "likes_count": post.rating,
                "views_count": _post_total_views(post, now),
            }
        )

    return JsonResponse(
        {"ok": True, "posts": serialized, "hidden_read_count": hidden_read_count}
    )


def _serialize_backend_post_card(
    request: HttpRequest,
    post: Post,
    current_user: User | None,
    *,
    now=None,
    is_favorite: bool = False,
) -> dict:
    now = now or timezone.now()
    content, poll_payload = _content_with_live_poll(post, current_user)
    template_payload = _serialize_post_template(post)
    author_channel_url, author_title = _author_display_fields(
        request, post.author, post.channel_url
    )
    return {
        "id": post.id,
        "title": _post_display_title(post),
        "template": template_payload,
        "enabled_template_editor_blocks": _serialize_enabled_template_editor_blocks(template_payload),
        "comun": community_service._serialize_post_comun(request, post),
        "content": content,
        "poll": poll_payload,
        "post_ratings": _serialize_post_ratings(post, current_user),
        "post_rating": _serialize_post_rating(post, current_user, template_payload=template_payload),
        "source_url": post.source_url,
        "channel_url": author_channel_url,
        "created_at": post.created_at.isoformat(),
        "author": {
            "username": post.author.username,
            "title": author_title,
            "channel_url": author_channel_url,
            "avatar_url": _author_avatar_for_display(request, post.author),
            **_author_admin_fields_for_user(current_user, post.author),
        },
        "tags": _serialize_tags(post.tags.all()),
        "is_favorite": is_favorite,
        "score": post.rating + post.comments_count * 5,
        "rating": post.rating,
        "comments_count": post.comments_count,
        "likes_count": post.rating,
        "views_count": _post_total_views(post, now),
    }


def _serialize_search_author_result(
    request: HttpRequest,
    author: Author,
) -> dict:
    author_channel_url, author_title = _author_display_fields(request, author)
    return {
        "username": author.username,
        "title": author_title,
        "avatar_url": _author_avatar_for_display(request, author),
        "description": author.description,
        "channel_url": author_channel_url or "",
        "subscribers_count": author.subscribers_count,
        "author_rating": _author_rating_value(author.rating_total),
    }


def _serialize_search_site_user_result(
    request: HttpRequest,
    user: User,
) -> dict:
    return {
        "username": user.username,
        "title": _site_user_display_name(user) or user.username,
        "avatar_url": _site_user_avatar_url(request, user),
        "description": "",
        "channel_url": "",
        "subscribers_count": 0,
        "author_rating": None,
    }


def _search_author_result_rank(item: dict, query: str) -> tuple[int, str]:
    normalized_query = (query or "").strip().lower()
    username = str(item.get("username") or "").strip().lower()
    title = str(item.get("title") or "").strip().lower()
    if not normalized_query:
        return (10, username)
    if username == normalized_query:
        return (0, username)
    if title == normalized_query:
        return (1, username)
    if username.startswith(normalized_query):
        return (2, username)
    if title.startswith(normalized_query):
        return (3, username)
    if normalized_query in username:
        return (4, username)
    if normalized_query in title:
        return (5, username)
    return (6, username)


def search_content(request: HttpRequest) -> HttpResponse:
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse(
            {
                "ok": True,
                "query": "",
                "page": 1,
                "limit": 0,
                "posts": [],
                "authors": [],
                "total_posts": 0,
                "total_authors": 0,
            }
        )

    type_filter = (request.GET.get("type") or "All").lower()
    sort = (request.GET.get("sort") or "New").lower()
    current_user = _get_user_from_request(request)

    limit_raw = request.GET.get("limit", "20")
    page_raw = request.GET.get("page", "1")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 20
    try:
        page = max(int(page_raw), 1)
    except ValueError:
        page = 1

    offset = (page - 1) * limit

    posts: list[dict] = []
    authors: list[dict] = []
    total_posts = 0
    total_authors = 0

    if type_filter in ("all", "posts"):
        post_query = Q(title__icontains=query) | Q(content__icontains=query)
        post_query |= Q(author__username__icontains=query) | Q(
            author__title__icontains=query
        )
        now = timezone.now()
        posts_qs = (
            Post.objects.filter(
                post_query,
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .filter(_publish_ready_filter(now))
            .select_related("author")
            .prefetch_related("tags")
            .order_by("-created_at" if sort == "new" else "-created_at")
        )
        total_posts = posts_qs.count()
        posts_page = list(posts_qs[offset : offset + limit])
        favorite_post_ids = _favorite_post_ids_for_user(posts_page, current_user)
        for post in posts_page:
            content, poll_payload = _content_with_live_poll(post, current_user)
            author_channel_url, author_title = _author_display_fields(
                request, post.author, post.channel_url
            )
            posts.append(
                {
                    "id": post.id,
                    "title": _post_display_title(post),
                    "template": _serialize_post_template(post),
                    "comun": community_service._serialize_post_comun(request, post),
                    "content": content,
                    "poll": poll_payload,
                    "source_url": post.source_url,
                    "channel_url": author_channel_url,
                    "created_at": post.created_at.isoformat(),
                    "comments_count": post.comments_count,
                    "likes_count": post.rating,
                "views_count": _post_total_views(post, now),
                    "tags": _serialize_tags(post.tags.all()),
                    "is_favorite": post.id in favorite_post_ids,
                    "author": {
                        "username": post.author.username,
                        "title": author_title,
                        "channel_url": author_channel_url,
                        "avatar_url": _author_avatar_for_display(request, post.author),
                        "description": post.author.description,
                        "subscribers_count": post.author.subscribers_count,
                        **_author_admin_fields_for_user(current_user, post.author),
                    },
                }
            )

    if type_filter in ("all", "users", "authors"):
        authors_qs = (
            Author.objects.filter(is_blocked=False)
            .filter(
                Q(username__icontains=query)
                | Q(title__icontains=query)
                | Q(description__icontains=query)
            )

            .order_by("username")
        )
        combined_author_results: list[dict] = []
        seen_usernames: set[str] = set()

        for author in authors_qs:
            serialized = _serialize_search_author_result(request, author)
            normalized_username = str(serialized.get("username") or "").strip().lower()
            if not normalized_username or normalized_username in seen_usernames:
                continue
            seen_usernames.add(normalized_username)
            combined_author_results.append(serialized)

        if type_filter in ("all", "users"):
            users_qs = (
                User.objects.filter(is_active=True)
                .filter(
                    Q(username__icontains=query)
                    | Q(first_name__icontains=query)
                    | Q(last_name__icontains=query)
                    | Q(site_profile__display_name__icontains=query)
                )
                .select_related("site_profile", "telegram_account", "vk_account")
                .order_by("username")
                .distinct()
            )
            for user in users_qs:
                normalized_username = (user.username or "").strip().lower()
                if not normalized_username or normalized_username in seen_usernames:
                    continue
                seen_usernames.add(normalized_username)
                combined_author_results.append(
                    _serialize_search_site_user_result(request, user)
                )

        combined_author_results.sort(
            key=lambda item: _search_author_result_rank(item, query)
        )
        total_authors = len(combined_author_results)
        authors.extend(combined_author_results[offset : offset + limit])

    return JsonResponse(
        {
            "ok": True,
            "query": query,
            "page": page,
            "limit": limit,
            "posts": posts,
            "authors": authors,
            "total_posts": total_posts,
            "total_authors": total_authors,
        }
    )


SITEMAP_PAGE_SIZE = 5000


def _sitemap_urlset(entries: list[tuple[str, str | None]]) -> HttpResponse:
    urls = []
    for loc, lastmod in entries:
        entry = f"<url><loc>{xml_escape(loc)}</loc>"
        if lastmod:
            entry += f"<lastmod>{xml_escape(lastmod)}</lastmod>"
        entry += "</url>"
        urls.append(entry)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(urls)
        + "</urlset>"
    )
    return HttpResponse(body, content_type="application/xml")


def _sitemap_index(entries: list[tuple[str, str | None]]) -> HttpResponse:
    items = []
    for loc, lastmod in entries:
        entry = f"<sitemap><loc>{xml_escape(loc)}</loc>"
        if lastmod:
            entry += f"<lastmod>{xml_escape(lastmod)}</lastmod>"
        entry += "</sitemap>"
        items.append(entry)
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(items)
        + "</sitemapindex>"
    )
    return HttpResponse(body, content_type="application/xml")


def sitemap_xml(request: HttpRequest) -> HttpResponse:
    base_url = _sitemap_base_url(request)
    now = timezone.now()

    def full(path: str) -> str:
        return f"{base_url}{path}"

    authors_lastmod = Author.objects.order_by("-updated_at").values_list("updated_at", flat=True).first()
    posts_lastmod = (
        Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
        .filter(_publish_ready_filter(now))
        .order_by("-updated_at")
        .values_list("updated_at", flat=True)
        .first()
    )
    posts_count = (
        Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
        .filter(_publish_ready_filter(now))
        .count()
    )
    pages = max(1, ceil(posts_count / SITEMAP_PAGE_SIZE))

    entries: list[tuple[str, str | None]] = [
        (full("/sitemap-static.xml"), None),
        (full("/sitemap-authors.xml"), _format_lastmod(authors_lastmod) if authors_lastmod else None),
    ]

    for page in range(1, pages + 1):
        entries.append(
            (
                full(f"/sitemap-posts-{page}.xml"),
                _format_lastmod(posts_lastmod) if posts_lastmod else None,
            )
        )

    return _sitemap_index(entries)


def sitemap_static_xml(request: HttpRequest) -> HttpResponse:
    base_url = _sitemap_base_url(request)
    static_paths = [
        "/",
        "/authors",
        "/about",
        "/advertisement",
        "/privacy",
        "/rules",
    ]
    entries = [(f"{base_url}{path}", None) for path in static_paths]
    return _sitemap_urlset(entries)


def sitemap_authors_xml(request: HttpRequest) -> HttpResponse:
    base_url = _sitemap_base_url(request)
    authors = Author.objects.filter(is_blocked=False).order_by("username")
    entries = [
        (f"{base_url}/{author.username}", _format_lastmod(author.updated_at))
        for author in authors
    ]
    return _sitemap_urlset(entries)


def sitemap_posts_xml(request: HttpRequest, page: int) -> HttpResponse:
    if page < 1:
        return HttpResponse(status=404)

    base_url = _sitemap_base_url(request)
    now = timezone.now()
    qs = (
        Post.objects.filter(is_blocked=False, is_pending=False, author__is_blocked=False)
        .filter(_publish_ready_filter(now))
    )
    total = qs.count()
    total_pages = max(1, ceil(total / SITEMAP_PAGE_SIZE))
    if page > total_pages:
        return HttpResponse(status=404)

    offset = (page - 1) * SITEMAP_PAGE_SIZE
    posts = (
        qs.only("id", "title", "updated_at", "created_at")
        .order_by("-updated_at", "-id")[offset : offset + SITEMAP_PAGE_SIZE]
    )

    entries = []
    for post in posts:
        lastmod = _format_lastmod(post.updated_at or post.created_at)
        slug = _slugify_title(post.title)
        path = f"/b/post/{post.id}-{slug}" if slug else f"/b/post/{post.id}"
        entries.append((f"{base_url}{path}", lastmod))

    return _sitemap_urlset(entries)

from telegram_integration import bot as telegram_bot
from users import serializers as user_serializers
from users import service as user_service
from users import views as user_views

_normalize_comun_category_name = community_service._normalize_comun_category_name
_generate_unique_comun_category_slug = community_service._generate_unique_comun_category_slug
_ensure_comun_category_by_name = community_service._ensure_comun_category_by_name
_normalize_comun_glossary_term = community_service._normalize_comun_glossary_term
_normalize_comun_glossary_definition = community_service._normalize_comun_glossary_definition
_generate_unique_comun_glossary_term_slug = community_service._generate_unique_comun_glossary_term_slug
_comun_glossary_queryset = community_service._comun_glossary_queryset
_active_comun_glossary_queryset = community_service._active_comun_glossary_queryset
_normalize_telegram_channel_username = community_service._normalize_telegram_channel_username
_generate_unique_comun_name = community_service._generate_unique_comun_name
_normalize_comun_slug = community_service._normalize_comun_slug
_generate_unique_comun_slug = community_service._generate_unique_comun_slug
_comun_is_moderator = community_service._comun_is_moderator
_comun_can_manage_moderators = community_service._comun_can_manage_moderators
_serialize_author_source_summary = community_serializers._serialize_author_source_summary
_current_user_verified_telegram_authors = community_service._current_user_verified_telegram_authors
_comun_team_user_ids = community_service._comun_team_user_ids
_author_is_managed_by_comun_team = community_service._author_is_managed_by_comun_team
_author_telegram_source_comun = community_service._author_telegram_source_comun
_attach_pending_comuns_for_author = community_service._attach_pending_comuns_for_author
_comun_creation_access_state = community_service._comun_creation_access_state
_normalize_comun_minimum_author_rating = community_service._normalize_comun_minimum_author_rating
_comun_minimum_author_rating_value = community_service._comun_minimum_author_rating_value
_comun_post_access_state = community_service._comun_post_access_state
_comun_post_access_error_message = community_service._comun_post_access_error_message
_comun_logo_url = community_service._comun_logo_url
_serialize_comun_profile_card = community_serializers._serialize_comun_profile_card
_serialize_comun_category = community_serializers._serialize_comun_category
_comun_categories_list = community_service._comun_categories_list
_comun_categories_count = community_service._comun_categories_count
_recalculate_comun_rating = community_service._recalculate_comun_rating
_serialize_comun_rating = community_serializers._serialize_comun_rating
_serialize_comun = community_serializers._serialize_comun
_comun_source_filter = community_service._comun_source_filter
_is_internal_comuna_url = community_service._is_internal_comuna_url
_text_contains_external_links = community_service._text_contains_external_links
_payload_contains_external_links = community_service._payload_contains_external_links
_site_user_avatar_url = community_service._site_user_avatar_url
_comun_posts_base_queryset = community_service._comun_posts_base_queryset
_serialize_comun_activity = community_serializers._serialize_comun_activity
_parse_post_reference_to_id = community_service._parse_post_reference_to_id
_serialize_comun_glossary_term = community_serializers._serialize_comun_glossary_term
_sync_comun_glossary_terms = community_service._sync_comun_glossary_terms
_comun_category_queryset = community_service._comun_category_queryset
_active_comun_category_queryset = community_service._active_comun_category_queryset
_post_comun_slug = community_service._post_comun_slug
comun_create_from_telegram_channel = community_views.comun_create_from_telegram_channel
comuns_list_create = community_views.comuns_list_create
comun_detail_manage = community_views.comun_detail_manage
comun_vote = community_views.comun_vote
comun_posts = community_views.comun_posts
comun_post_category_update = community_views.comun_post_category_update

_issue_token = user_service._issue_token
_get_user_from_token = user_service._get_user_from_token
_get_user_from_request = user_service._get_user_from_request
_serialize_user = user_serializers._serialize_user
_public_user_author_ids = user_service._public_user_author_ids
_serialize_public_site_user_profile = user_serializers._serialize_public_site_user_profile
_serialize_public_site_user_author_card = user_serializers._serialize_public_site_user_author_card
_generate_verification_code = user_service._generate_verification_code
register_user = user_views.register_user
login_user = user_views.login_user
auth_me = user_views.auth_me
public_user_profile = user_views.public_user_profile
author_verification_code = user_views.author_verification_code
vk_auth = user_views.vk_auth
