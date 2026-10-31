from __future__ import annotations

import fcntl
import logging
import os
import threading
import time

from django.conf import settings
from django.db import close_old_connections

from telegram_integration.bot import (
    _fetch_telegram_json,
    _send_bot_message_with_keyboard,
    _handle_callback_query,
    _handle_channel_post,
    _handle_inline_query,
    _handle_message,
    _handle_my_chat_member,
)

from telegram_integration.moderation import TelegramApprovalPrompt
from telegram_integration.health import JsonStatusFile, PollingStatus
from telegram_integration.runtime import TelegramPollingRuntime

logger = logging.getLogger(__name__)

_polling_started = False
_polling_lock_handle = None


class TelegramUpdateProcessor:
    """Advance the polling cursor only after the current update succeeds."""

    def __init__(self, on_progress=None):
        self.on_progress = on_progress
        self.offset: int | None = None
        self._completed_decisions: set[int] = set()

    def process(self, updates):
        # Consent must not wait behind a channel's failing photo download.
        # Acknowledgement still advances only through the original ordered batch.
        decision_errors = {}
        for update in updates:
            update_id = update.get("update_id")
            callback = update.get("callback_query") or {}
            if (not isinstance(update_id, int)
                    or (self.offset is not None and update_id < self.offset)
                    or update_id in self._completed_decisions
                    or not str(callback.get("data", "")).startswith(("approve:", "reject:"))):
                continue
            try:
                _handle_callback_query(callback)
            except Exception as error:
                decision_errors[update_id] = error
            else:
                self._completed_decisions.add(update_id)
                if self.on_progress:
                    self.on_progress()
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
            if update_id in decision_errors:
                raise decision_errors[update_id]
            if update_id not in self._completed_decisions:
                for kind, handler in handlers.items():
                    if kind in update:
                        handler(update[kind])
                        break
            if isinstance(update_id, int):
                self.offset = update_id + 1
                if self.on_progress:
                    self.on_progress()
                self._completed_decisions = {key for key in self._completed_decisions if key >= self.offset}


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


def _polling_loop(token: str, stop=None) -> None:
    status = PollingStatus(JsonStatusFile(os.environ.get(
        "TELEGRAM_STATUS_FILE", "/tmp/telegram-health/polling.json")))
    runtime = TelegramPollingRuntime(
        token, _fetch_telegram_json, TelegramUpdateProcessor(status.progress),
        TelegramApprovalPrompt(_send_bot_message_with_keyboard), status)
    logger.info("Telegram polling started")
    while stop is None or not stop.is_set():
        close_old_connections()
        delay = runtime.step()
        if delay:
            if stop is None:
                time.sleep(delay)
            else:
                stop.wait(delay)


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
