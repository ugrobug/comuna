from __future__ import annotations

import hashlib
import hmac
import json
import re
import urllib.error
import urllib.parse
import urllib.request

import jwt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from jwt import PyJWKClient
from jwt import PyJWTError

from notifications.models import SiteNotification
from telegram_integration.models import TelegramAccount

User = get_user_model()
_oidc_jwks_client: PyJWKClient | None = None

_TELEGRAM_LOGIN_FIELDS = {
    "id",
    "first_name",
    "last_name",
    "username",
    "photo_url",
    "auth_date",
}


def verify_telegram_login(payload: dict) -> tuple[bool, str | None]:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        return False, "telegram auth disabled"
    provided_hash = payload.get("hash")
    if not provided_hash:
        return False, "missing hash"
    data = {
        k: v
        for k, v in payload.items()
        if k in _TELEGRAM_LOGIN_FIELDS and v is not None
    }
    auth_date_raw = data.get("auth_date")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError):
        return False, "invalid auth date"
    now_ts = int(timezone.now().timestamp())
    if now_ts - auth_date > 60 * 60 * 24:
        return False, "auth expired"
    for key, value in list(data.items()):
        data[key] = str(value)
    data_check_string = "\n".join(f"{key}={data[key]}" for key in sorted(data.keys()))
    secret_key = hashlib.sha256(token.encode("utf-8")).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    if computed_hash != provided_hash:
        return False, "invalid hash"
    return True, None


def _normalize_phone(value: object) -> str:
    phone = re.sub(r"\D+", "", str(value or ""))
    if len(phone) < 7:
        return ""
    return f"+{phone}"


def _split_full_name(value: object) -> tuple[str, str]:
    full_name = str(value or "").strip()
    if not full_name:
        return "", ""
    parts = full_name.split(" ", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _find_user_by_phone(phone: str) -> User | None:
    phone = _normalize_phone(phone)
    if not phone:
        return None
    from users.models import SiteUserProfile

    profile = (
        SiteUserProfile.objects.select_related("user")
        .filter(phone=phone)
        .order_by("id")
        .first()
    )
    return profile.user if profile else None


def _remember_user_phone(user: User, phone: str) -> None:
    phone = _normalize_phone(phone)
    if not phone:
        return
    from users.models import SiteUserProfile

    profile, _ = SiteUserProfile.objects.get_or_create(user=user)
    if not profile.phone:
        profile.phone = phone
        profile.save(update_fields=["phone", "updated_at"])


def _telegram_oidc_client_id() -> str:
    return str(getattr(settings, "TELEGRAM_OIDC_CLIENT_ID", "") or "").strip()


def _telegram_oidc_jwks_client() -> PyJWKClient:
    global _oidc_jwks_client
    jwks_url = str(
        getattr(settings, "TELEGRAM_OIDC_JWKS_URL", "")
        or "https://oauth.telegram.org/.well-known/jwks.json"
    )
    if _oidc_jwks_client is None or _oidc_jwks_client.uri != jwks_url:
        _oidc_jwks_client = PyJWKClient(jwks_url)
    return _oidc_jwks_client


def validate_telegram_oidc_token(id_token: str) -> dict:
    token = str(id_token or "").strip()
    if not token:
        raise ValueError("missing Telegram id_token")
    client_id = _telegram_oidc_client_id()
    if not client_id:
        raise ValueError("telegram OIDC auth disabled")

    try:
        signing_key = _telegram_oidc_jwks_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            audience=client_id,
            issuer=getattr(settings, "TELEGRAM_OIDC_ISSUER", "https://oauth.telegram.org"),
            algorithms=["RS256"],
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
        )
    except PyJWTError as exc:
        raise ValueError("invalid Telegram id_token") from exc

    telegram_id = claims.get("id") or claims.get("sub")
    try:
        claims["id"] = int(telegram_id)
    except (TypeError, ValueError):
        raise ValueError("invalid Telegram id_token") from None
    return claims


def telegram_payload_from_oidc_claims(claims: dict) -> dict:
    first_name = (claims.get("given_name") or "").strip()
    last_name = (claims.get("family_name") or "").strip()
    if not first_name:
        first_name, last_name = _split_full_name(claims.get("name"))
    return {
        "id": claims.get("id"),
        "first_name": first_name,
        "last_name": last_name,
        "username": (claims.get("preferred_username") or "").strip(),
        "photo_url": (claims.get("picture") or "").strip(),
        "phone": _normalize_phone(claims.get("phone_number")),
    }


def generate_unique_username(base: str, suffix: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]", "_", base).strip("_")
    if not base:
        base = "user"
    candidate = base
    if User.objects.filter(username__iexact=candidate).exists():
        candidate = f"{base}_{suffix}"
    if User.objects.filter(username__iexact=candidate).exists():
        candidate = f"tg_{suffix}"
    return candidate[:150]


def validate_telegram_login(payload: dict) -> None:
    ok, error_message = verify_telegram_login(payload)
    if not ok:
        raise ValueError(error_message or "invalid telegram auth")


def upsert_telegram_account(payload: dict):
    try:
        telegram_id = int(payload.get("id"))
    except (TypeError, ValueError):
        raise ValueError("invalid telegram id") from None

    username = (payload.get("username") or "").strip()
    first_name = (payload.get("first_name") or "").strip()
    last_name = (payload.get("last_name") or "").strip()
    avatar_url = (payload.get("photo_url") or "").strip()
    phone = _normalize_phone(payload.get("phone") or payload.get("phone_number"))

    account = TelegramAccount.objects.select_related("user").filter(telegram_id=telegram_id).first()
    if account:
        user = account.user
    else:
        user = _find_user_by_phone(phone)
        if user:
            updates: list[str] = []
            if first_name and not user.first_name:
                user.first_name = first_name
                updates.append("first_name")
            if last_name and not user.last_name:
                user.last_name = last_name
                updates.append("last_name")
            if updates:
                user.save(update_fields=updates)
        else:
            base_username = username or (first_name or "tg")
            candidate = generate_unique_username(base_username, str(telegram_id))
            user = User.objects.create_user(username=candidate)
            user.set_unusable_password()
            if first_name:
                user.first_name = first_name
            if last_name:
                user.last_name = last_name
            user.save(update_fields=["password", "first_name", "last_name"])
        account = TelegramAccount.objects.create(
            user=user,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
        )

    _remember_user_phone(user, phone)
    account.username = username
    account.first_name = first_name
    account.last_name = last_name
    account.avatar_url = avatar_url
    account.save(update_fields=["username", "first_name", "last_name", "avatar_url", "updated_at"])
    return user


def telegram_login_will_create_new_user(payload: dict) -> bool:
    try:
        telegram_id = int(payload.get("id"))
    except (TypeError, ValueError):
        return True
    if TelegramAccount.objects.filter(telegram_id=telegram_id).exists():
        return False
    phone = _normalize_phone(payload.get("phone") or payload.get("phone_number"))
    return _find_user_by_phone(phone) is None


def build_telegram_login_redirect_html(token: str, next_url: str) -> str:
    next_literal = json.dumps(next_url or "/")
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<title>Telegram login</title></head><body>"
        "<script>"
        f"try{{localStorage.setItem('comuna.site.token','{token}');}}catch(e){{}}"
        f"window.location.replace({next_literal});"
        "</script>"
        "</body></html>"
    )


def notification_link_absolute(link_url: str) -> str:
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


def send_site_notification_to_telegram(notification: SiteNotification) -> None:
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
    link = notification_link_absolute(notification.link_url)
    if link:
        parts.append(link)
    text = "\n\n".join([part for part in parts if part]).strip()
    if not text:
        return

    payload = urllib.parse.urlencode(
        {"chat_id": str(account.telegram_id), "text": text[:4096]}
    ).encode("utf-8")
    if not payload:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        request = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            json.loads(response.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        notification.telegram_error = str(exc)
        notification.save(update_fields=["telegram_error", "updated_at"])
        return
    except Exception as exc:
        notification.telegram_error = str(exc)
        notification.save(update_fields=["telegram_error", "updated_at"])
        return

    notification.telegram_sent_at = timezone.now()
    notification.telegram_error = ""
    notification.save(update_fields=["telegram_sent_at", "telegram_error", "updated_at"])


__all__ = [
    "build_telegram_login_redirect_html",
    "generate_unique_username",
    "notification_link_absolute",
    "send_site_notification_to_telegram",
    "telegram_login_will_create_new_user",
    "telegram_payload_from_oidc_claims",
    "upsert_telegram_account",
    "validate_telegram_login",
    "validate_telegram_oidc_token",
    "verify_telegram_login",
]
