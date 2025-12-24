from __future__ import annotations

import logging
import threading
import time
from typing import Any

from django.conf import settings

from .views import _fetch_telegram_json, _handle_channel_post, _handle_private_message

logger = logging.getLogger(__name__)

_polling_started = False


def _polling_loop(token: str) -> None:
    offset: int | None = None
    _fetch_telegram_json("deleteWebhook", token, {"drop_pending_updates": True})
    while True:
        payload: dict[str, Any] = {
            "timeout": 25,
            "allowed_updates": ["channel_post", "edited_channel_post", "message"],
        }
        if offset is not None:
            payload["offset"] = offset
        response = _fetch_telegram_json("getUpdates", token, payload)
        if not response or not response.get("ok"):
            time.sleep(2)
            continue

        updates = response.get("result") or []
        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int):
                offset = update_id + 1
            if "channel_post" in update:
                _handle_channel_post(update["channel_post"])
            elif "edited_channel_post" in update:
                _handle_channel_post(update["edited_channel_post"])
            elif "message" in update:
                _handle_private_message(update["message"])


def start_polling_thread() -> None:
    global _polling_started
    if _polling_started:
        return
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; polling disabled.")
        return
    _polling_started = True
    thread = threading.Thread(target=_polling_loop, args=(token,), daemon=True)
    thread.start()
