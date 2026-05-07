from __future__ import annotations

import base64
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db.models import Q
from django.http import HttpRequest
from django.utils import timezone

from communities import serializers as community_serializers
from communities import service as community_service
from communities.models import Comun
from feeds.models import Author, Post
from telegram_integration import service as telegram_service
from users.models import (
    AuthorAdmin,
    AuthorVerificationCode,
    SiteUserProfile,
    TelegramAccount,
    VkAccount,
)

User = get_user_model()

_TOKEN_SIGNER = TimestampSigner(salt="comuna-auth")
_TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def _fv():
    from feeds import views as feeds_views

    return feeds_views


def _issue_token(user: User) -> str:
    return _TOKEN_SIGNER.sign(str(user.id))


def _get_user_from_token(token: str) -> User | None:
    try:
        unsigned = _TOKEN_SIGNER.unsign(token, max_age=_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return User.objects.get(id=int(unsigned))
    except (User.DoesNotExist, ValueError, TypeError):
        return None


def _get_user_from_request(request: HttpRequest) -> User | None:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
    elif auth.lower().startswith("token "):
        token = auth.split(" ", 1)[1].strip()
    else:
        token = ""
    if not token:
        return None
    return _get_user_from_token(token)


def _register_password_user(username: str, password: str, email: str = "") -> User:
    if not getattr(settings, "ALLOW_PASSWORD_REGISTRATION", False):
        raise ValueError("Регистрация по почте отключена. Используйте Telegram.")
    if not username or not password:
        raise ValueError("username and password are required")
    if len(password) < 8:
        raise ValueError("пароль слишком короткий")
    if User.objects.filter(username__iexact=username).exists():
        raise ValueError("username already exists")
    if email and User.objects.filter(email__iexact=email).exists():
        raise ValueError("email already exists")
    return User.objects.create_user(username=username, email=email or None, password=password)


def _authenticate_password_user(username_or_email: str, password: str) -> User:
    if not username_or_email or not password:
        raise ValueError("Введите email или имя пользователя и пароль.")

    user = None
    if "@" in username_or_email:
        user = User.objects.filter(email__iexact=username_or_email).first()
        if user and not user.check_password(password):
            user = None
    else:
        user = authenticate(username=username_or_email, password=password)

    if not user:
        raise ValueError(
            "Неверный логин, email или пароль. Проверьте данные и попробуйте снова."
        )
    return user


def _update_site_profile(
    user: User,
    *,
    display_name: object = None,
    avatar_url: object = None,
) -> User:
    if display_name is None and avatar_url is None:
        raise ValueError("nothing to update")

    profile, _ = SiteUserProfile.objects.get_or_create(user=user)

    if display_name is not None:
        next_display_name = str(display_name or "").strip()
        if len(next_display_name) > 120:
            raise ValueError("display_name too long")
        profile.display_name = next_display_name

    if avatar_url is not None:
        next_avatar_url = str(avatar_url or "").strip()
        if next_avatar_url and not re.match(r"^https?://", next_avatar_url):
            raise ValueError("invalid avatar_url")
        if len(next_avatar_url) > 500:
            raise ValueError("avatar_url too long")
        profile.avatar_url = next_avatar_url

    profile.save()
    return user


def _generate_unique_username(base: str, suffix: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]", "_", base).strip("_")
    if not base:
        base = "user"
    candidate = base
    if User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base}_{suffix}"
    if User.objects.filter(username__iexact=candidate).exists():
        candidate = f"tg_{suffix}"
    return candidate[:150]


def _public_user_author_ids(user: User) -> tuple[list[int], list[AuthorAdmin]]:
    author_links = list(
        AuthorAdmin.objects.filter(user=user, verified_at__isnull=False)
        .select_related("author")
        .order_by("author__username")
    )
    author_ids = [link.author_id for link in author_links]
    personal_author = Author.objects.filter(
        username__iexact=(user.username or "").strip(),
        channel_url="",
        channel_id__isnull=True,
    ).first()
    if personal_author and personal_author.id not in author_ids:
        author_ids.append(personal_author.id)
    return author_ids, author_links


def _build_public_user_profile_payload(
    request: HttpRequest,
    profile_user: User,
    *,
    current_user: User | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict:
    from users import serializers as user_serializers
    from my_feed import service as my_feed_service

    now = timezone.now()
    author_ids, author_links = _public_user_author_ids(profile_user)
    visible_author_links = [
        link
        for link in author_links
        if getattr(link, "author", None) is not None
        and not (
            (linked_comun := community_service._author_telegram_source_comun(link.author))
            and linked_comun.is_active
        )
    ]

    public_posts_qs = Post.objects.none()
    if author_ids:
        public_posts_qs = (
            Post.objects.filter(
                author_id__in=author_ids,
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .filter(_fv()._publish_ready_filter(now))
            .filter(Q(author__shadow_banned=False) | Q(author__force_home=True))
            .select_related("author")
            .prefetch_related("tags")
            .order_by("-created_at")
        )
    total_posts = public_posts_qs.count() if author_ids else 0
    posts = list(public_posts_qs[offset : offset + limit]) if author_ids else []
    favorite_post_ids = _fv()._favorite_post_ids_for_user(posts, current_user)

    managed_comuns = list(
        Comun.objects.filter(Q(creator_id=profile_user.id) | Q(moderators__id=profile_user.id), is_active=True)
        .select_related("creator", "telegram_source_author")
        .prefetch_related("moderators", "categories")
        .distinct()
        .order_by("sort_order", "name")
    )
    comun_cards: list[dict] = []
    seen_comun_ids: set[int] = set()

    for comun in managed_comuns:
        role = "creator" if comun.creator_id == profile_user.id else "moderator"
        seen_comun_ids.add(comun.id)
        comun_cards.append(
            community_serializers._serialize_comun_profile_card(
                request,
                comun,
                current_user=current_user,
                role=role,
            )
        )

    subscribed_comun_slugs: list[str] = []
    feed_settings = getattr(profile_user, "feed_settings", None)
    if feed_settings is not None:
        subscribed_comun_slugs = (
            my_feed_service._serialize_user_feed_settings(feed_settings).get("my_feed_comuns", []) or []
        )

    if subscribed_comun_slugs:
        subscribed_comuns = list(
            Comun.objects.filter(slug__in=subscribed_comun_slugs, is_active=True)
            .select_related("creator", "telegram_source_author")
            .prefetch_related("moderators", "categories")
            .order_by("sort_order", "name")
        )
        for comun in subscribed_comuns:
            if comun.id in seen_comun_ids:
                continue
            seen_comun_ids.add(comun.id)
            comun_cards.append(
                community_serializers._serialize_comun_profile_card(
                    request,
                    comun,
                    current_user=current_user,
                    role="subscriber",
                )
            )

    total_comuns = len(comun_cards)

    author_cards = [
        user_serializers._serialize_public_site_user_author_card(request, link)
        for link in visible_author_links
    ]
    posts_payload = [
        _fv()._serialize_backend_post_card(
            request,
            post,
            current_user,
            now=now,
            is_favorite=post.id in favorite_post_ids,
        )
        for post in posts
    ]

    return {
        "ok": True,
        "user": user_serializers._serialize_public_site_user_profile(
            request,
            profile_user,
            author_links=visible_author_links,
            posts_count=total_posts,
            comuns_count=total_comuns,
        ),
        "authors": author_cards,
        "comuns": comun_cards,
        "posts": posts_payload,
        "total_posts": total_posts,
    }


def _generate_verification_code() -> str:
    token = secrets.token_urlsafe(6).replace("_", "").replace("-", "").upper()
    return f"COMUNA-{token}"


def _issue_author_verification_code(user: User) -> str:
    active = (
        AuthorVerificationCode.objects.filter(user=user, used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if active and active.created_at >= timezone.now() - timedelta(days=1):
        return active.code

    code = _generate_verification_code()
    while AuthorVerificationCode.objects.filter(code=code).exists():
        code = _generate_verification_code()

    AuthorVerificationCode.objects.create(user=user, code=code)
    return code


def _authenticate_vk_payload(payload: dict) -> dict:
    access_token = (payload.get("access_token") or "").strip()
    id_token = (payload.get("id_token") or "").strip()
    user_id_hint = payload.get("user_id")
    vk_user = None

    if access_token:
        response = _fetch_vk_json(
            "users.get",
            {
                "access_token": access_token,
                "v": "5.131",
                "fields": "photo_200,screen_name",
            },
        )
        if response and "response" in response:
            users = response.get("response") or []
            if users:
                vk_user = {
                    "vk_id": users[0].get("id"),
                    "screen_name": (users[0].get("screen_name") or "").strip(),
                    "first_name": (users[0].get("first_name") or "").strip(),
                    "last_name": (users[0].get("last_name") or "").strip(),
                    "avatar_url": (users[0].get("photo_200") or "").strip(),
                }

    if not vk_user and id_token:
        vk_user = _parse_vk_id_token(id_token, user_id_hint=user_id_hint)

    if not vk_user:
        raise ValueError("vk auth failed")
    return vk_user


def _upsert_vk_account(vk_user: dict) -> User:
    try:
        vk_id = int(vk_user.get("vk_id"))
    except (TypeError, ValueError):
        raise ValueError("invalid vk id") from None

    screen_name = (vk_user.get("screen_name") or "").strip()
    first_name = (vk_user.get("first_name") or "").strip()
    last_name = (vk_user.get("last_name") or "").strip()
    avatar_url = (vk_user.get("avatar_url") or "").strip()

    account = VkAccount.objects.select_related("user").filter(vk_id=vk_id).first()
    if account:
        user = account.user
    else:
        base_username = screen_name or first_name or "vk"
        candidate = _generate_unique_username(base_username, str(vk_id))
        user = User.objects.create_user(username=candidate)
        user.set_unusable_password()
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save(update_fields=["password", "first_name", "last_name"])
        account = VkAccount.objects.create(
            user=user,
            vk_id=vk_id,
            username=screen_name,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
        )

    account.username = screen_name
    account.first_name = first_name
    account.last_name = last_name
    account.avatar_url = avatar_url
    account.save(update_fields=["username", "first_name", "last_name", "avatar_url", "updated_at"])
    return user


def _fetch_vk_json(method: str, payload: dict) -> dict | None:
    url = f"https://api.vk.com/method/{method}"
    data = urllib.parse.urlencode(payload)
    try:
        with urllib.request.urlopen(f"{url}?{data}", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def _decode_jwt_payload(token: str) -> dict | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        return json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None


def _parse_vk_id_token(id_token: str, user_id_hint: int | None = None) -> dict | None:
    payload = _decode_jwt_payload(id_token)
    if not payload:
        return None

    exp = payload.get("exp")
    if isinstance(exp, (int, float)) and exp < timezone.now().timestamp():
        return None

    aud = payload.get("aud")
    vk_app_id = os.environ.get("VK_APP_ID")
    if vk_app_id and aud and str(aud) != str(vk_app_id):
        return None

    sub = payload.get("sub") or payload.get("user_id") or user_id_hint
    try:
        vk_id = int(sub)
    except (TypeError, ValueError):
        return None

    screen_name = (payload.get("preferred_username") or payload.get("screen_name") or "").strip()
    full_name = (payload.get("name") or "").strip()
    first_name = (payload.get("given_name") or "").strip()
    last_name = (payload.get("family_name") or "").strip()
    if not first_name and full_name:
        parts = full_name.split(" ", 1)
        first_name = parts[0]
        if len(parts) > 1:
            last_name = parts[1]
    avatar_url = (payload.get("picture") or payload.get("avatar") or "").strip()

    return {
        "vk_id": vk_id,
        "screen_name": screen_name,
        "first_name": first_name,
        "last_name": last_name,
        "avatar_url": avatar_url,
    }


_validate_telegram_login = telegram_service.validate_telegram_login
_upsert_telegram_account = telegram_service.upsert_telegram_account
_build_telegram_login_redirect_html = telegram_service.build_telegram_login_redirect_html


__all__ = [
    "_authenticate_password_user",
    "_authenticate_vk_payload",
    "_build_public_user_profile_payload",
    "_build_telegram_login_redirect_html",
    "_fetch_vk_json",
    "_generate_verification_code",
    "_generate_unique_username",
    "_get_user_from_request",
    "_get_user_from_token",
    "_issue_author_verification_code",
    "_issue_token",
    "_parse_vk_id_token",
    "_public_user_author_ids",
    "_register_password_user",
    "_update_site_profile",
    "_upsert_telegram_account",
    "_upsert_vk_account",
    "_validate_telegram_login",
]
