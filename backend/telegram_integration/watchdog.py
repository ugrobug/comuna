"""Independent, persisted per-channel alerts; no user content or credentials in state."""
import logging
import time

from telegram_integration.health import PollingHealth

logger = logging.getLogger(__name__)


class TelegramWatchdog:
    def __init__(self, status, state, senders, clock=time.time, media_status=None, storage_status=None):
        self.status, self.store, self.senders, self.clock = status, state, senders, clock
        self.media_status = media_status
        self.storage_status = storage_status
        self.state = state.read()
        self.state.setdefault('started_at', clock())
        self.state.setdefault('channels', {})

    def check(self):
        now = self.clock()
        snapshot = self.status.read()
        problem = PollingHealth().problem(snapshot, now)
        if problem is None and self.media_status is not None:
            from telegram_integration.media_status import TelegramMediaStatus
            problem = TelegramMediaStatus.problem(self.media_status.read(), now)
        if problem is None and self.storage_status is not None:
            from media_storage.status import MediaReserveStatus
            problem = MediaReserveStatus.problem(self.storage_status.read(), now)
        if not snapshot and now - self.state['started_at'] < 120:
            self.store.write(self.state)
            return
        if problem is None and (not snapshot.get('cycle_ok_at') or snapshot.get('error')
                                or snapshot.get('blocked_since') is not None
                                or snapshot.get('queue_error_since') is not None):
            # A restarted process or a new transient error is not a recovery.
            return
        for channel, send in self.senders.items():
            delivery = self.state['channels'].setdefault(channel, {})
            previous = delivery.get('problem')
            if problem is None and previous is None:
                continue
            # Failed channels retry independently once per minute. A delivered
            # outage repeats hourly; recovery is sent only to notified channels.
            if now < delivery.get('retry_at', 0):
                continue
            if problem == previous and now - delivery.get('sent_at', 0) < 3600:
                continue
            text = (f'Тамбур: требуется внимание. {problem}. '
                    'Автоматические повторы продолжаются. Требуется проверить связь и очередь.'
                    if problem else
                    'Тамбур: приём сообщений и загрузка изображений снова работают; очереди медиа восстановлены. '
                    'Проверьте публикации за время сбоя: Telegram хранит ожидающие обновления ограниченное время.')
            try:
                send(text)
            except Exception as error:
                delivery['retry_at'] = now + 60
                logger.error('Telegram watchdog delivery failed (channel=%s, error=%s)', channel, type(error).__name__)
            else:
                delivery.update(problem=problem, sent_at=now, retry_at=0)
            self.store.write(self.state)


class EmailAlertSender:
    def __init__(self, recipient):
        self.recipient = recipient

    def __call__(self, text):
        from django.core.mail import get_connection, send_mail
        count = send_mail('Тамбур: состояние Telegram-бота', text, None, [self.recipient],
                          connection=get_connection(timeout=10), fail_silently=False)
        if count != 1:
            raise RuntimeError('Mail delivery was not accepted')


class MaxAlertSender:
    def __init__(self, client, chat_id):
        self.client, self.chat_id = client, chat_id

    def __call__(self, text):
        self.client.send(self.chat_id, text)
