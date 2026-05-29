"""Хелперы импорта из WordPress."""

from __future__ import annotations

import re
import secrets
from html import unescape

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify

from feeds.models import Author
from legacy_migration.models import LegacyWpUserMap, WpUsers
from users.models import SiteUserProfile

User = get_user_model()


def wp_author_username(
    *,
    wp_user_id: int,
    user_login: str,
    user_nicename: str,
) -> str:
    nicename = (user_nicename or "").strip()
    login = (user_login or "").strip()
    raw = nicename or login
    base = slugify(raw)[:64]
    if not base:
        base = f"wp-user-{wp_user_id}"
    return base


def unique_author_username(base: str, *, wp_user_id: int) -> str:
    candidate = base[:64]
    if not Author.objects.filter(username__iexact=candidate).exists():
        return candidate
    suffix = f"-wp{wp_user_id}"
    trimmed = base[: max(1, 64 - len(suffix))].rstrip("-")
    candidate = f"{trimmed}{suffix}"[:64]
    if not Author.objects.filter(username__iexact=candidate).exists():
        return candidate
    for index in range(2, 1000):
        suffix = f"-wp{wp_user_id}-{index}"
        trimmed = base[: max(1, 64 - len(suffix))].rstrip("-")
        candidate = f"{trimmed}{suffix}"[:64]
        if not Author.objects.filter(username__iexact=candidate).exists():
            return candidate
    return f"wp-{wp_user_id}"[:64]


def resolve_author_for_wp_user(
    *,
    wp_user_id: int,
    user_login: str,
    user_nicename: str,
    display_name: str,
) -> tuple[Author, bool]:
    """Возвращает (author, created)."""
    base = wp_author_username(
        wp_user_id=wp_user_id,
        user_login=user_login,
        user_nicename=user_nicename,
    )
    username = unique_author_username(base, wp_user_id=wp_user_id)
    existing = Author.objects.filter(username__iexact=username).first()
    if existing:
        if not existing.channel_id and not (existing.channel_url or "").strip():
            return existing, False
        username = unique_author_username(f"{base}-legacy", wp_user_id=wp_user_id)
        existing = Author.objects.filter(username__iexact=username).first()
        if existing:
            return existing, False

    title = (display_name or user_nicename or user_login or username).strip()[:255]
    author = Author.objects.create(
        username=username,
        title=title,
        channel_url="",
        channel_id=None,
        description="",
    )
    return author, True


def wp_user_username(
    *,
    wp_user_id: int,
    user_login: str,
    user_nicename: str,
) -> str:
    login = (user_login or "").strip()
    if login:
        base = slugify(login)[:120]
        if base:
            return base
    return wp_author_username(
        wp_user_id=wp_user_id,
        user_login=user_login,
        user_nicename=user_nicename,
    )


def unique_django_username(base: str, *, wp_user_id: int) -> str:
    candidate = base[:150]
    if not User.objects.filter(username__iexact=candidate).exists():
        return candidate
    suffix = f"-wp{wp_user_id}"
    trimmed = base[: max(1, 150 - len(suffix))].rstrip("-")
    candidate = f"{trimmed}{suffix}"[:150]
    if not User.objects.filter(username__iexact=candidate).exists():
        return candidate
    for index in range(2, 1000):
        suffix = f"-wp{wp_user_id}-{index}"
        trimmed = base[: max(1, 150 - len(suffix))].rstrip("-")
        candidate = f"{trimmed}{suffix}"[:150]
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
    return f"wp-user-{wp_user_id}"[:150]


def unique_legacy_username(prefix: str, key: str) -> str:
    raw = slugify(f"{prefix}-{key}")[:120]
    if not raw:
        raw = f"{prefix}-{secrets.token_hex(4)}"
    candidate = raw[:150]
    if not User.objects.filter(username__iexact=candidate).exists():
        return candidate
    for index in range(2, 1000):
        candidate = f"{raw[:130]}-{index}"[:150]
        if not User.objects.filter(username__iexact=candidate).exists():
            return candidate
    return f"{prefix}-{secrets.token_hex(6)}"[:150]


def wp_comment_body_to_text(html: str) -> str:
    text = html or ""
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p\s*>", "\n\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def resolve_user_for_wp_user_id(wp_user_id: int) -> User:
    wp_user_id = int(wp_user_id)
    if wp_user_id <= 0:
        raise ValueError("invalid wp user id")

    map_row = LegacyWpUserMap.objects.filter(wp_user_id=wp_user_id).select_related("user").first()
    if map_row and map_row.user_id:
        return map_row.user

    wp_user = WpUsers.objects.filter(id=wp_user_id).first()
    if not wp_user:
        raise LookupError(f"wp user {wp_user_id} not found")

    display = (wp_user.display_name or wp_user.user_nicename or wp_user.user_login or "").strip()
    base = wp_user_username(
        wp_user_id=wp_user_id,
        user_login=wp_user.user_login,
        user_nicename=wp_user.user_nicename,
    )
    username = unique_django_username(base, wp_user_id=wp_user_id)
    user = User.objects.create_user(
        username=username,
        email=(wp_user.user_email or "").strip() or None,
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    if display:
        SiteUserProfile.objects.update_or_create(
            user=user,
            defaults={"display_name": display[:120]},
        )

    author, _ = resolve_author_for_wp_user(
        wp_user_id=wp_user_id,
        user_login=wp_user.user_login,
        user_nicename=wp_user.user_nicename,
        display_name=display,
    )
    LegacyWpUserMap.objects.update_or_create(
        wp_user_id=wp_user_id,
        defaults={
            "wp_login": wp_user.user_login or "",
            "wp_email": wp_user.user_email or "",
            "wp_display_name": display,
            "author": author,
            "user": user,
            "imported_at": timezone.now(),
        },
    )
    return user


def resolve_user_for_wp_comment(
    *,
    wp_user_id: int,
    comment_author: str,
    comment_author_email: str,
) -> User:
    if wp_user_id and int(wp_user_id) > 0:
        return resolve_user_for_wp_user_id(int(wp_user_id))

    email = (comment_author_email or "").strip().lower()
    name = (comment_author or "").strip()
    key = email or slugify(name) or secrets.token_hex(4)
    username = unique_legacy_username("legacy-guest", key)
    user = User.objects.create_user(username=username)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    if name:
        SiteUserProfile.objects.update_or_create(
            user=user,
            defaults={"display_name": name[:120]},
        )
    return user


def resolve_user_for_ulike_voter(ulike_user_id: str) -> User:
    raw = str(ulike_user_id or "").strip()
    if raw.isdigit() and int(raw) > 0:
        wp_id = int(raw)
        if WpUsers.objects.filter(id=wp_id).exists():
            return resolve_user_for_wp_user_id(wp_id)

    username = unique_legacy_username("legacy-ulike", raw or secrets.token_hex(4))
    user = User.objects.create_user(username=username)
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return user
