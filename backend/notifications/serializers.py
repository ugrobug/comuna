from __future__ import annotations

from notifications.models import SiteNotification


def _serialize_site_notification_item(item: SiteNotification) -> dict:
    return {
        "id": item.id,
        "event_key": item.event_key,
        "title": item.title,
        "message": item.message,
        "link_url": item.link_url or None,
        "payload": item.payload if isinstance(item.payload, dict) else {},
        "group_key": item.group_key or "",
        "group_count": int(item.group_count or 1),
        "is_read": bool(item.read_at),
        "read_at": item.read_at.isoformat() if item.read_at else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


__all__ = [
    "_serialize_site_notification_item",
]
