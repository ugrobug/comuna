from __future__ import annotations

import json

from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from rabotaem_backend.rate_limit import is_rate_limited
from telegram_integration import serializers as telegram_serializers
from telegram_integration.bot import (
    _handle_callback_query,
    _handle_channel_post,
    _handle_my_chat_member,
    _handle_private_message,
)
from telegram_integration.service import (
    build_telegram_login_redirect_html,
    telegram_login_will_create_new_user,
    telegram_payload_from_oidc_claims,
    upsert_telegram_account,
    validate_telegram_login,
    validate_telegram_oidc_token,
)
User = get_user_model()
_PRIVACY_CONSENT_ERROR = "Для регистрации нужно согласиться с политикой обработки персональных данных."
_OAUTH_ACCOUNT_NOT_FOUND_ERROR = "Аккаунт не найден. Перейдите на вкладку регистрации."


def _user_service():
    from users import service as user_service

    return user_service


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


@csrf_exempt
def telegram_auth(request: HttpRequest) -> HttpResponse:
    if is_rate_limited(request, scope="auth_telegram", limit=20, window_seconds=300):
        return JsonResponse(
            {"ok": False, "error": "Слишком много попыток. Попробуйте позже."},
            status=429,
        )
    if request.method == "GET":
        payload = dict(request.GET.items())
    elif request.method == "POST":
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            return JsonResponse({"ok": False, "error": "invalid json"}, status=400)
    else:
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        if payload.get("id_token"):
            claims = validate_telegram_oidc_token(payload.get("id_token"))
            payload = {
                **telegram_payload_from_oidc_claims(claims),
                "auth_intent": payload.get("auth_intent"),
                "privacy_accepted": payload.get("privacy_accepted"),
            }
        else:
            validate_telegram_login(payload)
        if telegram_login_will_create_new_user(payload):
            if not _is_registration_intent(payload):
                return JsonResponse({"ok": False, "error": _OAUTH_ACCOUNT_NOT_FOUND_ERROR}, status=404)
            if not _is_privacy_accepted(payload.get("privacy_accepted")):
                return JsonResponse({"ok": False, "error": _PRIVACY_CONSENT_ERROR}, status=400)
        user = upsert_telegram_account(payload)
    except ValueError as exc:
        return JsonResponse({"ok": False, "error": str(exc)}, status=400)

    user_service = _user_service()
    token = user_service._issue_token(user, request)
    if request.method == "GET":
        next_url = request.GET.get("next") or "/"
        html = build_telegram_login_redirect_html(token, next_url)
        response = HttpResponse(html, content_type="text/html")
        user_service._set_auth_cookie(response, token)
        return response
    response = JsonResponse(telegram_serializers._serialize_telegram_auth_response(user, token))
    user_service._set_auth_cookie(response, token)
    return response


@csrf_exempt
def telegram_webhook(request: HttpRequest, token: str) -> HttpResponse:
    expected_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected_secret:
        return JsonResponse({"ok": False, "error": "TELEGRAM_WEBHOOK_SECRET not set"}, status=500)

    if token != expected_secret:
        return JsonResponse({"ok": False, "error": "invalid token"}, status=403)

    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if header_secret != expected_secret:
        return JsonResponse({"ok": False, "error": "invalid secret"}, status=403)

    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid json"}, status=400)

    if "channel_post" in payload:
        _handle_channel_post(payload["channel_post"])
    elif "edited_channel_post" in payload:
        _handle_channel_post(payload["edited_channel_post"])
    elif "my_chat_member" in payload:
        _handle_my_chat_member(payload["my_chat_member"])
    elif "message" in payload:
        _handle_private_message(payload["message"])
    elif "callback_query" in payload:
        _handle_callback_query(payload["callback_query"])

    return JsonResponse({"ok": True})


__all__ = ["telegram_auth", "telegram_webhook"]
