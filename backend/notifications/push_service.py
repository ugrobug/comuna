from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from functools import lru_cache
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from notifications.models import MobilePushDevice, SiteNotification

_PUSH_SCOPES = ("https://www.googleapis.com/auth/firebase.messaging",)
_TERMINAL_PUSH_ERROR_MARKERS = (
    "UNREGISTERED",
    "BadDeviceToken",
    "registration token is not a valid fcm registration token",
    "requested entity was not found",
)
_APNS_DEVICE_TOKEN_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_APNS_AUTH_TOKEN_TTL_SECONDS = 50 * 60
_APNS_AUTH_TOKEN_CACHE: dict[str, Any] = {}


def normalize_push_platform(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"ios", "iphone", "ipad"}:
        return "ios"
    if normalized in {"android"}:
        return "android"
    raise ValueError("unsupported push platform")


def mask_push_token(value: str) -> str:
    token = str(value or "").strip()
    if len(token) <= 18:
        return token
    return f"{token[:10]}...{token[-6:]}"


@lru_cache(maxsize=1)
def _load_push_service_account_info() -> dict[str, Any] | None:
    raw_json = str(getattr(settings, "PUSH_FCM_SERVICE_ACCOUNT_JSON", "") or "").strip()
    raw_file = str(getattr(settings, "PUSH_FCM_SERVICE_ACCOUNT_FILE", "") or "").strip()

    if raw_json:
        try:
            parsed = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid PUSH_FCM_SERVICE_ACCOUNT_JSON") from exc
        if isinstance(parsed, dict):
            return parsed
        raise ValueError("invalid PUSH_FCM_SERVICE_ACCOUNT_JSON")

    if not raw_file:
        return None

    with open(raw_file, "r", encoding="utf-8") as handle:
        parsed = json.load(handle)
    if not isinstance(parsed, dict):
        raise ValueError("invalid PUSH_FCM_SERVICE_ACCOUNT_FILE")
    return parsed


@lru_cache(maxsize=1)
def _load_apns_auth_key() -> str:
    raw_key = str(getattr(settings, "PUSH_APNS_AUTH_KEY", "") or "").strip()
    raw_file = str(getattr(settings, "PUSH_APNS_AUTH_KEY_FILE", "") or "").strip()

    if raw_key:
        return raw_key.replace("\\n", "\n")
    if not raw_file:
        return ""
    with open(raw_file, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _get_apns_provider_config() -> dict[str, Any]:
    config_error = ""
    auth_key = ""
    try:
        auth_key = _load_apns_auth_key()
    except OSError as exc:
        config_error = str(exc)

    key_id = str(getattr(settings, "PUSH_APNS_KEY_ID", "") or "").strip()
    team_id = str(getattr(settings, "PUSH_APNS_TEAM_ID", "") or "").strip()
    topic = str(getattr(settings, "PUSH_APNS_TOPIC", "") or "").strip()
    use_sandbox = bool(getattr(settings, "PUSH_APNS_USE_SANDBOX", False))
    missing = [
        label
        for label, value in {
            "APPLE_APNS_KEY_ID/PUSH_APNS_KEY_ID": key_id,
            "APPLE_TEAM_ID": team_id,
            "APPLE_APNS_TOPIC": topic,
            "PUSH_APNS_AUTH_KEY/PUSH_APNS_AUTH_KEY_FILE": auth_key,
        }.items()
        if not value
    ]
    if not config_error and missing and any([key_id, team_id, topic, auth_key]):
        config_error = "missing " + ", ".join(missing)
    return {
        "configured": bool(key_id and team_id and topic and auth_key),
        "config_error": config_error,
        "key_id": key_id,
        "team_id": team_id,
        "topic": topic,
        "auth_key": auth_key,
        "use_sandbox": use_sandbox,
    }


def get_push_provider_config() -> dict[str, Any]:
    fcm_config_error = ""
    try:
        info = _load_push_service_account_info()
    except ValueError as exc:
        info = None
        fcm_config_error = str(exc)
    project_id = str(getattr(settings, "PUSH_FCM_PROJECT_ID", "") or "").strip()
    if not project_id and info:
        project_id = str(info.get("project_id") or "").strip()
    fcm_configured = bool(project_id and info)
    apns_config = _get_apns_provider_config()

    return {
        "configured": bool(fcm_configured or apns_config["configured"]),
        "config_error": "; ".join(
            error for error in [fcm_config_error, apns_config["config_error"]] if error
        ),
        "fcm_configured": fcm_configured,
        "fcm_config_error": fcm_config_error,
        "apns_configured": apns_config["configured"],
        "apns_config_error": apns_config["config_error"],
        "project_id": project_id,
        "service_account_info": info,
        "apns": apns_config,
    }


def is_push_configured() -> bool:
    return bool(get_push_provider_config()["configured"])


def _serialize_push_device_item(device: MobilePushDevice) -> dict[str, Any]:
    return {
        "id": device.id,
        "platform": device.platform,
        "device_id": device.device_id or "",
        "device_name": device.device_name or "",
        "app_version": device.app_version or "",
        "token_preview": mask_push_token(device.token),
        "is_active": bool(device.is_active),
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "last_push_sent_at": device.last_push_sent_at.isoformat() if device.last_push_sent_at else None,
    }


def summarize_push_devices_for_user(user) -> dict[str, Any]:
    devices = list(
        MobilePushDevice.objects.filter(user=user, is_active=True).order_by("platform", "-last_seen_at", "-id")
    )
    active_platforms = sorted({device.platform for device in devices})
    return {
        "configured": is_push_configured(),
        "registered_devices_count": len(devices),
        "active_platforms": active_platforms,
        "items": [_serialize_push_device_item(device) for device in devices],
    }


def register_push_device_for_user(
    user,
    *,
    token: str,
    platform: str,
    device_id: str = "",
    device_name: str = "",
    app_version: str = "",
) -> MobilePushDevice:
    normalized_token = str(token or "").strip()
    if not normalized_token:
        raise ValueError("push token is required")
    if len(normalized_token) > 512:
        raise ValueError("push token is too long")

    normalized_platform = normalize_push_platform(platform)
    normalized_device_id = str(device_id or "").strip()[:191]
    normalized_device_name = str(device_name or "").strip()[:120]
    normalized_app_version = str(app_version or "").strip()[:40]
    now = timezone.now()

    with transaction.atomic():
        device = MobilePushDevice.objects.filter(token=normalized_token).first()
        if device is None and normalized_device_id:
            device = (
                MobilePushDevice.objects.filter(
                    user=user,
                    device_id=normalized_device_id,
                    platform=normalized_platform,
                )
                .order_by("-id")
                .first()
            )

        if device is None:
            device = MobilePushDevice.objects.create(
                user=user,
                token=normalized_token,
                platform=normalized_platform,
                device_id=normalized_device_id,
                device_name=normalized_device_name,
                app_version=normalized_app_version,
                is_active=True,
                last_error="",
            )
        else:
            device.user = user
            device.token = normalized_token
            device.platform = normalized_platform
            device.device_id = normalized_device_id
            device.device_name = normalized_device_name
            device.app_version = normalized_app_version
            device.is_active = True
            device.last_error = ""
            device.last_seen_at = now
            device.save(
                update_fields=[
                    "user",
                    "token",
                    "platform",
                    "device_id",
                    "device_name",
                    "app_version",
                    "is_active",
                    "last_error",
                    "last_seen_at",
                    "updated_at",
                ]
            )

        if normalized_device_id:
            MobilePushDevice.objects.filter(
                user=user,
                device_id=normalized_device_id,
                platform=normalized_platform,
                is_active=True,
            ).exclude(id=device.id).update(is_active=False, updated_at=now)

    return device


def deactivate_push_devices_for_user(
    user,
    *,
    token: str = "",
    device_id: str = "",
    platform: str = "",
) -> int:
    normalized_token = str(token or "").strip()
    normalized_device_id = str(device_id or "").strip()
    normalized_platform = ""
    if platform:
        normalized_platform = normalize_push_platform(platform)

    if not normalized_token and not normalized_device_id:
        raise ValueError("token or device_id is required")

    filters: dict[str, Any] = {"user": user, "is_active": True}
    if normalized_token:
        filters["token"] = normalized_token
    if normalized_device_id:
        filters["device_id"] = normalized_device_id
    if normalized_platform:
        filters["platform"] = normalized_platform

    now = timezone.now()
    return MobilePushDevice.objects.filter(**filters).update(is_active=False, updated_at=now)


def _notification_link_absolute(link_url: str) -> str:
    value = str(link_url or "").strip()
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    base = str(getattr(settings, "SITE_BASE_URL", "") or "").rstrip("/")
    if not base:
        return value
    if not value.startswith("/"):
        value = f"/{value}"
    return f"{base}{value}"


def _build_push_data(notification: SiteNotification) -> dict[str, str]:
    link = _notification_link_absolute(notification.link_url)
    data = {
        "notification_id": str(notification.id),
        "event_key": str(notification.event_key or ""),
        "title": str(notification.title or "")[:255],
        "message": str(notification.message or "")[:1000],
        "link_url": link or str(notification.link_url or ""),
        "created_at": notification.created_at.isoformat() if notification.created_at else "",
    }
    if isinstance(notification.payload, dict) and notification.payload:
        data["payload_json"] = json.dumps(notification.payload, ensure_ascii=False)[:3500]
    return data


def _build_push_request_body(notification: SiteNotification, device: MobilePushDevice) -> dict[str, Any]:
    body = {
        "message": {
            "token": device.token,
            "notification": {
                "title": str(notification.title or "")[:255],
                "body": str(notification.message or "")[:1000],
            },
            "data": _build_push_data(notification),
            "android": {
                "priority": "high",
            },
            "apns": {
                "headers": {
                    "apns-priority": "10",
                },
                "payload": {
                    "aps": {
                        "sound": "default",
                    }
                },
            },
        }
    }
    return body


def _get_fcm_access_token() -> tuple[str | None, str | None]:
    config = get_push_provider_config()
    if not config["fcm_configured"]:
        return None, str(config.get("fcm_config_error") or "FCM push provider is not configured")

    try:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account
    except ImportError as exc:
        return None, f"push auth dependency is not installed: {exc}"

    try:
        credentials = service_account.Credentials.from_service_account_info(
            config["service_account_info"],
            scopes=list(_PUSH_SCOPES),
        )
        credentials.refresh(Request())
    except Exception as exc:
        return None, str(exc)

    token = str(credentials.token or "").strip()
    if not token:
        return None, "failed to get firebase access token"
    return token, None


def _apns_device_token(value: str) -> str:
    token = re.sub(r"\s+", "", str(value or "")).strip()
    return token if _APNS_DEVICE_TOKEN_RE.fullmatch(token) else ""


def _get_apns_auth_token(apns_config: dict[str, Any]) -> tuple[str | None, str | None]:
    if not apns_config.get("configured"):
        return None, str(apns_config.get("config_error") or "APNs push provider is not configured")

    try:
        import jwt
    except ImportError as exc:
        return None, f"APNs auth dependency is not installed: {exc}"

    now = int(time.time())
    cache_key = f"{apns_config['team_id']}:{apns_config['key_id']}"
    cached = _APNS_AUTH_TOKEN_CACHE.get(cache_key)
    if cached and cached.get("expires_at", 0) > now:
        return str(cached.get("token") or ""), None

    try:
        token = jwt.encode(
            {"iss": apns_config["team_id"], "iat": now},
            apns_config["auth_key"],
            algorithm="ES256",
            headers={"kid": apns_config["key_id"]},
        )
    except Exception as exc:
        return None, str(exc)

    token = str(token or "").strip()
    if not token:
        return None, "failed to create APNs auth token"
    _APNS_AUTH_TOKEN_CACHE[cache_key] = {
        "token": token,
        "expires_at": now + _APNS_AUTH_TOKEN_TTL_SECONDS,
    }
    return token, None


def _extract_push_error_message(raw_body: str) -> str:
    raw_value = str(raw_body or "").strip()
    if not raw_value:
        return "push request failed"
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return raw_value
    if not isinstance(parsed, dict):
        return raw_value
    error = parsed.get("error")
    if not isinstance(error, dict):
        return raw_value
    status = str(error.get("status") or "").strip()
    message = str(error.get("message") or "").strip()
    if status and message:
        return f"{status}: {message}"
    if message:
        return message
    if status:
        return status
    return raw_value


def _is_terminal_push_error(message: str) -> bool:
    normalized = str(message or "").strip().lower()
    return any(marker.lower() in normalized for marker in _TERMINAL_PUSH_ERROR_MARKERS)


def _send_fcm_request(project_id: str, access_token: str, body: dict[str, Any]) -> tuple[bool, str]:
    request_body = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send",
        data=request_body,
        method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8", errors="ignore")
        return False, _extract_push_error_message(raw_body)
    except urllib.error.URLError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, str(exc)
    return True, ""


def _extract_apns_error_message(status_code: int, raw_body: str) -> str:
    raw_value = str(raw_body or "").strip()
    if not raw_value:
        return f"APNS HTTP {status_code}"
    try:
        parsed = json.loads(raw_value)
    except json.JSONDecodeError:
        return f"APNS HTTP {status_code}: {raw_value}"
    if not isinstance(parsed, dict):
        return f"APNS HTTP {status_code}: {raw_value}"
    reason = str(parsed.get("reason") or "").strip()
    timestamp = str(parsed.get("timestamp") or "").strip()
    if reason and timestamp:
        return f"APNS {reason} ({timestamp})"
    if reason:
        return f"APNS {reason}"
    return f"APNS HTTP {status_code}: {raw_value}"


def _build_apns_payload(notification: SiteNotification) -> dict[str, Any]:
    return {
        "aps": {
            "alert": {
                "title": str(notification.title or "")[:255],
                "body": str(notification.message or "")[:1000],
            },
            "sound": "default",
        },
        "data": _build_push_data(notification),
    }


def _send_apns_request(
    notification: SiteNotification,
    device: MobilePushDevice,
    apns_config: dict[str, Any],
) -> tuple[bool, str]:
    device_token = _apns_device_token(device.token)
    if not device_token:
        return False, "APNS BadDeviceToken"

    auth_token, auth_error = _get_apns_auth_token(apns_config)
    if not auth_token:
        return False, auth_error or "failed to create APNs auth token"

    try:
        import httpx
    except ImportError as exc:
        return False, f"APNs HTTP/2 dependency is not installed: {exc}"

    host = "api.sandbox.push.apple.com" if apns_config.get("use_sandbox") else "api.push.apple.com"
    url = f"https://{host}/3/device/{device_token}"
    headers = {
        "authorization": f"bearer {auth_token}",
        "apns-topic": str(apns_config.get("topic") or ""),
        "apns-push-type": "alert",
        "apns-priority": "10",
    }
    try:
        with httpx.Client(http2=True, timeout=5.0) as client:
            response = client.post(url, headers=headers, json=_build_apns_payload(notification))
    except Exception as exc:
        return False, str(exc)
    if response.status_code == 200:
        return True, ""
    return False, _extract_apns_error_message(response.status_code, response.text)


def _should_send_device_via_apns(device: MobilePushDevice, config: dict[str, Any]) -> bool:
    return (
        device.platform == "ios"
        and bool(config.get("apns_configured"))
        and bool(_apns_device_token(device.token))
    )


def send_site_notification_to_push(notification: SiteNotification) -> None:
    if not notification.is_push:
        return

    config = get_push_provider_config()
    if not config["configured"]:
        return

    devices = list(
        MobilePushDevice.objects.filter(user=notification.user, is_active=True).order_by("-last_seen_at", "-id")
    )
    if not devices:
        return

    now = timezone.now()
    sent = False
    errors: list[str] = []
    fcm_access_token: str | None = None
    fcm_access_token_error = ""
    fcm_access_token_loaded = False

    for device in devices:
        if _should_send_device_via_apns(device, config):
            ok, error_message = _send_apns_request(notification, device, config["apns"])
        else:
            if not config.get("fcm_configured"):
                ok = False
                error_message = "FCM push provider is not configured"
            else:
                if not fcm_access_token_loaded:
                    fcm_access_token, fcm_access_token_error = _get_fcm_access_token()
                    fcm_access_token_loaded = True
                if not fcm_access_token:
                    ok = False
                    error_message = fcm_access_token_error or "failed to initialize FCM push sender"
                else:
                    payload = _build_push_request_body(notification, device)
                    ok, error_message = _send_fcm_request(str(config["project_id"]), fcm_access_token, payload)
        if ok:
            sent = True
            device.last_push_sent_at = now
            device.last_error = ""
            device.save(update_fields=["last_push_sent_at", "last_error", "last_seen_at", "updated_at"])
            continue

        device.last_error = error_message
        update_fields = ["last_error", "last_seen_at", "updated_at"]
        if _is_terminal_push_error(error_message):
            device.is_active = False
            update_fields.append("is_active")
        device.save(update_fields=update_fields)
        if error_message:
            errors.append(f"{device.platform}: {error_message}")

    notification.push_error = "; ".join(errors[:3])[:2000] if errors else ""
    update_fields = ["push_error", "updated_at"]
    if sent:
        notification.push_sent_at = now
        update_fields.append("push_sent_at")
    notification.save(update_fields=update_fields)


__all__ = [
    "_serialize_push_device_item",
    "deactivate_push_devices_for_user",
    "get_push_provider_config",
    "is_push_configured",
    "normalize_push_platform",
    "register_push_device_for_user",
    "send_site_notification_to_push",
    "summarize_push_devices_for_user",
]
