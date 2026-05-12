from __future__ import annotations

from telegram_integration.media import safe_public_url
from telegram_integration.models import TelegramAccount


def _user_serializers():
    from users import serializers as user_serializers

    return user_serializers


def _serialize_telegram_account(account: TelegramAccount | None) -> dict | None:
    if not account:
        return None
    return {
        "telegram_id": account.telegram_id,
        "username": account.username,
        "first_name": account.first_name,
        "last_name": account.last_name,
        "avatar_url": safe_public_url(account.avatar_url),
    }


def _serialize_telegram_auth_response(user, token: str) -> dict:
    account = TelegramAccount.objects.filter(user=user).first()
    return {
        "ok": True,
        "token": token,
        "user": _user_serializers()._serialize_user(user),
        "telegram": _serialize_telegram_account(account),
    }


__all__ = [
    "_serialize_telegram_account",
    "_serialize_telegram_auth_response",
]
