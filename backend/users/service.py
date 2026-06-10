from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from datetime import timedelta

import jwt
from django.apps import apps
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.http import HttpRequest, HttpResponse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils import timezone
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from communities import serializers as community_serializers
from communities import service as community_service
from communities.models import Comun
from feeds.models import Author, Post
from post.service import send_email
from telegram_integration import service as telegram_service
from telegram_integration.media import is_private_telegram_file_url
from users.models import (
    AuthorAdmin,
    AuthorVerificationCode,
    SiteAuthToken,
    SiteChat,
    SiteUserProfile,
    TelegramAccount,
    VkAccount,
)

User = get_user_model()
logger = logging.getLogger(__name__)

_TOKEN_MAX_AGE = int(getattr(settings, "SITE_AUTH_TOKEN_MAX_AGE_SECONDS", 60 * 60 * 24 * 30))
_AUTH_COOKIE_NAME = str(getattr(settings, "SITE_AUTH_COOKIE_NAME", "comuna_site_token") or "comuna_site_token")
_COOKIE_AUTH_SENTINEL = "__cookie__"
_VK_JWKS_CLIENTS: dict[str, PyJWKClient] = {}
DELETED_USER_DISPLAY_NAME = "Удаленный пользователь"


def _fv():
    from feeds import views as feeds_views

    return feeds_views


def _hash_auth_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _auth_cookie_secure() -> bool:
    return bool(getattr(settings, "SITE_AUTH_COOKIE_SECURE", not getattr(settings, "DEBUG", False)))


def _auth_cookie_domain() -> str | None:
    return str(getattr(settings, "SITE_AUTH_COOKIE_DOMAIN", "") or "").strip() or None


def _auth_cookie_samesite() -> str:
    value = str(getattr(settings, "SITE_AUTH_COOKIE_SAMESITE", "Lax") or "Lax").strip()
    return value if value in {"Lax", "Strict", "None"} else "Lax"


def _request_ip(request: HttpRequest | None) -> str | None:
    if request is None:
        return None
    forwarded_for = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",", 1)[0].strip()
    return forwarded_for or request.META.get("REMOTE_ADDR") or None


def _issue_token(user: User, request: HttpRequest | None = None) -> str:
    token = secrets.token_urlsafe(48)
    SiteAuthToken.objects.create(
        user=user,
        token_hash=_hash_auth_token(token),
        expires_at=timezone.now() + timedelta(seconds=_TOKEN_MAX_AGE),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request is not None else ""),
        ip_address=_request_ip(request),
    )
    return token


def _get_user_from_token(token: str) -> User | None:
    token = (token or "").strip()
    if not token or token == _COOKIE_AUTH_SENTINEL:
        return None
    auth_token = (
        SiteAuthToken.objects.select_related("user")
        .filter(
            token_hash=_hash_auth_token(token),
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
            user__is_active=True,
        )
        .first()
    )
    if not auth_token:
        return None
    if not auth_token.last_used_at or auth_token.last_used_at < timezone.now() - timedelta(minutes=5):
        auth_token.last_used_at = timezone.now()
        auth_token.save(update_fields=["last_used_at"])
    return auth_token.user


def _get_auth_tokens_from_request(request: HttpRequest) -> list[str]:
    auth = request.headers.get("Authorization", "")
    tokens: list[str] = []
    if auth.lower().startswith("bearer "):
        tokens.append(auth.split(" ", 1)[1].strip())
    elif auth.lower().startswith("token "):
        tokens.append(auth.split(" ", 1)[1].strip())
    cookie_token = (request.COOKIES.get(_AUTH_COOKIE_NAME) or "").strip()
    if cookie_token and cookie_token not in tokens:
        tokens.append(cookie_token)
    return [token for token in tokens if token]


def _get_auth_token_from_request(request: HttpRequest) -> str:
    tokens = _get_auth_tokens_from_request(request)
    return tokens[0] if tokens else ""


def _get_user_from_request(request: HttpRequest) -> User | None:
    for token in _get_auth_tokens_from_request(request):
        user = _get_user_from_token(token)
        if user:
            return user
    return None


def _revoke_token(token: str) -> None:
    token = (token or "").strip()
    if not token or token == _COOKIE_AUTH_SENTINEL:
        return
    SiteAuthToken.objects.filter(
        token_hash=_hash_auth_token(token),
        revoked_at__isnull=True,
    ).update(revoked_at=timezone.now())


def _revoke_request_tokens(request: HttpRequest) -> None:
    for token in _get_auth_tokens_from_request(request):
        _revoke_token(token)


def _set_auth_cookie(response: HttpResponse, token: str) -> None:
    response.set_cookie(
        _AUTH_COOKIE_NAME,
        token,
        max_age=_TOKEN_MAX_AGE,
        path="/",
        domain=_auth_cookie_domain(),
        secure=_auth_cookie_secure(),
        httponly=True,
        samesite=_auth_cookie_samesite(),
    )


def _clear_auth_cookie(response: HttpResponse) -> None:
    response.delete_cookie(
        _AUTH_COOKIE_NAME,
        path="/",
        domain=_auth_cookie_domain(),
        samesite=_auth_cookie_samesite(),
    )


def _is_deleted_site_user(user: User | None) -> bool:
    if not user:
        return False
    try:
        profile = user.site_profile
    except Exception:
        profile = None
    return bool(not user.is_active or getattr(profile, "deleted_at", None))


def _deleted_user_public_payload(user_id: int | None = None) -> dict:
    return {
        "id": user_id,
        "username": "deleted",
        "display_name": DELETED_USER_DISPLAY_NAME,
        "avatar_url": None,
        "profile_url": None,
        "is_deleted": True,
    }


def _unique_deleted_username(user: User) -> str:
    base = f"deleted_user_{user.id}"
    candidate = base[:150]
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exclude(pk=user.pk).exists():
        suffix += 1
        candidate = f"{base}_{suffix}"[:150]
    return candidate


def _unique_deleted_author_username(user: User, author: Author) -> str:
    base = f"deleted_user_{user.id}"
    candidate = base[:64]
    suffix = 1
    while Author.objects.filter(username__iexact=candidate).exclude(pk=author.pk).exists():
        suffix += 1
        candidate = f"{base}_{suffix}"[:64]
    return candidate


def _anonymize_personal_author(user: User) -> None:
    personal_author = Author.objects.filter(
        username__iexact=(user.username or "").strip(),
        channel_url="",
        channel_id__isnull=True,
    ).first()
    if not personal_author:
        return
    personal_author.username = _unique_deleted_author_username(user, personal_author)
    personal_author.title = DELETED_USER_DISPLAY_NAME
    personal_author.channel_url = ""
    personal_author.invite_url = ""
    personal_author.avatar_url = ""
    personal_author.avatar_image = ""
    personal_author.avatar_file_id = ""
    personal_author.description = ""
    personal_author.admin_chat_id = None
    personal_author.notify_comments = False
    personal_author.auto_publish = False
    personal_author.save(
        update_fields=[
            "username",
            "title",
            "channel_url",
            "invite_url",
            "avatar_url",
            "avatar_image",
            "avatar_file_id",
            "description",
            "admin_chat_id",
            "notify_comments",
            "auto_publish",
            "updated_at",
        ]
    )


def _delete_optional_user_rows(app_label: str, model_name: str, **filters) -> None:
    try:
        model = _model_class(app_label, model_name)
    except LookupError:
        return
    model.objects.filter(**filters).delete()


def _update_optional_user_rows(
    app_label: str,
    model_name: str,
    filters: dict,
    updates: dict,
) -> None:
    try:
        model = _model_class(app_label, model_name)
    except LookupError:
        return
    model.objects.filter(**filters).update(**updates)


def _delete_site_user_account(user: User) -> None:
    if not user:
        raise ValueError("user not found")
    if user.is_staff:
        raise ValueError("staff account cannot be deleted here")

    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=user.pk)
        if _is_deleted_site_user(user):
            return

        _anonymize_personal_author(user)

        profile, _ = SiteUserProfile.objects.select_for_update().get_or_create(user=user)
        now = timezone.now()
        profile.display_name = ""
        profile.phone = ""
        profile.avatar_url = ""
        profile.email_verified_at = None
        profile.registration_source = ""
        profile.registration_path = ""
        profile.deleted_at = now
        profile.save(
            update_fields=[
                "display_name",
                "phone",
                "avatar_url",
                "email_verified_at",
                "registration_source",
                "registration_path",
                "deleted_at",
                "updated_at",
            ]
        )

        AuthorAdmin.objects.filter(user=user).delete()
        AuthorVerificationCode.objects.filter(user=user).delete()
        TelegramAccount.objects.filter(user=user).delete()
        VkAccount.objects.filter(user=user).delete()
        SiteAuthToken.objects.filter(user=user, revoked_at__isnull=True).update(revoked_at=now)
        SiteChat.objects.filter(Q(user_one=user) | Q(user_two=user)).delete()

        _delete_optional_user_rows("feeds", "UserFeedSettings", user=user)
        _delete_optional_user_rows("feeds", "SiteNotificationPreference", user=user)
        _delete_optional_user_rows("feeds", "SiteNotification", user=user)
        _delete_optional_user_rows("feeds", "MobilePushDevice", user=user)
        _delete_optional_user_rows("feeds", "PostFavorite", user=user)
        _delete_optional_user_rows("feeds", "PostLike", user=user)
        _delete_optional_user_rows("feeds", "PostRead", user=user)
        _delete_optional_user_rows("feeds", "PostCommentLike", user=user)
        _delete_optional_user_rows("feeds", "PostPollVote", user=user)
        _delete_optional_user_rows("feeds", "PostRatingVote", user=user)
        _delete_optional_user_rows("feeds", "ComunVote", user=user)
        _delete_optional_user_rows(
            "special_projects",
            "SpecialProjectLetterSuggestion",
            submitted_by=user,
        )
        _delete_optional_user_rows("special_projects", "PublicBookSubmissionState", user=user)
        _delete_optional_user_rows("special_projects", "PublicBookReminder", user=user)
        _delete_optional_user_rows(
            "special_projects",
            "PublicBookFinalNotificationSubscription",
            user=user,
        )
        _delete_optional_user_rows("special_projects", "PublicBookModerationState", user=user)
        _delete_optional_user_rows("special_projects", "FilmJourneySubscription", user=user)
        _update_optional_user_rows(
            "special_projects",
            "SpecialProjectLetterImage",
            {"created_by": user},
            {"created_by": None},
        )
        _update_optional_user_rows(
            "special_projects",
            "SpecialProjectLetterSuggestion",
            {"reviewed_by": user},
            {"reviewed_by": None},
        )
        _update_optional_user_rows(
            "special_projects",
            "SpecialProjectGeneratedPhrase",
            {"generated_by": user},
            {"generated_by": None},
        )
        _update_optional_user_rows(
            "special_projects",
            "PublicBookProjectSettings",
            {"updated_by": user},
            {"updated_by": None},
        )
        _update_optional_user_rows(
            "special_projects",
            "PublicBookWord",
            {"censored_by": user},
            {"censored_by": None},
        )
        _update_optional_user_rows(
            "special_projects",
            "PublicBookBlockedWord",
            {"created_by": user},
            {"created_by": None},
        )

        for comun in Comun.objects.filter(moderators=user).iterator():
            comun.moderators.remove(user)

        user.username = _unique_deleted_username(user)
        user.email = ""
        user.first_name = ""
        user.last_name = ""
        user.is_active = False
        user.set_unusable_password()
        user.save(
            update_fields=[
                "username",
                "email",
                "first_name",
                "last_name",
                "is_active",
                "password",
            ]
        )


def _register_password_user(username: str, password: str, email: str = "") -> User:
    if not getattr(settings, "ALLOW_PASSWORD_REGISTRATION", False):
        raise ValueError("Регистрация по почте отключена. Используйте Telegram.")
    email = (email or "").strip().lower()
    if not username or not password or not email:
        raise ValueError("username, email and password are required")
    if "@" not in email:
        raise ValueError("Введите корректный email.")
    if len(password) < 8:
        raise ValueError("пароль слишком короткий")
    try:
        validate_password(password)
    except ValidationError as exc:
        raise ValueError(" ".join(exc.messages)) from exc

    existing_by_email = User.objects.filter(email__iexact=email).first()
    if existing_by_email:
        if existing_by_email.has_usable_password():
            raise ValueError("email already exists")
        raise ValueError(
            "Аккаунт с таким email уже существует. Восстановите пароль через подтверждение почты."
        )

    if User.objects.filter(username__iexact=username).exists():
        raise ValueError("username already exists")
    user = User.objects.create_user(username=username, email=email, password=password)
    _mark_email_unverified(user)
    return user


def _site_url(path: str) -> str:
    base_url = str(getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if not base_url:
        base_url = "http://localhost:5173"
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base_url}{path}"


def _mark_email_unverified(user: User) -> SiteUserProfile:
    profile, _ = SiteUserProfile.objects.get_or_create(user=user)
    if profile.email_verified_at is not None:
        profile.email_verified_at = None
        profile.save(update_fields=["email_verified_at", "updated_at"])
    return profile


def _normalize_registration_source(value: str | None) -> str:
    source = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(value or "").strip().lower()).strip("_")
    return source[:80]


def _remember_registration_source(
    user: User,
    source: str | None,
    path: str | None = "",
) -> None:
    normalized_source = _normalize_registration_source(source)
    if not normalized_source:
        return
    normalized_path = str(path or "").strip()[:255]
    profile, _ = SiteUserProfile.objects.get_or_create(user=user)
    update_fields: list[str] = []
    if not profile.registration_source:
        profile.registration_source = normalized_source
        update_fields.append("registration_source")
    if normalized_path and not profile.registration_path:
        profile.registration_path = normalized_path
        update_fields.append("registration_path")
    if update_fields:
        profile.save(update_fields=[*update_fields, "updated_at"])


def _email_verification_secret(user: User) -> str:
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return f"{uid}:{token}"


def _email_verification_url(user: User) -> str:
    return _site_url(f"/verify_email/{_email_verification_secret(user)}")


def _send_registration_email(user: User) -> bool:
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        return False
    username = (getattr(user, "username", "") or "").strip() or "пользователь"
    verification_url = _email_verification_url(user)
    escaped_username = html.escape(username)
    escaped_url = html.escape(verification_url, quote=True)
    try:
        send_email(
            subject="Подтвердите почту в Tambur",
            to=email,
            text=(
                f"Здравствуйте, {username}!\n\n"
                "Чтобы завершить подтверждение почты, откройте секретную ссылку:\n"
                f"{verification_url}\n\n"
                "Ссылка секретная и привязана к вашему аккаунту.\n"
                "Если это были не вы, просто проигнорируйте это письмо."
            ),
            html=(
                f"<p>Здравствуйте, {escaped_username}!</p>"
                "<p>Чтобы завершить подтверждение почты, откройте секретную ссылку:</p>"
                f"<p><a href=\"{escaped_url}\">Подтвердить почту</a></p>"
                "<p>Ссылка секретная и привязана к вашему аккаунту.</p>"
                "<p>Если это были не вы, просто проигнорируйте это письмо.</p>"
            ),
        )
        return True
    except Exception:
        logger.exception("Failed to send registration email to user %s", user.id)
        return False


def _model_class(app_label: str, model_name: str):
    return apps.get_model(app_label, model_name)


def _identity_lookup(obj, fields: tuple[str, ...]) -> dict:
    lookup: dict[str, object] = {}
    for field_name in fields:
        field = obj._meta.get_field(field_name)
        if field.is_relation and hasattr(obj, f"{field_name}_id"):
            lookup[f"{field_name}_id"] = getattr(obj, f"{field_name}_id")
        else:
            lookup[field_name] = getattr(obj, field_name)
    return lookup


def _move_unique_user_rows(
    model,
    source: User,
    target: User,
    *,
    user_field: str = "user",
    identity_fields: tuple[str, ...] = (),
    merge_existing=None,
) -> None:
    source_filter = {f"{user_field}_id": source.id}
    for obj in model.objects.filter(**source_filter).order_by("id").iterator():
        target_lookup = {f"{user_field}_id": target.id, **_identity_lookup(obj, identity_fields)}
        existing = model.objects.filter(**target_lookup).first()
        if existing:
            if merge_existing is not None:
                merge_existing(existing, obj)
            obj.delete()
            continue
        setattr(obj, f"{user_field}_id", target.id)
        obj.save(update_fields=[user_field])


def _merge_site_profiles(target: User, source: User) -> None:
    source_profile = SiteUserProfile.objects.filter(user=source).first()
    if not source_profile:
        return
    target_profile, _ = SiteUserProfile.objects.get_or_create(user=target)
    update_fields: list[str] = []
    if source_profile.display_name and not target_profile.display_name:
        target_profile.display_name = source_profile.display_name
        update_fields.append("display_name")
    if source_profile.avatar_url and not target_profile.avatar_url:
        target_profile.avatar_url = source_profile.avatar_url
        update_fields.append("avatar_url")
    if source_profile.phone and not target_profile.phone:
        target_profile.phone = source_profile.phone
        update_fields.append("phone")
    if source_profile.email_verified_at and (
        target_profile.email_verified_at is None
        or source_profile.email_verified_at < target_profile.email_verified_at
    ):
        target_profile.email_verified_at = source_profile.email_verified_at
        update_fields.append("email_verified_at")
    if source_profile.registration_source and not target_profile.registration_source:
        target_profile.registration_source = source_profile.registration_source
        update_fields.append("registration_source")
    if source_profile.registration_path and not target_profile.registration_path:
        target_profile.registration_path = source_profile.registration_path
        update_fields.append("registration_path")
    if update_fields:
        target_profile.save(update_fields=[*set(update_fields), "updated_at"])
    source_profile.delete()


def _merge_telegram_accounts(target: User, source: User) -> None:
    target_account = TelegramAccount.objects.filter(user=target).first()
    source_account = TelegramAccount.objects.filter(user=source).first()
    if not source_account:
        return
    if not target_account:
        source_account.user = target
        source_account.save(update_fields=["user", "updated_at"])
        return

    update_fields: list[str] = []
    if not target_account.oidc_sub:
        source_oidc_sub = getattr(source_account, "oidc_sub", None) or (
            str(source_account.telegram_id) if source_account.telegram_id != target_account.telegram_id else ""
        )
        if source_oidc_sub and not TelegramAccount.objects.filter(oidc_sub=source_oidc_sub).exclude(pk=target_account.pk).exists():
            target_account.oidc_sub = source_oidc_sub
            update_fields.append("oidc_sub")
    for field in ("username", "first_name", "last_name", "avatar_url"):
        if getattr(source_account, field) and not getattr(target_account, field):
            setattr(target_account, field, getattr(source_account, field))
            update_fields.append(field)
    if update_fields:
        target_account.save(update_fields=[*set(update_fields), "updated_at"])
    source_account.delete()


def _merge_vk_accounts(target: User, source: User) -> None:
    target_account = VkAccount.objects.filter(user=target).first()
    source_account = VkAccount.objects.filter(user=source).first()
    if not source_account:
        return
    if not target_account:
        source_account.user = target
        source_account.save(update_fields=["user", "updated_at"])
        return
    update_fields: list[str] = []
    for field in ("username", "email", "phone", "first_name", "last_name", "avatar_url"):
        if getattr(source_account, field) and not getattr(target_account, field):
            setattr(target_account, field, getattr(source_account, field))
            update_fields.append(field)
    if update_fields:
        target_account.save(update_fields=[*set(update_fields), "updated_at"])
    source_account.delete()


def _merge_feed_settings(target: User, source: User) -> None:
    UserFeedSettings = _model_class("feeds", "UserFeedSettings")
    source_settings = UserFeedSettings.objects.filter(user=source).first()
    if not source_settings:
        return
    target_settings = UserFeedSettings.objects.filter(user=target).first()
    if not target_settings:
        source_settings.user = target
        source_settings.save(update_fields=["user", "updated_at"])
        return
    previous_source_settings = {
        "my_feed_comuns": source_settings.my_feed_comuns or [],
        "my_feed_comun_categories": source_settings.my_feed_comun_categories or {},
    }
    previous_target_settings = {
        "my_feed_comuns": target_settings.my_feed_comuns or [],
        "my_feed_comun_categories": target_settings.my_feed_comun_categories or {},
    }
    for field in ("my_feed_authors", "my_feed_tags", "my_feed_comuns", "hidden_authors"):
        merged = list(dict.fromkeys([*(getattr(target_settings, field) or []), *(getattr(source_settings, field) or [])]))
        setattr(target_settings, field, merged)
    target_settings.my_feed_comun_categories = {
        **(source_settings.my_feed_comun_categories or {}),
        **(target_settings.my_feed_comun_categories or {}),
    }
    target_settings.tag_rules = {
        **(source_settings.tag_rules or {}),
        **(target_settings.tag_rules or {}),
    }
    target_settings.save()
    source_settings.delete()
    next_target_settings = {
        "my_feed_comuns": target_settings.my_feed_comuns or [],
        "my_feed_comun_categories": target_settings.my_feed_comun_categories or {},
    }
    community_service._sync_comun_subscriber_counts(previous_source_settings, {})
    community_service._sync_comun_subscriber_counts(previous_target_settings, next_target_settings)


def _merge_notification_preferences(target: User, source: User) -> None:
    SiteNotificationPreference = _model_class("feeds", "SiteNotificationPreference")

    def merge_pref(existing, duplicate) -> None:
        existing.site_enabled = existing.site_enabled or duplicate.site_enabled
        existing.telegram_enabled = existing.telegram_enabled or duplicate.telegram_enabled
        existing.push_enabled = existing.push_enabled or duplicate.push_enabled
        existing.save(update_fields=["site_enabled", "telegram_enabled", "push_enabled", "updated_at"])

    _move_unique_user_rows(
        SiteNotificationPreference,
        source,
        target,
        identity_fields=("event_key",),
        merge_existing=merge_pref,
    )


def _merge_user_accounts(target: User, source: User, *, reason: str = "") -> User:
    if not target or not source or target.id == source.id:
        return target
    if not target.is_active:
        raise ValueError("target account is inactive")

    with transaction.atomic():
        target = User.objects.select_for_update().get(pk=target.pk)
        source = User.objects.select_for_update().get(pk=source.pk)
        if target.id == source.id:
            return target

        if not target.email and source.email:
            target.email = source.email
        if not target.first_name and source.first_name:
            target.first_name = source.first_name
        if not target.last_name and source.last_name:
            target.last_name = source.last_name
        target.save(update_fields=["email", "first_name", "last_name"])

        _merge_site_profiles(target, source)
        _merge_telegram_accounts(target, source)
        _merge_vk_accounts(target, source)
        _merge_feed_settings(target, source)
        _merge_notification_preferences(target, source)

        _move_unique_user_rows(AuthorAdmin, source, target, identity_fields=("author",))
        AuthorVerificationCode.objects.filter(user=source).update(user=target)
        SiteAuthToken.objects.filter(user=source).update(user=target)

        Comun = _model_class("feeds", "Comun")
        Comun.objects.filter(creator=source).update(creator=target)
        for comun in Comun.objects.filter(moderators=source).iterator():
            comun.moderators.add(target)
            comun.moderators.remove(source)

        ComunVote = _model_class("feeds", "ComunVote")
        _move_unique_user_rows(ComunVote, source, target, identity_fields=("comun",))
        ComunPostCategoryAssignment = _model_class("feeds", "ComunPostCategoryAssignment")
        ComunPostCategoryAssignment.objects.filter(assigned_by=source).update(assigned_by=target)

        PostComment = _model_class("feeds", "PostComment")
        PostComment.objects.filter(user=source).update(user=target)
        _move_unique_user_rows(_model_class("feeds", "PostCommentLike"), source, target, identity_fields=("comment",))
        _move_unique_user_rows(_model_class("feeds", "PostLike"), source, target, identity_fields=("post",))
        _move_unique_user_rows(_model_class("feeds", "PostRead"), source, target, identity_fields=("post",))
        _move_unique_user_rows(_model_class("feeds", "PostFavorite"), source, target, identity_fields=("post",))
        _move_unique_user_rows(_model_class("feeds", "PostPollVote"), source, target, identity_fields=("post",))
        _move_unique_user_rows(
            _model_class("feeds", "PostRatingVote"),
            source,
            target,
            identity_fields=("post", "block_id"),
        )

        _model_class("feeds", "SiteNotification").objects.filter(user=source).update(user=target)
        _model_class("feeds", "MobilePushDevice").objects.filter(user=source).update(user=target)
        _model_class("feeds", "AuthorRatingEvent").objects.filter(actor=source).update(actor=target)

        _model_class("special_projects", "SpecialProjectLetterImage").objects.filter(created_by=source).update(created_by=target)
        _model_class("special_projects", "SpecialProjectLetterSuggestion").objects.filter(submitted_by=source).update(submitted_by=target)
        _model_class("special_projects", "SpecialProjectLetterSuggestion").objects.filter(reviewed_by=source).update(reviewed_by=target)
        _model_class("special_projects", "SpecialProjectGeneratedPhrase").objects.filter(generated_by=source).update(generated_by=target)
        _model_class("special_projects", "PublicBookWord").objects.filter(submitted_by=source).update(submitted_by=target)
        _model_class("special_projects", "PublicBookBlockedWord").objects.filter(created_by=source).update(created_by=target)

        source.email = ""
        source.is_active = False
        source.set_unusable_password()
        source.save(update_fields=["email", "is_active", "password"])

    logger.info("Merged user account %s into %s (%s)", source.id, target.id, reason)
    target.refresh_from_db()
    return target


def _merge_accounts_with_verified_email(user: User) -> User:
    email = _normalize_email(getattr(user, "email", ""))
    if not email:
        return user
    duplicate_ids = list(
        User.objects.filter(email__iexact=email, is_active=True)
        .exclude(pk=user.pk)
        .order_by("id")
        .values_list("id", flat=True)
    )
    for duplicate_id in duplicate_ids:
        duplicate = User.objects.filter(pk=duplicate_id, is_active=True).first()
        if duplicate:
            user = _merge_user_accounts(user, duplicate, reason="verified_email")
    return user


def _verify_email_by_secret(secret: str) -> User:
    value = str(secret or "").strip()
    if ":" not in value:
        raise ValueError("Ссылка подтверждения недействительна или устарела.")
    uid, token = value.split(":", 1)
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, is_active=True)
    except Exception as exc:
        raise ValueError("Ссылка подтверждения недействительна или устарела.") from exc

    if not default_token_generator.check_token(user, token):
        raise ValueError("Ссылка подтверждения недействительна или устарела.")
    if not (getattr(user, "email", "") or "").strip():
        raise ValueError("У аккаунта не указан email.")

    profile, _ = SiteUserProfile.objects.get_or_create(user=user)
    if profile.email_verified_at is None:
        profile.email_verified_at = timezone.now()
        profile.save(update_fields=["email_verified_at", "updated_at"])
    return _merge_accounts_with_verified_email(user)


def _send_password_reset_email(user: User) -> bool:
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        return False

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = _site_url(f"/login_reset?uid={uid}&token={token}")
    username = (getattr(user, "username", "") or "").strip() or "пользователь"
    try:
        send_email(
            subject="Восстановление доступа к Tambur",
            to=email,
            text=(
                f"Здравствуйте, {username}!\n\n"
                "Мы получили запрос на восстановление доступа к аккаунту.\n"
                f"Чтобы задать новый пароль, откройте ссылку: {reset_url}\n\n"
                "Если вы не запрашивали восстановление, просто проигнорируйте это письмо."
            ),
            html=(
                f"<p>Здравствуйте, {username}!</p>"
                "<p>Мы получили запрос на восстановление доступа к аккаунту.</p>"
                f"<p><a href=\"{reset_url}\">Задать новый пароль</a></p>"
                "<p>Если вы не запрашивали восстановление, просто проигнорируйте это письмо.</p>"
            ),
        )
        return True
    except Exception:
        logger.exception("Failed to send password reset email to user %s", user.id)
        return False


def _request_password_reset(email: str) -> bool:
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Введите корректный email.")

    user = (
        User.objects.filter(email__iexact=email, is_active=True)
        .order_by("id")
        .first()
    )
    if not user:
        return False
    return _send_password_reset_email(user)


def _reset_password_by_token(uid: str, token: str, password: str) -> User:
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, is_active=True)
    except Exception as exc:
        raise ValueError("Ссылка восстановления недействительна или устарела.") from exc

    if not default_token_generator.check_token(user, token):
        raise ValueError("Ссылка восстановления недействительна или устарела.")
    if len(password or "") < 8:
        raise ValueError("пароль слишком короткий")
    try:
        validate_password(password, user=user)
    except ValidationError as exc:
        raise ValueError(" ".join(exc.messages)) from exc

    user.set_password(password)
    user.save(update_fields=["password"])
    return user


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
    email: object = None,
) -> tuple[User, bool]:
    if display_name is None and avatar_url is None and email is None:
        raise ValueError("nothing to update")

    profile, _ = SiteUserProfile.objects.get_or_create(user=user)
    email_verification_sent = False

    if display_name is not None:
        next_display_name = str(display_name or "").strip()
        if len(next_display_name) > 120:
            raise ValueError("display_name too long")
        profile.display_name = next_display_name

    if avatar_url is not None:
        next_avatar_url = str(avatar_url or "").strip()
        if next_avatar_url and not re.match(r"^https?://", next_avatar_url):
            raise ValueError("invalid avatar_url")
        if is_private_telegram_file_url(next_avatar_url):
            raise ValueError("invalid avatar_url")
        if len(next_avatar_url) > 500:
            raise ValueError("avatar_url too long")
        if next_avatar_url:
            from users.avatar_media import cache_external_avatar_for_user, public_cached_avatar_url

            cached_avatar_url = public_cached_avatar_url(next_avatar_url)
            if not cached_avatar_url:
                cached_avatar_url = cache_external_avatar_for_user(
                    user,
                    next_avatar_url,
                    source="profile",
                    force=True,
                )
            if not cached_avatar_url:
                raise ValueError("invalid avatar_url")
            next_avatar_url = cached_avatar_url
        profile.avatar_url = next_avatar_url

    if email is not None:
        next_email = _normalize_email(email)
        if next_email:
            try:
                validate_email(next_email)
            except ValidationError as exc:
                raise ValueError("Введите корректный email.") from exc
        current_email = _normalize_email(getattr(user, "email", ""))
        if next_email != current_email:
            user.email = next_email
            user.save(update_fields=["email"])
            profile.email_verified_at = None
        if next_email and profile.email_verified_at is None:
            email_verification_sent = _send_registration_email(user)

    profile.save()
    return user, email_verification_sent


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
    has_local_vk_jwks = bool(str(getattr(settings, "VK_OIDC_JWKS_URL", "") or "").strip())
    verified_id_token_user = (
        _parse_vk_id_token(id_token, user_id_hint=user_id_hint) if id_token and has_local_vk_jwks else None
    )

    if access_token:
        vk_user = _vk_user_from_vk_id_response(
            _fetch_vk_id_json(
                "user_info",
                {
                    "access_token": access_token,
                },
            )
        )
        if vk_user and verified_id_token_user:
            if str(verified_id_token_user.get("vk_id")) != str(vk_user.get("vk_id")):
                raise ValueError("vk auth mismatch")
            vk_user = _merge_vk_user_data(vk_user, verified_id_token_user)

    if not vk_user and access_token:
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
                if (
                    verified_id_token_user
                    and str(verified_id_token_user.get("vk_id")) == str(vk_user.get("vk_id"))
                ):
                    vk_user.update(
                        {
                            "email": verified_id_token_user.get("email") or "",
                            "phone": verified_id_token_user.get("phone") or "",
                        }
                    )

    if not vk_user and id_token and not verified_id_token_user:
        vk_user = _vk_user_from_vk_id_response(
            _fetch_vk_id_json(
                "public_info",
                {
                    "id_token": id_token,
                },
            )
        )

    if not vk_user and verified_id_token_user:
        vk_user = verified_id_token_user

    if not vk_user:
        raise ValueError("vk auth failed")
    vk_user["email"] = _normalize_email(vk_user.get("email"))
    vk_user["phone"] = _normalize_phone(vk_user.get("phone"))
    return vk_user


def _normalize_email(value: object) -> str:
    email = str(value or "").strip().lower()
    if not email or "@" not in email:
        return ""
    return email


def _normalize_phone(value: object) -> str:
    phone = re.sub(r"\D+", "", str(value or ""))
    if len(phone) < 7:
        return ""
    return f"+{phone}" if not str(value or "").strip().startswith("+") else f"+{phone}"


def _merge_vk_user_data(primary: dict, fallback: dict) -> dict:
    merged = dict(primary)
    for key in ("screen_name", "email", "phone", "first_name", "last_name", "avatar_url"):
        if not (merged.get(key) or "") and fallback.get(key):
            merged[key] = fallback[key]
    return merged


def _vk_user_from_vk_id_response(response: dict | None) -> dict | None:
    if not isinstance(response, dict):
        return None
    raw_user = response.get("user")
    if not isinstance(raw_user, dict):
        raw_user = response.get("response") if isinstance(response.get("response"), dict) else response
    if not isinstance(raw_user, dict):
        return None

    raw_vk_id = raw_user.get("user_id") or raw_user.get("id") or raw_user.get("uid") or raw_user.get("sub")
    try:
        vk_id = int(raw_vk_id)
    except (TypeError, ValueError):
        return None

    return {
        "vk_id": vk_id,
        "screen_name": (raw_user.get("screen_name") or raw_user.get("preferred_username") or "").strip(),
        "email": _normalize_email(raw_user.get("email")),
        "phone": _normalize_phone(raw_user.get("phone") or raw_user.get("phone_number")),
        "first_name": (raw_user.get("first_name") or raw_user.get("given_name") or "").strip(),
        "last_name": (raw_user.get("last_name") or raw_user.get("family_name") or "").strip(),
        "avatar_url": (raw_user.get("avatar") or raw_user.get("picture") or raw_user.get("photo_200") or "").strip(),
    }


def _find_user_by_verified_contact(*, email: str = "", phone: str = "") -> User | None:
    email = _normalize_email(email)
    phone = _normalize_phone(phone)
    if email:
        user = User.objects.filter(email__iexact=email).order_by("id").first()
        if user:
            return user
    if phone:
        profile = SiteUserProfile.objects.select_related("user").filter(phone=phone).order_by("id").first()
        if profile:
            return profile.user
    return None


def _upsert_vk_account(vk_user: dict, link_user: User | None = None) -> User:
    try:
        vk_id = int(vk_user.get("vk_id"))
    except (TypeError, ValueError):
        raise ValueError("invalid vk id") from None

    screen_name = (vk_user.get("screen_name") or "").strip()
    email = _normalize_email(vk_user.get("email"))
    phone = _normalize_phone(vk_user.get("phone"))
    first_name = (vk_user.get("first_name") or "").strip()
    last_name = (vk_user.get("last_name") or "").strip()
    avatar_url = (vk_user.get("avatar_url") or "").strip()

    account = VkAccount.objects.select_related("user").filter(vk_id=vk_id).first()
    if account:
        user = account.user
        if link_user and account.user_id != link_user.id:
            user = _merge_user_accounts(link_user, account.user, reason="vk_link")
            account = VkAccount.objects.filter(vk_id=vk_id).first() or VkAccount.objects.filter(user=user).first()
    else:
        user = link_user or _find_user_by_verified_contact(email=email, phone=phone)
        if link_user:
            contact_user = _find_user_by_verified_contact(email=email, phone=phone)
            if contact_user and contact_user.id != link_user.id:
                user = _merge_user_accounts(link_user, contact_user, reason="vk_contact_link")
        existing_user_account = VkAccount.objects.filter(user=user).first() if user else None
        if existing_user_account:
            if existing_user_account.vk_id != vk_id:
                raise ValueError("К этому профилю уже привязан другой VK.")
            account = existing_user_account
        if user:
            updates: list[str] = []
            if email and not (user.email or "").strip():
                user.email = email
                updates.append("email")
            if first_name and not user.first_name:
                user.first_name = first_name
                updates.append("first_name")
            if last_name and not user.last_name:
                user.last_name = last_name
                updates.append("last_name")
            if email and "email" not in updates and (user.email or "").strip().lower() != email:
                user.email = email
                updates.append("email")
            if updates:
                user.save(update_fields=updates)
        else:
            base_username = screen_name or first_name or "vk"
            candidate = _generate_unique_username(base_username, str(vk_id))
            user = User.objects.create_user(username=candidate, email=email or None)
            user.set_unusable_password()
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.save(update_fields=["password", "first_name", "last_name", "email"])
        if phone:
            profile, _ = SiteUserProfile.objects.get_or_create(user=user)
            if not profile.phone:
                profile.phone = phone
                profile.save(update_fields=["phone", "updated_at"])
        if account is None:
            account = VkAccount.objects.create(
                user=user,
                vk_id=vk_id,
                username=screen_name,
                email=email,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                avatar_url=avatar_url,
            )

    account.username = screen_name
    if email:
        account.email = email
    if phone:
        account.phone = phone
    account.first_name = first_name
    account.last_name = last_name
    account.avatar_url = avatar_url
    account.save(update_fields=["username", "email", "phone", "first_name", "last_name", "avatar_url", "updated_at"])
    if avatar_url:
        from users.avatar_media import cache_external_avatar_for_user

        cache_external_avatar_for_user(user, avatar_url, source="vk")
    return user


def _vk_login_will_create_new_user(vk_user: dict) -> bool:
    try:
        vk_id = int(vk_user.get("vk_id"))
    except (TypeError, ValueError):
        return True
    if VkAccount.objects.filter(vk_id=vk_id).exists():
        return False
    return _find_user_by_verified_contact(
        email=str(vk_user.get("email") or ""),
        phone=str(vk_user.get("phone") or ""),
    ) is None


def _fetch_vk_json(method: str, payload: dict) -> dict | None:
    url = f"https://api.vk.com/method/{method}"
    data = urllib.parse.urlencode(payload)
    try:
        with urllib.request.urlopen(f"{url}?{data}", timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def _fetch_vk_id_json(endpoint: str, payload: dict) -> dict | None:
    vk_app_id = str(getattr(settings, "VK_APP_ID", "") or os.environ.get("VK_APP_ID", "")).strip()
    if not vk_app_id:
        logger.warning("VK ID request skipped: VK_APP_ID is not configured")
        return None

    endpoint = endpoint.strip().lstrip("/")
    if endpoint not in {"user_info", "public_info"}:
        return None

    query = urllib.parse.urlencode({"client_id": vk_app_id})
    data = urllib.parse.urlencode(payload).encode("utf-8")
    request = urllib.request.Request(
        f"https://id.vk.ru/oauth2/{endpoint}?{query}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    if isinstance(parsed, dict) and "error" in parsed:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_vk_id_token(id_token: str, user_id_hint: int | None = None) -> dict | None:
    vk_app_id = str(getattr(settings, "VK_APP_ID", "") or os.environ.get("VK_APP_ID", "")).strip()
    jwks_url = str(getattr(settings, "VK_OIDC_JWKS_URL", "") or "").strip()
    issuer = str(getattr(settings, "VK_OIDC_ISSUER", "") or "").strip()
    if not vk_app_id or not jwks_url:
        logger.warning("VK id_token rejected: VK_APP_ID or VK_OIDC_JWKS_URL is not configured")
        return None

    try:
        jwks_client = _VK_JWKS_CLIENTS.setdefault(jwks_url, PyJWKClient(jwks_url, timeout=5))
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        decode_kwargs: dict[str, object] = {
            "audience": vk_app_id,
            "algorithms": ["RS256", "ES256"],
            "options": {"require": ["exp", "iat", "sub"]},
        }
        if issuer:
            decode_kwargs["issuer"] = issuer
        payload = jwt.decode(id_token, signing_key.key, **decode_kwargs)
    except (InvalidTokenError, PyJWKClientError, ValueError, TypeError):
        logger.warning("VK id_token signature or claims validation failed", exc_info=True)
        return None

    sub = payload.get("user_id") or payload.get("uid") or payload.get("sub")
    if sub is None:
        sub = user_id_hint
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
        "email": _normalize_email(payload.get("email")),
        "phone": _normalize_phone(payload.get("phone_number") or payload.get("phone")),
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
    "_clear_auth_cookie",
    "_deleted_user_public_payload",
    "_delete_site_user_account",
    "_is_deleted_site_user",
    "_fetch_vk_json",
    "_fetch_vk_id_json",
    "_generate_verification_code",
    "_generate_unique_username",
    "_get_auth_token_from_request",
    "_get_auth_tokens_from_request",
    "_get_user_from_request",
    "_get_user_from_token",
    "_issue_author_verification_code",
    "_issue_token",
    "_parse_vk_id_token",
    "_public_user_author_ids",
    "_register_password_user",
    "_request_password_reset",
    "_revoke_request_tokens",
    "_revoke_token",
    "_reset_password_by_token",
    "_send_password_reset_email",
    "_send_registration_email",
    "_verify_email_by_secret",
    "_set_auth_cookie",
    "_update_site_profile",
    "_upsert_telegram_account",
    "_upsert_vk_account",
    "_validate_telegram_login",
    "_vk_login_will_create_new_user",
]
