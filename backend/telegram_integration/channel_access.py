from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable


class TelegramAccessCheckUnavailable(RuntimeError):
    """An unverified permission check must not acknowledge a channel update."""


class TelegramChannelAccessVerifier:
    """Distinguish confirmed missing permissions from a retryable API failure."""

    def __init__(self, token: str, bot_id_provider: Callable[[], int | None], *, opener=urllib.request.urlopen):
        self.token = token
        self.bot_id_provider = bot_id_provider
        self.opener = opener

    def is_admin(self, chat_id: int) -> bool:
        bot_id = self.bot_id_provider()
        if not bot_id:
            raise TelegramAccessCheckUnavailable("Bot identity check unavailable")
        try:
            with self.opener(
                f"https://api.telegram.org/bot{self.token}/getChatMember",
                data=urllib.parse.urlencode({"chat_id": chat_id, "user_id": bot_id}).encode(),
                timeout=5,
            ) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read())
            except (ValueError, OSError):
                raise TelegramAccessCheckUnavailable("Invalid Telegram error response") from None
        except (OSError, ValueError):
            # Never include the request URL, which contains the bot token.
            raise TelegramAccessCheckUnavailable("Telegram permission check unavailable") from None

        if not isinstance(payload, dict):
            raise TelegramAccessCheckUnavailable("Invalid Telegram permission response")
        if not payload.get("ok"):
            if payload.get("error_code") in {400, 403}:
                return False
            raise TelegramAccessCheckUnavailable("Telegram permission check failed")
        result = payload.get("result")
        status = result.get("status") if isinstance(result, dict) else None
        if status in {"administrator", "creator"}:
            return True
        if status in {"member", "restricted", "left", "kicked"}:
            return False
        raise TelegramAccessCheckUnavailable("Incomplete Telegram membership response")
