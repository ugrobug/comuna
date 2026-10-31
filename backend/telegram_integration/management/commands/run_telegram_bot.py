import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from telegram_integration.polling import _acquire_polling_lock, _polling_loop


class Command(BaseCommand):
    help = 'Run the dedicated Telegram receiver. Set TELEGRAM_USE_POLLING=0.'

    def handle(self, *args, **options):
        if settings.TELEGRAM_USE_POLLING:
            raise CommandError('Disable web polling before starting the dedicated worker')
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError('TELEGRAM_BOT_TOKEN is required')
        if not _acquire_polling_lock():
            raise CommandError('Another Telegram receiver already holds the lock')
        stop = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop.set())
        _polling_loop(settings.TELEGRAM_BOT_TOKEN, stop)
