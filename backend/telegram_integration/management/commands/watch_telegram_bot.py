import os
import signal
import threading

from django.core.management.base import BaseCommand, CommandError
from max_integration.client import MaxClient
from telegram_integration.health import JsonStatusFile
from telegram_integration.watchdog import EmailAlertSender, MaxAlertSender, TelegramWatchdog


class Command(BaseCommand):
    help = 'Watch Telegram status and notify configured MAX/email recipients independently.'

    def handle(self, *args, **options):
        email = os.environ.get('TELEGRAM_ALERT_EMAIL', '')
        chat = os.environ.get('TELEGRAM_ALERT_MAX_CHAT_ID', '')
        if not email or not chat:
            raise CommandError('Configure TELEGRAM_ALERT_EMAIL and TELEGRAM_ALERT_MAX_CHAT_ID')
        watchdog = TelegramWatchdog(
            JsonStatusFile(os.environ.get('TELEGRAM_STATUS_FILE', '/tmp/telegram-health/polling.json')),
            JsonStatusFile(os.environ.get('TELEGRAM_ALERT_STATE_FILE', '/tmp/telegram-health/alerts.json')),
            {'email': EmailAlertSender(email), 'max': MaxAlertSender(MaxClient(), int(chat))})
        stop = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop.set())
        while not stop.is_set():
            watchdog.check()
            stop.wait(15)
