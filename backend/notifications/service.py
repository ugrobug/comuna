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


SPECIAL_PROJECT_NOTIFICATION_KEY = "special_project_notifications"
SPECIAL_PROJECT_NOTIFICATION_EVENT_KEYS = {
    "film_journey_daily",
    "film_journey_reminder",
    "public_book_reminder",
    "public_book_final_pdf",
}


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
        "description": "Опубликован пост в сообществе на которую вы подписаны.",
        "default_site_enabled": True,
        "default_telegram_enabled": False,
        "default_push_enabled": True,
        "supports_grouping": True,
        "default_grouping_period": "none",
        "grouping_options": [
            {"value": "none", "label": "Не группировать"},
            {"value": "day", "label": "Группировать за день"},
            {"value": "week", "label": "Группировать за неделю"},
        ],
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
        "settings_hidden": True,
    },
    {
        "key": SPECIAL_PROJECT_NOTIFICATION_KEY,
        "title": "Оповещения спецпроектов",
        "description": "Новые материалы, напоминания и финальные уведомления по спецпроектам.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
        "settings_only": True,
    },
    {
        "key": "film_journey_daily",
        "title": "Новый фильм спецпроекта",
        "description": "Ежедневная секретная ссылка на фильм из спецпроекта 365.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
        "settings_group": SPECIAL_PROJECT_NOTIFICATION_KEY,
    },
    {
        "key": "film_journey_reminder",
        "title": "Напоминание спецпроекта 365",
        "description": "Напоминание оставить оценку и комментарий, чтобы получить следующий фильм.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
        "settings_group": SPECIAL_PROJECT_NOTIFICATION_KEY,
    },
    {
        "key": "public_book_reminder",
        "title": "Напоминание книги сообщества",
        "description": (
            "Напоминание добавить следующее слово в книгу: через 24 часа после слова "
            "и еще один раз, если пользователь не вернулся."
        ),
        "default_site_enabled": False,
        "default_telegram_enabled": True,
        "default_push_enabled": False,
        "settings_group": SPECIAL_PROJECT_NOTIFICATION_KEY,
    },
    {
        "key": "public_book_final_pdf",
        "title": "PDF книги сообщества",
        "description": "Оповещение, когда финальная версия книги станет доступна.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
        "default_push_enabled": True,
        "settings_group": SPECIAL_PROJECT_NOTIFICATION_KEY,
    },
]

_NOTIFICATION_EVENT_MAP = {
    str(item["key"]): item for item in NOTIFICATION_EVENT_DEFINITIONS
}
VALID_NOTIFICATION_GROUPING_PERIODS = {"none", "day", "week"}


def _normalize_grouping_period(value: object, *, default: str = "none") -> str:
    period = str(value or "").strip().lower()
    if period in VALID_NOTIFICATION_GROUPING_PERIODS:
        return period
    return default if default in VALID_NOTIFICATION_GROUPING_PERIODS else "none"


def _default_grouping_period(definition: dict[str, Any]) -> str:
    return _normalize_grouping_period(definition.get("default_grouping_period"), default="none")


def _settings_event_definitions() -> list[dict[str, Any]]:
    return [
        item
        for item in NOTIFICATION_EVENT_DEFINITIONS
        if not item.get("settings_group") and not item.get("settings_hidden")
    ]


def _notification_preference_key(event_key: str) -> str:
    key = str(event_key or "").strip()
    return SPECIAL_PROJECT_NOTIFICATION_KEY if key in SPECIAL_PROJECT_NOTIFICATION_EVENT_KEYS else key


def get_notification_event_catalog() -> list[dict[str, Any]]:
    return [dict(item) for item in _settings_event_definitions()]


def get_notification_event_definition(event_key: str) -> dict[str, Any] | None:
    return _NOTIFICATION_EVENT_MAP.get((event_key or "").strip())


def _ensure_user_notification_preferences(user: User) -> dict[str, SiteNotificationPreference]:
    existing = {
        item.event_key: item
        for item in SiteNotificationPreference.objects.filter(user=user)
    }
    missing: list[SiteNotificationPreference] = []
    for definition in _settings_event_definitions():
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
                grouping_period=_default_grouping_period(definition),
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
    for definition in _settings_event_definitions():
        key = str(definition["key"])
        pref = preferences.get(key)
        default_site_enabled = bool(definition.get("default_site_enabled", True))
        default_telegram_enabled = bool(definition.get("default_telegram_enabled", False))
        default_push_enabled = bool(definition.get("default_push_enabled", True))
        supports_grouping = bool(definition.get("supports_grouping", False))
        default_grouping_period = _default_grouping_period(definition)
        grouping_period = (
            _normalize_grouping_period(pref.grouping_period, default=default_grouping_period)
            if pref and supports_grouping
            else default_grouping_period
        )
        events.append(
            {
                "key": key,
                "title": str(definition.get("title") or key),
                "description": str(definition.get("description") or ""),
                "site_enabled": pref.site_enabled if pref else default_site_enabled,
                "telegram_enabled": pref.telegram_enabled if pref else default_telegram_enabled,
                "push_enabled": pref.push_enabled if pref else default_push_enabled,
                "supports_grouping": supports_grouping,
                "grouping_period": grouping_period if supports_grouping else "none",
                "default_grouping_period": default_grouping_period,
                "grouping_options": list(definition.get("grouping_options") or []),
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
            key = _notification_preference_key(key)
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
            definition = _NOTIFICATION_EVENT_MAP.get(key) or {}
            supports_grouping = bool(definition.get("supports_grouping", False))
            default_grouping_period = _default_grouping_period(definition)
            site_enabled = pref.site_enabled if pref is not None else default_site_enabled
            telegram_enabled = (
                pref.telegram_enabled if pref is not None else default_telegram_enabled
            )
            push_enabled = pref.push_enabled if pref is not None else default_push_enabled
            grouping_period = (
                _normalize_grouping_period(pref.grouping_period, default=default_grouping_period)
                if pref is not None and supports_grouping
                else default_grouping_period
            )
            if "site_enabled" in item:
                site_enabled = bool(item.get("site_enabled"))
            if "telegram_enabled" in item:
                telegram_enabled = bool(item.get("telegram_enabled"))
            if "push_enabled" in item:
                push_enabled = bool(item.get("push_enabled"))
            if supports_grouping and "grouping_period" in item:
                grouping_period = _normalize_grouping_period(
                    item.get("grouping_period"),
                    default=default_grouping_period,
                )
            if not supports_grouping:
                grouping_period = "none"
            if pref is None:
                pref = SiteNotificationPreference.objects.create(
                    user=user,
                    event_key=key,
                    site_enabled=site_enabled,
                    telegram_enabled=telegram_enabled,
                    push_enabled=push_enabled,
                    grouping_period=grouping_period,
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
            if pref.grouping_period != grouping_period:
                pref.grouping_period = grouping_period
                changed = True
            if changed:
                pref.save(
                    update_fields=[
                        "site_enabled",
                        "telegram_enabled",
                        "push_enabled",
                        "grouping_period",
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

    preference_key = _notification_preference_key(event_key)
    definition = get_notification_event_definition(preference_key) or get_notification_event_definition(event_key) or {}
    preferences = _ensure_user_notification_preferences(user)

    pref = preferences.get(preference_key)
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
        group_count=1,
        is_site=is_site,
        is_telegram=is_telegram,
        is_push=is_push,
    )
    if is_telegram:
        send_site_notification_to_telegram(notification)
    if is_push:
        send_site_notification_to_push(notification)
    return notification


def create_grouped_user_notification(
    *,
    user: User | None,
    event_key: str,
    title: str,
    message: str = "",
    link_url: str = "",
    payload: dict[str, Any] | None = None,
    group_key: str = "",
    group_item: dict[str, Any] | None = None,
    force_site: bool | None = None,
    force_telegram: bool | None = None,
    force_push: bool | None = None,
) -> SiteNotification | None:
    if user is None or not group_key:
        return create_user_notification(
            user=user,
            event_key=event_key,
            title=title,
            message=message,
            link_url=link_url,
            payload=payload,
            force_site=force_site,
            force_telegram=force_telegram,
            force_push=force_push,
        )

    preference_key = _notification_preference_key(event_key)
    definition = get_notification_event_definition(preference_key) or get_notification_event_definition(event_key) or {}
    preferences = _ensure_user_notification_preferences(user)
    pref = preferences.get(preference_key)
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

    item = group_item if isinstance(group_item, dict) else {}
    with transaction.atomic():
        notification = (
            SiteNotification.objects.select_for_update()
            .filter(user=user, event_key=event_key, group_key=group_key)
            .first()
        )
        if not notification:
            group_payload = dict(payload or {})
            group_payload["items"] = [item] if item else []
            notification = SiteNotification.objects.create(
                user=user,
                event_key=event_key,
                title=str(title or "").strip()[:255],
                message=str(message or "").strip(),
                link_url=str(link_url or "").strip()[:500],
                payload=group_payload,
                group_key=str(group_key or "").strip()[:160],
                group_count=1,
                is_site=is_site,
                is_telegram=is_telegram,
                is_push=is_push,
            )
        else:
            group_payload = notification.payload if isinstance(notification.payload, dict) else {}
            items = list(group_payload.get("items") or [])
            item_id = item.get("id") if item else None
            if item and not any(existing.get("id") == item_id for existing in items if isinstance(existing, dict)):
                items.append(item)
            group_payload.update(payload or {})
            group_payload["items"] = items[-100:]
            notification.title = str(title or "").strip()[:255]
            notification.message = str(message or "").strip()
            notification.link_url = str(link_url or "").strip()[:500]
            notification.payload = group_payload
            notification.group_count = max(len(items), int(notification.group_count or 0), 1)
            notification.is_site = is_site
            notification.is_telegram = is_telegram
            notification.is_push = is_push
            notification.read_at = None
            notification.save(
                update_fields=[
                    "title",
                    "message",
                    "link_url",
                    "payload",
                    "group_count",
                    "is_site",
                    "is_telegram",
                    "is_push",
                    "read_at",
                    "updated_at",
                ]
            )

    if is_telegram:
        send_site_notification_to_telegram(notification)
    if is_push:
        send_site_notification_to_push(notification)
    return notification


def notification_grouping_period_for_user(user: User | None, event_key: str) -> str:
    if user is None:
        return "none"
    definition = get_notification_event_definition(event_key) or {}
    if not definition.get("supports_grouping"):
        return "none"
    preferences = _ensure_user_notification_preferences(user)
    pref = preferences.get(event_key)
    default_grouping_period = _default_grouping_period(definition)
    return _normalize_grouping_period(
        pref.grouping_period if pref else default_grouping_period,
        default=default_grouping_period,
    )


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
    items = list(list_qs.order_by("-updated_at", "-id")[safe_offset : safe_offset + safe_limit])
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
    "create_grouped_user_notification",
    "create_user_notification",
    "get_notification_event_catalog",
    "get_notification_event_definition",
    "list_site_notifications_for_user",
    "mark_all_site_notifications_read_for_user",
    "mark_site_notification_read_for_user",
    "notification_grouping_period_for_user",
    "serialize_notification_settings_for_user",
    "update_notification_settings_for_user",
]
