"""Retryable polling lifecycle, independent of web worker lifetime."""
import logging
import time

logger = logging.getLogger(__name__)


class TelegramPollingRuntime:
    def __init__(self, token, fetch, processor, approvals, status, clock=time.time):
        self.token, self.fetch, self.processor = token, fetch, processor
        self.approvals, self.status, self.clock = approvals, status, clock
        self.initialized = False
        self.failures = 0
        self.last_log = None
        self.blocked_offset = None

    def request(self, method, payload):
        result = self.fetch(method, self.token, payload)
        if not isinstance(result, dict) or not result.get('ok'):
            raise ConnectionError('Telegram API unavailable')
        return result

    def step(self):
        self.status.update(phase='polling')
        try:
            if not self.initialized:
                self.request('deleteWebhook', {'drop_pending_updates': False})
                self.initialized = True
            payload = {'timeout': 25, 'limit': 100, 'allowed_updates':
                       '["channel_post","edited_channel_post","message","callback_query","my_chat_member","inline_query"]'}
            if self.processor.offset is not None:
                payload['offset'] = self.processor.offset
            result = self.request('getUpdates', payload)
            self.status.update(api_ok_at=self.clock(), phase='processing', progress_at=self.clock())
            updates = result.get('result') or []
            try:
                self.processor.process(updates)
            except Exception:
                # A different failed update starts a new observation window.
                if self.blocked_offset != self.processor.offset or self.status.state.get('blocked_since') is None:
                    self.blocked_offset = self.processor.offset
                    self.status.update(blocked_since=self.clock())
                raise
            self.status.update(blocked_since=None, phase='idle', error=None,
                               cycle_ok_at=self.clock(), last_batch_size=len(updates))
            self.failures = 0
            self.last_log = None
            # Never let a DB/delivery failure prevent receiving new updates.
            try:
                self.approvals.drain(limit=2)
            except Exception as error:
                self.status.update(queue_error_since=self.status.state.get('queue_error_since') or self.clock())
                logger.warning('Telegram approval queue failed (error=%s)', type(error).__name__)
            else:
                self.status.update(queue_error_since=None)
            return 0
        except Exception as error:
            self.failures += 1
            self.status.update(phase='retrying', error=type(error).__name__)
            now = self.clock()
            if self.last_log is None or now - self.last_log >= 60:
                logger.warning('Telegram polling failed; cursor retained (error=%s, attempts=%s)',
                               type(error).__name__, self.failures)
                self.last_log = now
            return min(30, 2 ** min(self.failures, 5))
