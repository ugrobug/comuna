import os
import signal
import threading

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from feeds import views
from telegram_integration.bot import _send_bot_message_with_keyboard
from telegram_integration.media_queue import TelegramMediaWorker
from telegram_integration.media_status import TelegramMediaStatus
from telegram_integration.health import JsonStatusFile
from telegram_integration.moderation import TelegramApprovalPrompt


class Command(BaseCommand):
    help = 'Deliver queued Telegram photos independently of polling.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--limit', type=int, default=10)

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError('TELEGRAM_BOT_TOKEN is required')
        # Process-local SDK configuration, before the lazy storage client is created.
        if hasattr(settings, 'AWS_S3_CLIENT_CONFIG'):
            from botocore.config import Config
            settings.AWS_S3_CLIENT_CONFIG = settings.AWS_S3_CLIENT_CONFIG.merge(
                Config(connect_timeout=5, read_timeout=15, retries={'max_attempts': 1}))
        status = TelegramMediaStatus(JsonStatusFile(os.environ.get(
            'TELEGRAM_MEDIA_STATUS_FILE', '/tmp/telegram-health/media.json')))
        stop = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop.set())
        worker = TelegramMediaWorker(
            download=lambda message: views._extract_photo_url(message, settings.TELEGRAM_BOT_TOKEN),
            content=views, prompt=TelegramApprovalPrompt(_send_bot_message_with_keyboard),
            progress=status.heartbeat)
        status.update()
        while not stop.is_set():
            close_old_connections()
            status.heartbeat()
            result = worker.drain(options['limit'])
            status.update(error=result['error'] if result['failed'] or result['processed'] else None)
            self.stdout.write(str(result))
            if not options['loop']:
                return
            stop.wait(60 if result['failed'] else 5)
