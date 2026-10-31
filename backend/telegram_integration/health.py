"""Small atomic status files shared by the worker and its independent watchdog."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


class JsonStatusFile:
    def __init__(self, path):
        self.path = Path(path)

    def read(self):
        try:
            value = json.loads(self.path.read_text())
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def write(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f'{self.path.name}.{os.getpid()}.tmp')
        temporary.write_text(json.dumps(value))
        temporary.replace(self.path)


class PollingStatus:
    def __init__(self, store, clock=time.time):
        self.store, self.clock = store, clock
        self.state = {'started_at': clock(), 'phase': 'starting'}
        self.update()

    def update(self, **fields):
        self.state.update(fields, heartbeat_at=self.clock())
        self.store.write(self.state)

    def progress(self):
        # At most one write per five seconds inside a large batch.
        if self.clock() - self.state.get("progress_at", 0) >= 5:
            self.update(progress_at=self.clock())


class PollingHealth:
    """No API/SQL calls: a quiet but successful long poll is healthy too."""
    timeout = 120

    def problem(self, status, now):
        if not status:
            return 'Нет состояния процесса Telegram'
        started = status.get('started_at', now)
        if now - status.get('heartbeat_at', started) > self.timeout:
            return 'Процесс Telegram остановился или завис'
        if status.get('phase') == 'processing':
            if now - status.get('progress_at', started) > self.timeout:
                return 'Остановилась обработка сообщений Telegram'
        elif now - status.get('api_ok_at', started) > self.timeout:
            return 'Нет связи с API Telegram'
        blocked = status.get('blocked_since')
        if blocked is not None and now - blocked > self.timeout:
            return 'Повторная ошибка обработки сообщения Telegram; очередь ожидает'
        queue_error = status.get('queue_error_since')
        if queue_error is not None and now - queue_error > self.timeout:
            return 'Не работает обработка очереди согласований Telegram'
        return None


if __name__ == '__main__':
    state = JsonStatusFile(os.environ.get('TELEGRAM_STATUS_FILE', '/tmp/telegram-health/polling.json')).read()
    raise SystemExit(1 if PollingHealth().problem(state, time.time()) else 0)
