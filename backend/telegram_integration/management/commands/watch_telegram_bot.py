import os
import signal
import threading

from django.core.management.base import BaseCommand, CommandError
from max_integration.client import MaxClient
from telegram_integration.health import JsonStatusFile
from telegram_integration.watchdog import EmailAlertSender, MaxAlertSender, TelegramWatchdog


class Command(BaseCommand):
    help = 'Watch Telegram status and notify configured MAX/email recipients independently.'

    def build_senders(self, environment):
        email = environment.get('TELEGRAM_ALERT_EMAIL', '').strip()
        chat = environment.get('TELEGRAM_ALERT_MAX_CHAT_ID', '').strip()
        senders = {}
        if email:
            senders['email'] = EmailAlertSender(email)
        if chat:
            try:
                chat_id = int(chat)
            except ValueError as error:
                raise CommandError('TELEGRAM_ALERT_MAX_CHAT_ID must be an integer') from error
            senders['max'] = MaxAlertSender(MaxClient(), chat_id)
        if not senders:
            raise CommandError('Configure TELEGRAM_ALERT_EMAIL or TELEGRAM_ALERT_MAX_CHAT_ID')
        return senders

    def handle(self, *args, **options):
        watchdog = TelegramWatchdog(
            JsonStatusFile(os.environ.get('TELEGRAM_STATUS_FILE', '/tmp/telegram-health/polling.json')),
            JsonStatusFile(os.environ.get('TELEGRAM_ALERT_STATE_FILE', '/tmp/telegram-health/alerts.json')),
            self.build_senders(os.environ),
            media_status=JsonStatusFile(os.environ['TELEGRAM_MEDIA_STATUS_FILE'])
                if os.environ.get('TELEGRAM_MEDIA_STATUS_FILE') else None,
            storage_status=JsonStatusFile(os.environ['MEDIA_RESERVE_STATUS_FILE'])
                if os.environ.get('MEDIA_RESERVE_STATUS_FILE') else None)
        stop = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop.set())
        while not stop.is_set():
            watchdog.check()
            stop.wait(15)
