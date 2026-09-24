from __future__ import annotations

import fcntl
import logging
import os
import threading
import time
from typing import Any

from django.conf import settings

from telegram_integration.bot import (
    _fetch_telegram_json,
    _handle_callback_query,
    _handle_channel_post,
    _handle_inline_query,
    _handle_message,
    _handle_my_chat_member,
)

logger = logging.getLogger(__name__)

_polling_started = False
_polling_lock_handle = None


class TelegramUpdateProcessor:
    """Advance the polling cursor only after the current update succeeds."""

    def __init__(self):
        self.offset: int | None = None

    def process(self, updates):
        handlers = {
            "channel_post": _handle_channel_post,
            "edited_channel_post": _handle_channel_post,
            "message": _handle_message,
            "callback_query": _handle_callback_query,
            "my_chat_member": _handle_my_chat_member,
            "inline_query": _handle_inline_query,
        }
        for update in updates:
            update_id = update.get("update_id")
            if isinstance(update_id, int) and self.offset is not None and update_id < self.offset:
                continue
            for kind, handler in handlers.items():
                if kind in update:
                    handler(update[kind])
                    break
            if isinstance(update_id, int):
                self.offset = update_id + 1


def _acquire_polling_lock() -> bool:
    global _polling_lock_handle
    if _polling_lock_handle is not None:
        return True

    lock_path = os.environ.get("TELEGRAM_POLLING_LOCK_FILE", "/tmp/tambur-telegram-polling.lock")
    handle = open(lock_path, "w")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return False
    _polling_lock_handle = handle
    return True


def _polling_loop(token: str) -> None:
    processor = TelegramUpdateProcessor()
    print("Telegram polling started")
    _fetch_telegram_json("deleteWebhook", token, {"drop_pending_updates": False})
    while True:
        try:
            payload: dict[str, Any] = {
                "timeout": 25,
                "allowed_updates": (
                    '["channel_post","edited_channel_post","message",'
                    '"callback_query","my_chat_member","inline_query"]'
                ),
            }
            if processor.offset is not None:
                payload["offset"] = processor.offset
            response = _fetch_telegram_json("getUpdates", token, payload)
            if not response or not response.get("ok"):
                time.sleep(2)
                continue

            updates = response.get("result") or []
            if updates:
                print(f"Telegram polling received {len(updates)} updates")
            processor.process(updates)
        except Exception as exc:
            logger.warning("Telegram update failed; cursor retained (error=%s)", type(exc).__name__)
            time.sleep(2)


def start_polling_thread() -> None:
    global _polling_started
    if _polling_started:
        return
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set; polling disabled.")
        return
    if not _acquire_polling_lock():
        logger.info("Telegram polling already started in another process; skipping.")
        return
    _polling_started = True
    print("Starting Telegram polling thread")
    thread = threading.Thread(target=_polling_loop, args=(token,), daemon=True)
    thread.start()


__all__ = ["start_polling_thread"]
