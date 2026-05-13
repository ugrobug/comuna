from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from notifications.models import SiteNotification, SiteNotificationPreference
from notifications.push_service import (
    send_site_notification_to_push,
    summarize_push_devices_for_user,
)
from telegram_integration.models import TelegramAccount
from telegram_integration.service import send_site_notification_to_telegram

User = get_user_model()


NOTIFICATION_EVENT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "key": "post_comment",
        "title": "Новый комментарий к вашему посту",
        "description": "Кто-то оставил комментарий под вашим постом.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
    },
    {
        "key": "comment_reply",
        "title": "Ответ на ваш комментарий",
        "description": "Кто-то ответил на ваш комментарий.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
    },
    {
        "key": "post_published",
        "title": "Пост опубликован",
        "description": "Ваш пост был опубликован и стал доступен на сайте.",
        "default_site_enabled": True,
        "default_telegram_enabled": False,
        "default_push_enabled": True,
    },
    {
        "key": "comun_invite",
        "title": "Приглашение в коммуну",
        "description": "Вас пригласили в коммуну или назначили модератором.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
    },
    {
        "key": "post_added_to_voting",
        "title": "Ваш пост добавили в голосование",
        "description": "Пост вашей авторской ленты попал в этап голосования в комуне.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
    },
    {
        "key": "bug_report_status_changed",
        "title": "Изменился статус баг-репорта",
        "description": "Баг-репорт, который вы отметили, получил новый статус.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
    },
    {
        "key": "system_announcement",
        "title": "Системное объявление",
        "description": "Важные новости и сообщения от команды проекта.",
        "default_site_enabled": True,
        "default_telegram_enabled": False,
        "default_push_enabled": True,
    },
]

_NOTIFICATION_EVENT_MAP = {
    str(item["key"]): item for item in NOTIFICATION_EVENT_DEFINITIONS
}


def get_notification_event_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in NOTIFICATION_EVENT_DEFINITIONS]


def get_notification_event_definition(event_key: str) -> dict[str, Any] | None:
    return _NOTIFICATION_EVENT_MAP.get((event_key or "").strip())


def _ensure_user_notification_preferences(user: User) -> dict[str, SiteNotificationPreference]:
    existing = {
        item.event_key: item
        for item in SiteNotificationPreference.objects.filter(user=user)
    }
    missing: list[SiteNotificationPreference] = []
    for definition in NOTIFICATION_EVENT_DEFINITIONS:
        key = str(definition["key"])
        if key in existing:
            continue
        missing.append(
            SiteNotificationPreference(
                user=user,
                event_key=key,
                site_enabled=bool(definition.get("default_site_enabled", True)),
                telegram_enabled=bool(definition.get("default_telegram_enabled", False)),
                push_enabled=bool(definition.get("default_push_enabled", True)),
            )
        )
    if missing:
        SiteNotificationPreference.objects.bulk_create(missing, ignore_conflicts=True)
        existing = {
            item.event_key: item
            for item in SiteNotificationPreference.objects.filter(user=user)
        }
    return existing


def serialize_notification_settings_for_user(user: User) -> dict[str, Any]:
    preferences = _ensure_user_notification_preferences(user)

    events: list[dict[str, Any]] = []
    for definition in NOTIFICATION_EVENT_DEFINITIONS:
        key = str(definition["key"])
        pref = preferences.get(key)
        default_site_enabled = bool(definition.get("default_site_enabled", True))
        default_telegram_enabled = bool(definition.get("default_telegram_enabled", False))
        default_push_enabled = bool(definition.get("default_push_enabled", True))
        events.append(
            {
                "key": key,
                "title": str(definition.get("title") or key),
                "description": str(definition.get("description") or ""),
                "site_enabled": pref.site_enabled if pref else default_site_enabled,
                "telegram_enabled": pref.telegram_enabled if pref else default_telegram_enabled,
                "push_enabled": pref.push_enabled if pref else default_push_enabled,
                "default_site_enabled": default_site_enabled,
                "default_telegram_enabled": default_telegram_enabled,
                "default_push_enabled": default_push_enabled,
            }
        )

    telegram_account = TelegramAccount.objects.filter(user=user).first()
    push_summary = summarize_push_devices_for_user(user)
    return {
        "events": events,
        "telegram": {
            "linked": bool(telegram_account),
            "username": telegram_account.username if telegram_account else "",
            "first_name": telegram_account.first_name if telegram_account else "",
        },
        "push": {
            "configured": bool(push_summary.get("configured")),
            "registered_devices_count": int(push_summary.get("registered_devices_count", 0)),
            "active_platforms": list(push_summary.get("active_platforms") or []),
        },
    }


def update_notification_settings_for_user(
    user: User,
    raw_settings: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(raw_settings, list):
        raise ValueError("settings must be a list")

    valid_keys = set(_NOTIFICATION_EVENT_MAP.keys())
    preferences = _ensure_user_notification_preferences(user)
    seen_keys: set[str] = set()

    with transaction.atomic():
        for item in raw_settings:
            if not isinstance(item, dict):
                raise ValueError("invalid settings item")
            key = str(item.get("key") or "").strip()
            if not key or key not in valid_keys:
                raise ValueError(f"unknown event key: {key or 'empty'}")
            if key in seen_keys:
                continue
            seen_keys.add(key)

            pref = preferences.get(key)
            default_site_enabled = bool(
                (_NOTIFICATION_EVENT_MAP.get(key) or {}).get("default_site_enabled", True)
            )
            default_telegram_enabled = bool(
                (_NOTIFICATION_EVENT_MAP.get(key) or {}).get("default_telegram_enabled", False)
            )
            default_push_enabled = bool(
                (_NOTIFICATION_EVENT_MAP.get(key) or {}).get("default_push_enabled", True)
            )
            site_enabled = pref.site_enabled if pref is not None else default_site_enabled
            telegram_enabled = (
                pref.telegram_enabled if pref is not None else default_telegram_enabled
            )
            push_enabled = pref.push_enabled if pref is not None else default_push_enabled
            if "site_enabled" in item:
                site_enabled = bool(item.get("site_enabled"))
            if "telegram_enabled" in item:
                telegram_enabled = bool(item.get("telegram_enabled"))
            if "push_enabled" in item:
                push_enabled = bool(item.get("push_enabled"))
            if pref is None:
                pref = SiteNotificationPreference.objects.create(
                    user=user,
                    event_key=key,
                    site_enabled=site_enabled,
                    telegram_enabled=telegram_enabled,
                    push_enabled=push_enabled,
                )
                preferences[key] = pref
                continue

            changed = False
            if pref.site_enabled != site_enabled:
                pref.site_enabled = site_enabled
                changed = True
            if pref.telegram_enabled != telegram_enabled:
                pref.telegram_enabled = telegram_enabled
                changed = True
            if pref.push_enabled != push_enabled:
                pref.push_enabled = push_enabled
                changed = True
            if changed:
                pref.save(
                    update_fields=[
                        "site_enabled",
                        "telegram_enabled",
                        "push_enabled",
                        "updated_at",
                    ]
                )

    return serialize_notification_settings_for_user(user)


def create_user_notification(
    *,
    user: User | None,
    event_key: str,
    title: str,
    message: str = "",
    link_url: str = "",
    payload: dict[str, Any] | None = None,
    force_site: bool | None = None,
    force_telegram: bool | None = None,
    force_push: bool | None = None,
) -> SiteNotification | None:
    if user is None:
        return None

    definition = get_notification_event_definition(event_key) or {}
    preferences = _ensure_user_notification_preferences(user)

    pref = preferences.get(event_key)
    is_site = bool(force_site) if force_site is not None else bool(
        pref.site_enabled if pref else definition.get("default_site_enabled", True)
    )
    is_telegram = bool(force_telegram) if force_telegram is not None else bool(
        pref.telegram_enabled if pref else definition.get("default_telegram_enabled", False)
    )
    is_push = bool(force_push) if force_push is not None else bool(
        pref.push_enabled if pref else definition.get("default_push_enabled", True)
    )

    if not is_site and not is_telegram and not is_push:
        return None

    notification = SiteNotification.objects.create(
        user=user,
        event_key=event_key,
        title=str(title or "").strip()[:255],
        message=str(message or "").strip(),
        link_url=str(link_url or "").strip()[:500],
        payload=payload or {},
        is_site=is_site,
        is_telegram=is_telegram,
        is_push=is_push,
    )
    if is_telegram:
        send_site_notification_to_telegram(notification)
    if is_push:
        send_site_notification_to_push(notification)
    return notification


def list_site_notifications_for_user(
    user: User,
    *,
    limit: int = 10,
    offset: int = 0,
    unread_only: bool = False,
) -> tuple[list[SiteNotification], int, int]:
    safe_limit = min(max(int(limit or 10), 1), 50)
    safe_offset = max(int(offset or 0), 0)
    base_qs = SiteNotification.objects.filter(user=user, is_site=True)
    list_qs = base_qs.filter(read_at__isnull=True) if unread_only else base_qs
    total_count = list_qs.count()
    items = list(list_qs.order_by("-created_at", "-id")[safe_offset : safe_offset + safe_limit])
    unread_count = base_qs.filter(read_at__isnull=True).count()
    return items, unread_count, total_count


def mark_site_notification_read_for_user(
    user: User,
    notification_id: int,
) -> tuple[SiteNotification | None, int]:
    notification = SiteNotification.objects.filter(
        id=notification_id,
        user=user,
        is_site=True,
    ).first()
    if not notification:
        return None, SiteNotification.objects.filter(
            user=user,
            is_site=True,
            read_at__isnull=True,
        ).count()

    if notification.read_at is None:
        notification.read_at = timezone.now()
        notification.save(update_fields=["read_at", "updated_at"])

    unread_count = SiteNotification.objects.filter(
        user=user,
        is_site=True,
        read_at__isnull=True,
    ).count()
    return notification, unread_count


def mark_all_site_notifications_read_for_user(user: User) -> int:
    now = timezone.now()
    return SiteNotification.objects.filter(
        user=user,
        is_site=True,
        read_at__isnull=True,
    ).update(read_at=now, updated_at=now)


__all__ = [
    "NOTIFICATION_EVENT_DEFINITIONS",
    "create_user_notification",
    "get_notification_event_catalog",
    "get_notification_event_definition",
    "list_site_notifications_for_user",
    "mark_all_site_notifications_read_for_user",
    "mark_site_notification_read_for_user",
    "serialize_notification_settings_for_user",
    "update_notification_settings_for_user",
]
