from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from notifications import serializers as notification_serializers
from notifications.service import (
    list_site_notifications_for_user,
    mark_all_site_notifications_read_for_user,
    mark_site_notification_read_for_user,
    serialize_notification_settings_for_user,
    update_notification_settings_for_user,
)
from users.views import _get_user_from_request


_serialize_site_notification_item = notification_serializers._serialize_site_notification_item


@csrf_exempt
def auth_notification_settings(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)

    if request.method == "GET":
        payload = serialize_notification_settings_for_user(user)
        return JsonResponse({"ok": True, **payload})

    if request.method not in ("PATCH", "POST"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    raw_settings = body.get("events")
    if raw_settings is None:
        raw_settings = body.get("settings")
    if raw_settings is None:
        return JsonResponse({"ok": False, "error": "events are required"}, status=400)

    try:
        payload = update_notification_settings_for_user(user, raw_settings)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({"ok": True, **payload})


def auth_notifications(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    limit_raw = request.GET.get("limit", "10")
    offset_raw = request.GET.get("offset", "0")
    try:
        limit = min(max(int(limit_raw), 1), 50)
    except ValueError:
        limit = 10
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    unread_only = (request.GET.get("unread_only") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    notifications, unread_count, total_count = list_site_notifications_for_user(
        user,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )

    return JsonResponse(
        {
            "ok": True,
            "items": [_serialize_site_notification_item(item) for item in notifications],
            "unread_count": unread_count,
            "total_count": total_count,
        }
    )


@csrf_exempt
def auth_notification_read(request: HttpRequest, notification_id: int) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method not in ("POST", "PATCH"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    notification, unread_count = mark_site_notification_read_for_user(user, notification_id)
    if not notification:
        return JsonResponse({"ok": False, "error": "notification not found"}, status=404)
    return JsonResponse(
        {
            "ok": True,
            "item": _serialize_site_notification_item(notification),
            "unread_count": unread_count,
        }
    )


@csrf_exempt
def auth_notifications_read_all(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method not in ("POST", "PATCH"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    updated = mark_all_site_notifications_read_for_user(user)
    return JsonResponse({"ok": True, "updated": updated, "unread_count": 0})


__all__ = [
    "auth_notification_read",
    "auth_notification_settings",
    "auth_notifications",
    "auth_notifications_read_all",
]
