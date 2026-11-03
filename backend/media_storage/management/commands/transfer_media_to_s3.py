import os
import signal
import threading
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from media_storage.status import MediaReserveStatus
from media_storage.reconcile import MediaReserveReconciler
from media_storage.transfer import MediaTransferWorker, S3TransferDestination
from telegram_integration.health import JsonStatusFile


class Command(BaseCommand):
    help = 'Transfer and verify reserved media, preserving public URLs.'

    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
        parser.add_argument('--limit', type=int, default=10)

    def handle(self, *args, **options):
        if not hasattr(default_storage, 's3_storage'):
            raise CommandError('S3 media storage must be configured')
        spool = default_storage.spool
        status = MediaReserveStatus(JsonStatusFile(os.environ.get(
            'MEDIA_RESERVE_STATUS_FILE', '/tmp/telegram-health/storage.json')), spool)
        worker = MediaTransferWorker(spool=spool, destination=S3TransferDestination(default_storage.s3_storage),
            availability=default_storage.availability, progress=status.heartbeat)
        reconciler = MediaReserveReconciler(spool)
        stop = threading.Event()
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, lambda *_: stop.set())
        status.update()
        while not stop.is_set():
            close_old_connections()
            status.heartbeat()
            reconciler.run()
            result = worker.drain(options['limit'])
            status.update()
            self.stdout.write(str(result))
            if not options['loop']:
                return
            stop.wait(60 if result['failed'] else 5 if result['processed'] else 30)
