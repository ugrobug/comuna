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
    print("Telegram polling started")
    _fetch_telegram_json("deleteWebhook", token, {"drop_pending_updates": True})
    while True:
        try:
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
            if updates:
                print(f"Telegram polling received {len(updates)} updates")
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
        except Exception as exc:
            print(f"Telegram polling error: {exc}")
            time.sleep(2)


def start_polling_thread() -> None:
    global _polling_started
    if _polling_started:
        return
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; polling disabled.")
        return
    _polling_started = True
    print("Starting Telegram polling thread")
    thread = threading.Thread(target=_polling_loop, args=(token,), daemon=True)
    thread.start()
