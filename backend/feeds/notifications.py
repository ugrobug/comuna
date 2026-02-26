from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import SiteNotification, SiteNotificationPreference, TelegramAccount

User = get_user_model()


# Add new events here: they will automatically appear in the user's
# notification settings page and will use these channel defaults.
NOTIFICATION_EVENT_DEFINITIONS: list[dict[str, Any]] = [
    {
        "key": "post_comment",
        "title": "Новый комментарий к вашему посту",
        "description": "Кто-то оставил комментарий под вашим постом.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
    },
    {
        "key": "comment_reply",
        "title": "Ответ на ваш комментарий",
        "description": "Кто-то ответил на ваш комментарий.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
    },
    {
        "key": "post_published",
        "title": "Пост опубликован",
        "description": "Ваш пост был опубликован и стал доступен на сайте.",
        "default_site_enabled": True,
        "default_telegram_enabled": False,
    },
    {
        "key": "comun_invite",
        "title": "Приглашение в коммуну",
        "description": "Вас пригласили в коммуну или назначили модератором.",
        "default_site_enabled": True,
        "default_telegram_enabled": True,
    },
    {
        "key": "system_announcement",
        "title": "Системное объявление",
        "description": "Важные новости и сообщения от команды проекта.",
        "default_site_enabled": True,
        "default_telegram_enabled": False,
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
        events.append(
            {
                "key": key,
                "title": str(definition.get("title") or key),
                "description": str(definition.get("description") or ""),
                "site_enabled": pref.site_enabled if pref else default_site_enabled,
                "telegram_enabled": pref.telegram_enabled if pref else default_telegram_enabled,
                "default_site_enabled": default_site_enabled,
                "default_telegram_enabled": default_telegram_enabled,
            }
        )

    telegram_account = TelegramAccount.objects.filter(user=user).first()
    return {
        "events": events,
        "telegram": {
            "linked": bool(telegram_account),
            "username": telegram_account.username if telegram_account else "",
            "first_name": telegram_account.first_name if telegram_account else "",
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

            site_enabled = bool(item.get("site_enabled", True))
            telegram_enabled = bool(item.get("telegram_enabled", False))

            pref = preferences.get(key)
            if pref is None:
                pref = SiteNotificationPreference.objects.create(
                    user=user,
                    event_key=key,
                    site_enabled=site_enabled,
                    telegram_enabled=telegram_enabled,
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
            if changed:
                pref.save(update_fields=["site_enabled", "telegram_enabled", "updated_at"])

    return serialize_notification_settings_for_user(user)


def _notification_link_absolute(link_url: str) -> str:
    value = (link_url or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    base = (getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    if not base:
        return value
    if not value.startswith("/"):
        value = f"/{value}"
    return f"{base}{value}"


def _send_telegram_notification(notification: SiteNotification) -> None:
    if not notification.is_telegram:
        return
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    if not token:
        return

    account = TelegramAccount.objects.filter(user=notification.user).first()
    if not account:
        return

    parts = [notification.title.strip()]
    if notification.message.strip():
        parts.append(notification.message.strip())
    link = _notification_link_absolute(notification.link_url)
    if link:
        parts.append(link)
    text = "\n\n".join([part for part in parts if part]).strip()
    if not text:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": str(account.telegram_id),
            "text": text[:4096],
            "disable_web_page_preview": "1",
        }
    ).encode("utf-8")

    try:
        request = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8") or "{}")
        if data.get("ok"):
            notification.telegram_sent_at = timezone.now()
            notification.telegram_error = ""
            notification.save(update_fields=["telegram_sent_at", "telegram_error", "updated_at"])
            return
        error_message = str(data.get("description") or "telegram send failed")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        error_message = str(exc)
    except Exception as exc:  # keep notification creation resilient
        error_message = str(exc)

    notification.telegram_error = error_message[:1000]
    notification.save(update_fields=["telegram_error", "updated_at"])


def create_user_notification(
    *,
    user: User,
    event_key: str,
    title: str | None = None,
    message: str = "",
    link_url: str = "",
    payload: dict[str, Any] | None = None,
    site_enabled: bool | None = None,
    telegram_enabled: bool | None = None,
) -> SiteNotification | None:
    definition = get_notification_event_definition(event_key)
    if not definition:
        raise ValueError(f"unknown notification event: {event_key}")

    preferences = _ensure_user_notification_preferences(user)
    pref = preferences.get(event_key)
    site_channel_enabled = (
        bool(site_enabled)
        if site_enabled is not None
        else bool(pref.site_enabled if pref else definition.get("default_site_enabled", True))
    )
    telegram_channel_enabled = (
        bool(telegram_enabled)
        if telegram_enabled is not None
        else bool(
            pref.telegram_enabled
            if pref
            else definition.get("default_telegram_enabled", False)
        )
    )

    if not site_channel_enabled and not telegram_channel_enabled:
        return None

    notification = SiteNotification.objects.create(
        user=user,
        event_key=event_key,
        title=(title or str(definition.get("title") or event_key)).strip()[:255],
        message=(message or "").strip(),
        link_url=(link_url or "").strip()[:500],
        payload=payload or {},
        is_site=site_channel_enabled,
        is_telegram=telegram_channel_enabled,
    )
    if telegram_channel_enabled:
        _send_telegram_notification(notification)
    return notification
