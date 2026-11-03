"""Leased, verified S3 delivery of immutable local files."""
from datetime import timedelta
import hashlib
import base64
import logging
import secrets

from django.db import transaction
from django.utils import timezone
from media_storage.models import MediaTransfer

logger = logging.getLogger(__name__)


class S3TransferDestination:
    def __init__(self, storage):
        self.storage = storage
        self.client = storage.connection.meta.client

    def key(self, key):
        prefix = str(self.storage.location or '').strip('/')
        return f'{prefix}/{key}' if prefix else key

    def put_and_verify(self, job, source):
        digest = hashlib.sha256()
        md5 = hashlib.md5(usedforsecurity=False)
        for block in iter(lambda: source.read(65536), b''):
            digest.update(block)
            md5.update(block)
        if digest.hexdigest() != job.sha256 or source.tell() != job.size:
            raise ValueError('Local media integrity mismatch')
        source.seek(0)
        parameters = dict(self.storage.object_parameters or {})
        parameters.update(ContentType=job.content_type, Metadata={'sha256': job.sha256},
            ContentMD5=base64.b64encode(md5.digest()).decode('ascii'))
        if self.storage.default_acl:
            parameters['ACL'] = self.storage.default_acl
        self.client.put_object(Bucket=self.storage.bucket_name, Key=self.key(job.key), Body=source, **parameters)
        head = self.client.head_object(Bucket=self.storage.bucket_name, Key=self.key(job.key))
        if head['ContentLength'] != job.size or head.get('Metadata', {}).get('sha256') != job.sha256:
            raise ValueError('Remote media verification failed')

    def delete(self, key):
        self.client.delete_object(Bucket=self.storage.bucket_name, Key=self.key(key))

    def url(self, key):
        return self.storage.url(key)


class MediaTransferWorker:
    lease_seconds = 600
    max_attempts = 100

    def __init__(self, *, spool, destination, availability, progress=None):
        self.spool, self.destination, self.availability = spool, destination, availability
        self.progress = progress or (lambda: None)

    def claim(self):
        with transaction.atomic():
            row = (MediaTransfer.objects.select_for_update(skip_locked=True)
                   .filter(state__in=['pending', 'deleting'], next_attempt_at__lte=timezone.now())
                   .order_by('next_attempt_at', 'id').first())
            if row:
                row.lease_token = secrets.token_hex(16)
                row.attempts += 1
                row.next_attempt_at = timezone.now() + timedelta(seconds=self.lease_seconds)
                row.save(update_fields=['lease_token', 'attempts', 'next_attempt_at', 'updated_at'])
            return row

    def complete(self, claimed):
        with transaction.atomic():
            row = MediaTransfer.objects.select_for_update().filter(pk=claimed.pk,
                lease_token=claimed.lease_token, state=claimed.state).first()
            if row is None:
                return False
            row.state = 'deleted' if row.state == 'deleting' else 'uploaded'
            row.lease_token, row.last_error = '', ''
            row.save(update_fields=['state', 'lease_token', 'last_error', 'updated_at'])
            # Keep the only local copy until verification AND the state commit.
            transaction.on_commit(lambda: self.cleanup(row.pk), robust=True)
        return True

    def cleanup(self, job_id):
        with transaction.atomic():
            row = MediaTransfer.objects.select_for_update().filter(pk=job_id,
                state__in=['uploaded', 'deleted'], local_deleted_at__isnull=True).first()
            if row:
                self.spool.remove_local(row.key)
                row.local_deleted_at = timezone.now()
                row.save(update_fields=['local_deleted_at'])

    def drain(self, limit=10):
        # Recover a crash between the verified DB commit and filesystem cleanup.
        for pk in MediaTransfer.objects.filter(state__in=['uploaded', 'deleted'], local_deleted_at__isnull=True).order_by('pk').values_list('pk', flat=True)[:20]:
            self.cleanup(pk)
        count = 0
        for _ in range(max(1, min(int(limit), 20))):
            self.progress()
            row = self.claim()
            if row is None:
                break
            try:
                if row.state == 'deleting':
                    self.destination.delete(row.key)
                else:
                    with self.spool.local.open(row.key, 'rb') as source:
                        self.destination.put_and_verify(row, source)
                self.complete(row)
                self.availability.recovered()
                count += 1
            except Exception as error:
                if self.availability.is_unavailable(error):
                    self.availability.failed(error)
                MediaTransfer.objects.filter(pk=row.pk, lease_token=row.lease_token).update(
                    state='failed' if row.attempts >= self.max_attempts else row.state,
                    last_error=type(error).__name__[:100], lease_token='', updated_at=timezone.now(),
                    next_attempt_at=timezone.now() + timedelta(seconds=min(3600, 60 * 2 ** min(row.attempts - 1, 6))))
                logger.warning('Media transfer retry (job=%s, error=%s)', row.pk, type(error).__name__)
                return {'processed': count, 'failed': 1, 'error': type(error).__name__}
        return {'processed': count, 'failed': 0, 'error': ''}
