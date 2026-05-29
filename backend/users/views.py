from __future__ import annotations

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from rabotaem_backend.rate_limit import is_rate_limited
from telegram_integration import views as telegram_views
from users import serializers as user_serializers
from users import service as user_service

User = get_user_model()

_PRIVACY_CONSENT_ERROR = "Для регистрации нужно согласиться с политикой обработки персональных данных."

_get_user_from_request = user_service._get_user_from_request
_get_user_from_token = user_service._get_user_from_token
_issue_token = user_service._issue_token
_public_user_author_ids = user_service._public_user_author_ids
_serialize_public_site_user_author_card = user_serializers._serialize_public_site_user_author_card
_serialize_public_site_user_profile = user_serializers._serialize_public_site_user_profile
_serialize_user = user_serializers._serialize_user


def _is_privacy_accepted(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"1", "true", "yes", "on", "accepted"}
    return False


def _is_registration_intent(payload: dict) -> bool:
    raw_intent = payload.get("auth_intent") or payload.get("intent") or payload.get("mode")
    intent = str(raw_intent or "").strip().lower()
    if intent in {"signup", "register", "registration"}:
        return True
    if intent in {"login", "auth", "signin", "sign_in"}:
        return False
    return _is_privacy_accepted(payload.get("privacy_accepted"))


def _auth_success_response(user: User, request: HttpRequest, extra: dict | None = None) -> JsonResponse:
    token = _issue_token(user, request)
    payload = {"ok": True, "token": token, "user": _serialize_user(user)}
    if extra:
        payload.update(extra)
    response = JsonResponse(payload)
    user_service._set_auth_cookie(response, token)
    return response


def _rate_limit_response() -> JsonResponse:
    return JsonResponse(
        {"ok": False, "error": "Слишком много попыток. Попробуйте позже."},
        status=429,
    )


@csrf_exempt
def register_user(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if is_rate_limited(request, scope="auth_register", limit=5, window_seconds=300):
        return _rate_limit_response()
    if not getattr(settings, "ALLOW_PASSWORD_REGISTRATION", False):
        return JsonResponse(
            {"ok": False, "error": "Регистрация по почте отключена. Используйте Telegram."},
            status=403,
        )
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    email = (payload.get("email") or "").strip()
    if not _is_privacy_accepted(payload.get("privacy_accepted")):
        return JsonResponse({"ok": False, "error": _PRIVACY_CONSENT_ERROR}, status=400)
    try:
        user = user_service._register_password_user(username, password, email)
    except ValueError as exc:
        status = 403 if not getattr(settings, "ALLOW_PASSWORD_REGISTRATION", False) else 400
        return JsonResponse({"ok": False, "error": str(exc)}, status=status)
    user_service._remember_registration_source(
        user,
        payload.get("registration_source"),
        payload.get("registration_path"),
    )
    email_sent = user_service._send_registration_email(user)
    return _auth_success_response(user, request, {"email_sent": email_sent})


@csrf_exempt
def login_user(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    username_or_email = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if is_rate_limited(
        request,
        scope="auth_login",
        limit=10,
        window_seconds=300,
        identifiers=(username_or_email.lower(),),
    ):
        return _rate_limit_response()
    try:
        user = user_service._authenticate_password_user(username_or_email, password)
    except ValueError as exc:
        status = 400 if "Введите email" in str(exc) else 401
        return JsonResponse({"ok": False, "error": str(exc)}, status=status)

    return _auth_success_response(user, request)


@csrf_exempt
def password_reset_request(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if is_rate_limited(request, scope="auth_password_reset", limit=5, window_seconds=300):
        return _rate_limit_response()
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    try:
        user_service._request_password_reset((payload.get("email") or "").strip())
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({"ok": True})


@csrf_exempt
def verify_email(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        secret = request.GET.get("token", "")
    elif request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
        secret = str(payload.get("token") or "")
    else:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        user = user_service._verify_email_by_secret(secret)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return JsonResponse({"ok": True, "user": _serialize_user(user)})


@csrf_exempt
def password_reset_confirm(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if is_rate_limited(request, scope="auth_password_reset_confirm", limit=10, window_seconds=300):
        return _rate_limit_response()
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    password = payload.get("password") or ""
    try:
        user = user_service._reset_password_by_token(
            str(payload.get("uid") or ""),
            str(payload.get("token") or ""),
            password,
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return _auth_success_response(user, request)


@csrf_exempt
def auth_me(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method == "GET":
        return JsonResponse({"ok": True, "user": _serialize_user(user)})
    if request.method not in ("PATCH", "POST"):
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    display_name = payload.get("display_name")
    avatar_url = payload.get("avatar_url")
    email = payload.get("email") if "email" in payload else None
    try:
        user, email_verification_sent = user_service._update_site_profile(
            user,
            display_name=display_name,
            avatar_url=avatar_url,
            email=email,
        )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)
    return JsonResponse(
        {
            "ok": True,
            "user": _serialize_user(user),
            "email_verification_sent": email_verification_sent,
        }
    )


@csrf_exempt
def logout_user(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    user_service._revoke_request_tokens(request)
    response = JsonResponse({"ok": True})
    user_service._clear_auth_cookie(response)
    return response


def public_user_profile(request: HttpRequest, user_id: int) -> HttpResponse:
    if request.method != "GET":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    limit_raw = request.GET.get("limit", "10")
    offset_raw = request.GET.get("offset", "0")
    try:
        limit = min(max(int(limit_raw), 1), 100)
    except ValueError:
        limit = 10
    try:
        offset = max(int(offset_raw), 0)
    except ValueError:
        offset = 0

    profile_user = (
        User.objects.filter(id=user_id)
        .select_related("site_profile", "telegram_account", "vk_account")
        .first()
    )
    if not profile_user:
        return JsonResponse({"ok": False, "error": "user not found"}, status=404)

    payload = user_service._build_public_user_profile_payload(
        request,
        profile_user,
        current_user=_get_user_from_request(request),
        limit=limit,
        offset=offset,
    )
    return JsonResponse(payload)


@csrf_exempt
def author_verification_code(request: HttpRequest) -> HttpResponse:
    user = _get_user_from_request(request)
    if not user:
        return JsonResponse({"ok": False, "error": "unauthorized"}, status=401)
    if request.method not in {"GET", "POST"}:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    return JsonResponse({"ok": True, "code": user_service._issue_author_verification_code(user)})


@csrf_exempt
def vk_auth(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)
    if is_rate_limited(request, scope="auth_vk", limit=20, window_seconds=300):
        return _rate_limit_response()
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    try:
        vk_user = user_service._authenticate_vk_payload(payload)
        current_user = _get_user_from_request(request)
        creates_new_user = (
            user_service._vk_login_will_create_new_user(vk_user)
            and not current_user
            and _is_registration_intent(payload)
        )
        if creates_new_user and not _is_privacy_accepted(payload.get("privacy_accepted")):
            return JsonResponse({"ok": False, "error": _PRIVACY_CONSENT_ERROR}, status=400)
        user = user_service._upsert_vk_account(vk_user, link_user=current_user)
        if creates_new_user:
            user_service._remember_registration_source(
                user,
                payload.get("registration_source"),
                payload.get("registration_path"),
            )
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    return _auth_success_response(user, request)


telegram_auth = telegram_views.telegram_auth


__all__ = [
    "_get_user_from_request",
    "_get_user_from_token",
    "_issue_token",
    "_public_user_author_ids",
    "_serialize_public_site_user_author_card",
    "_serialize_public_site_user_profile",
    "_serialize_user",
    "auth_me",
    "author_verification_code",
    "login_user",
    "logout_user",
    "password_reset_confirm",
    "password_reset_request",
    "public_user_profile",
    "register_user",
    "telegram_auth",
    "verify_email",
    "vk_auth",
]
