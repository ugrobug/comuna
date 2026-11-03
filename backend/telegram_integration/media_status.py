"""Queue observability without exposing message content or credentials."""
import time
from telegram_integration.models import TelegramMediaJob


class TelegramMediaStatus:
    def __init__(self, store):
        self.store = store

    def update(self, error=None, processing=False):
        oldest = (TelegramMediaJob.objects.filter(state='pending').order_by('created_at')
                  .values_list('created_at', flat=True).first())
        previous = self.store.read()
        self.store.write({
            'heartbeat_at': time.time(), 'processing': processing,
            'pending_since': oldest.timestamp() if oldest else None,
            'failed': TelegramMediaJob.objects.filter(state='failed').exists(),
            'error': error if error is not None else previous.get('error') if oldest else None,
        })

    def heartbeat(self):
        state = self.store.read()
        if time.time() - state.get('heartbeat_at', 0) >= 5:
            self.store.write({**state, 'heartbeat_at': time.time()})

    @staticmethod
    def problem(state, now):
        if not state:
            return 'Нет состояния загрузчика фотографий Telegram'
        if now - state.get('heartbeat_at', 0) > 720:
            return 'Загрузчик фотографий Telegram остановился или завис'
        if state.get('failed'):
            return 'Некоторые фотографии Telegram исчерпали повторы; требуется проверка очереди'
        pending = state.get('pending_since')
        if pending and now - pending > 120 and state.get('error'):
            return 'Фотографии Telegram ожидают загрузки; текстовые публикации продолжаются'
        return None
