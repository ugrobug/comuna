"""Хелперы импорта из WordPress."""

from __future__ import annotations

import re
import secrets
from html import unescape

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.text import slugify

from feeds.models import Author, Post
from legacy_migration.models import LegacyWpUserMap, WpUsers
from legacy_migration.wordpress_hasher import (
    wordpress_password_field_value,
    wp_password_hash_usable,
)
from users.models import AuthorAdmin, SiteUserProfile

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
    map_row = LegacyWpUserMap.objects.filter(wp_user_id=wp_user_id).select_related("author").first()
    if map_row and map_row.author_id and map_row.author:
        return map_row.author, False

    base = wp_author_username(
        wp_user_id=wp_user_id,
        user_login=user_login,
        user_nicename=user_nicename,
    )
    # Если на Tambur уже существует Author с таким username и совпадающим title,
    # считаем что это "тот же" автор и используем его, даже если это телеграм-канал.
    display_norm = (display_name or "").strip()
    if display_norm and base:
        existing_by_base = Author.objects.filter(username__iexact=base).first()
        if existing_by_base and (existing_by_base.title or "").strip() == display_norm:
            return existing_by_base, False

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


def _wp_import_author_username_q(base: str, wp_user_id: int) -> Q:
    """Имена Author, которые создаёт импорт WP для одного wp_user_id (без голого base)."""
    escaped = re.escape(base)
    wid = int(wp_user_id)
    return (
        Q(username__iexact=f"{base}-wp{wid}")
        | Q(username__iregex=rf"^{escaped}-wp{wid}-\d+$")
        | Q(username__iregex=rf"^{escaped}-legacy-wp{wid}(-\d+)?$")
    )


def authors_created_for_wp_import(wp_user_id: int, base: str) -> list[Author]:
    return list(Author.objects.filter(_wp_import_author_username_q(base, wp_user_id)).order_by("id"))


def pick_canonical_wp_import_author(
    authors: list[Author],
    *,
    wp_user_id: int,
    base: str,
    map_author_id: int | None,
) -> Author:
    if not authors:
        raise ValueError("authors пуст")
    if len(authors) == 1:
        return authors[0]
    by_id = {a.id: a for a in authors}
    if map_author_id and map_author_id in by_id:
        return by_id[map_author_id]
    preferred = f"{base}-wp{wp_user_id}".lower()
    for author in authors:
        if author.username.lower() == preferred:
            return author
    post_counts = Post.objects.filter(author_id__in=by_id.keys()).values("author_id").annotate(c=Count("id"))
    count_map = {row["author_id"]: row["c"] for row in post_counts}
    return max(authors, key=lambda a: (count_map.get(a.id, 0), -a.id))


def dedupe_wp_import_authors_for_user(
    wp_user_id: int,
    *,
    dry_run: bool = False,
) -> dict[str, object]:
    """
    Слить jeckmod-wp266, jeckmod-wp266-2, … в одного Author.
    Карточку jeckmod без суффикса -wp{id} не трогаем (часто живой канал).
    """
    wp_user = WpUsers.objects.filter(id=wp_user_id).first()
    if not wp_user:
        return {"status": "no_wp_user", "wp_user_id": wp_user_id}

    base = wp_author_username(
        wp_user_id=wp_user_id,
        user_login=wp_user.user_login or "",
        user_nicename=wp_user.user_nicename or "",
    )
    display_norm = (getattr(wp_user, "display_name", "") or "").strip()

    # Canonical: если есть живой Author с username=base и title совпадает с display_name,
    # то это "оригинал" — сливаем всё в него.
    canonical_by_base = None
    if base and display_norm:
        a = Author.objects.filter(username__iexact=base).first()
        if a and (a.title or "").strip() == display_norm:
            canonical_by_base = a

    authors = authors_created_for_wp_import(wp_user_id, base)
    if canonical_by_base:
        # Сливаем в base-автора, даже если дублей пока нет.
        canonical = canonical_by_base
        dup_ids = [a.id for a in authors if a.id != canonical.id]
    else:
        if len(authors) <= 1:
            return {
                "status": "skip",
                "wp_user_id": wp_user_id,
                "canonical_id": authors[0].id if authors else None,
                "canonical_username": authors[0].username if authors else None,
                "merged": 0,
            }

        map_row = LegacyWpUserMap.objects.filter(wp_user_id=wp_user_id).first()
        map_author_id = int(map_row.author_id) if map_row and map_row.author_id else None
        canonical = pick_canonical_wp_import_author(
            authors,
            wp_user_id=wp_user_id,
            base=base,
            map_author_id=map_author_id,
        )
        dup_ids = [a.id for a in authors if a.id != canonical.id]

    map_row = LegacyWpUserMap.objects.filter(wp_user_id=wp_user_id).first()
    posts_moved = Post.objects.filter(author_id__in=dup_ids).count()

    if dry_run:
        return {
            "status": "dry-run",
            "wp_user_id": wp_user_id,
            "canonical_id": canonical.id,
            "canonical_username": canonical.username,
            "dup_ids": dup_ids,
            "posts_moved": posts_moved,
            "merged": len(dup_ids),
        }

    if dup_ids:
        Post.objects.filter(author_id__in=dup_ids).update(author_id=canonical.id)
        LegacyWpUserMap.objects.filter(author_id__in=dup_ids).update(author=canonical)
        Author.objects.filter(id__in=dup_ids).delete()
    if map_row and map_row.author_id and int(map_row.author_id) != int(canonical.id):
        map_row.author = canonical
        map_row.save(update_fields=["author", "updated_at"])

    return {
        "status": "merged",
        "wp_user_id": wp_user_id,
        "canonical_id": canonical.id,
        "canonical_username": canonical.username,
        "dup_ids": dup_ids,
        "posts_moved": posts_moved,
        "merged": len(dup_ids),
    }


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


def assign_wp_password_from_hash(user: User, user_pass: str) -> bool:
    """Записать user_pass из WP в User.password (без set_password)."""
    raw = (user_pass or "").strip()
    if wp_password_hash_usable(raw):
        user.password = wordpress_password_field_value(raw)
        user.save(update_fields=["password"])
        return True
    user.set_unusable_password()
    user.save(update_fields=["password"])
    return False


def _unique_email_for_wp_import(email: str, *, exclude_user_id: int | None) -> str:
    cleaned = (email or "").strip()
    if not cleaned:
        return ""
    qs = User.objects.filter(email__iexact=cleaned)
    if exclude_user_id:
        qs = qs.exclude(pk=exclude_user_id)
    if qs.exists():
        return ""
    return cleaned


def _find_existing_user_by_email(email: str) -> User | None:
    cleaned = (email or "").strip()
    if not cleaned:
        return None
    return User.objects.filter(email__iexact=cleaned).first()


def upsert_django_user_for_wp_user(
    wp_user: WpUsers,
    *,
    force_password: bool = False,
) -> tuple[User, bool, bool, bool]:
    """
    Создать/обновить auth User + LegacyWpUserMap для строки wp_users.
    Возвращает (user, user_created, password_updated, linked_existing_user).
    linked_existing_user: найден живой User по email без маппинга — пароль/email не трогаем.
    """
    wp_user_id = int(wp_user.id)
    display = (wp_user.display_name or wp_user.user_nicename or wp_user.user_login or "").strip()
    map_row = LegacyWpUserMap.objects.filter(wp_user_id=wp_user_id).select_related("user").first()

    user_created = False
    password_updated = False
    linked_existing_user = False

    if map_row and map_row.user_id:
        user = map_row.user
    else:
        existing = _find_existing_user_by_email(wp_user.user_email)
        if existing:
            user = existing
            linked_existing_user = True
        else:
            base = wp_user_username(
                wp_user_id=wp_user_id,
                user_login=wp_user.user_login,
                user_nicename=wp_user.user_nicename,
            )
            username = unique_django_username(base, wp_user_id=wp_user_id)
            email = _unique_email_for_wp_import(wp_user.user_email, exclude_user_id=None)
            user = User.objects.create_user(username=username, email=email or None)
            user_created = True

    changed_user = False
    if not linked_existing_user:
        email = _unique_email_for_wp_import(wp_user.user_email, exclude_user_id=user.pk)
        if email and (user.email or "").lower() != email.lower():
            user.email = email
            changed_user = True

    if linked_existing_user:
        should_set_password = force_password
    else:
        should_set_password = force_password or user_created or not user.has_usable_password()
    if should_set_password and (force_password or wp_password_hash_usable(wp_user.user_pass)):
        if assign_wp_password_from_hash(user, wp_user.user_pass):
            password_updated = True
        elif user_created:
            password_updated = True

    if changed_user:
        user.save(update_fields=["email"])

    if display:
        if linked_existing_user:
            SiteUserProfile.objects.get_or_create(
                user=user,
                defaults={"display_name": display[:120]},
            )
        else:
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
    ensure_author_admin_for_legacy_map(LegacyWpUserMap.objects.filter(wp_user_id=wp_user_id).first())
    return user, user_created, password_updated, linked_existing_user


def ensure_author_admin_for_legacy_map(
    map_row: LegacyWpUserMap | None,
    *,
    dry_run: bool = False,
) -> str:
    """
    Связать User ↔ Author через AuthorAdmin по строке LegacyWpUserMap.
    Возвращает: created | verified | exists | missing | conflict.
    """
    if not map_row or not map_row.user_id or not map_row.author_id:
        return "missing"

    user_id = int(map_row.user_id)
    author_id = int(map_row.author_id)

    other_user_link = AuthorAdmin.objects.filter(author_id=author_id).exclude(user_id=user_id).first()
    if other_user_link:
        return "conflict"

    link = AuthorAdmin.objects.filter(user_id=user_id, author_id=author_id).first()
    if link:
        if link.verified_at:
            return "exists"
        if dry_run:
            return "verified"
        link.verified_at = timezone.now()
        link.save(update_fields=["verified_at"])
        return "verified"

    if dry_run:
        return "created"

    AuthorAdmin.objects.create(
        user_id=user_id,
        author_id=author_id,
        verified_at=timezone.now(),
    )
    return "created"


def resolve_user_for_wp_user_id(wp_user_id: int) -> User:
    wp_user_id = int(wp_user_id)
    if wp_user_id <= 0:
        raise ValueError("invalid wp user id")

    map_row = LegacyWpUserMap.objects.filter(wp_user_id=wp_user_id).select_related("user").first()
    if map_row and map_row.user_id:
        wp_user = WpUsers.objects.filter(id=wp_user_id).first()
        if wp_user and wp_password_hash_usable(wp_user.user_pass):
            stored = (map_row.user.password or "").strip()
            if not stored.startswith("wordpress$") and not wp_password_hash_usable(stored):
                assign_wp_password_from_hash(map_row.user, wp_user.user_pass)
        return map_row.user

    wp_user = WpUsers.objects.filter(id=wp_user_id).first()
    if not wp_user:
        raise LookupError(f"wp user {wp_user_id} not found")

    user, _, _, _ = upsert_django_user_for_wp_user(wp_user, force_password=False)
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
