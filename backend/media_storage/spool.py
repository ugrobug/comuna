"""Shared-volume fallback. Reads never need S3, writes retain a disk reserve."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import re
import shutil
import time
import uuid

from botocore.exceptions import ClientError
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.files.utils import validate_file_name
from media_storage.models import MediaTransfer


class MediaReserveFull(OSError):
    pass


class LocalMediaSpool:
    prefix = '_spool/'
    key_pattern = re.compile(r'^_spool/[a-f0-9]{32}/[^/]+$')

    def __init__(self, root=None, *, free_bytes=None, reserve_bytes=None, max_file_bytes=None):
        self.root = Path(root or settings.MEDIA_ROOT)
        self.directory = self.root / '_spool'
        self.local = FileSystemStorage(location=self.root, base_url='/media/')
        self.free_bytes = free_bytes or (lambda: shutil.disk_usage(self.root).free)
        self.reserve_bytes = reserve_bytes if reserve_bytes is not None else getattr(settings, 'MEDIA_SPOOL_RESERVE_BYTES', 2 * 1024**3)
        self.max_file_bytes = max_file_bytes if max_file_bytes is not None else getattr(settings, 'MEDIA_SPOOL_MAX_FILE_BYTES', 20 * 1024**2)

    @contextmanager
    def locked(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    @classmethod
    def is_key(cls, name):
        return bool(cls.key_pattern.fullmatch(str(name))) and '..' not in str(name).split('/')

    def save(self, name, content, max_length=None):
        validate_file_name(name, allow_relative_path=True)
        key = name if self.is_key(name) else f'{self.prefix}{uuid.uuid4().hex}/{Path(name).name}'
        # Keep extensions and variant naming, while respecting FileField.max_length.
        if max_length and len(key) > max_length:
            directory, filename = key.rsplit('/', 1)
            suffix = Path(filename).suffix
            available = max_length - len(directory) - len(suffix) - 1
            if available < 1:
                raise ValueError('Media field max_length is too short for reserve storage')
            key = f'{directory}/{Path(filename).stem[:available]}{suffix}'
        content.seek(0)
        size = content.size
        if size > self.max_file_bytes:
            raise MediaReserveFull('Файл слишком большой для временного хранилища. Повторите загрузку позже.')
        with self.locked():
            if self.free_bytes() - size < self.reserve_bytes:
                raise MediaReserveFull('Временное хранилище заполнено. Повторите загрузку позже.')
            saved = self.local.save(key, content, max_length=max_length)
            try:
                digest = hashlib.sha256()
                with self.local.open(saved, 'rb') as source:
                    for block in iter(lambda: source.read(65536), b''):
                        digest.update(block)
                # The queue transaction follows the caller's transaction; rollback
                # cannot publish a post that references an unrecorded transfer.
                MediaTransfer.objects.create(key=saved, size=size, sha256=digest.hexdigest(),
                    content_type=getattr(content, 'content_type', None) or mimetypes.guess_type(saved)[0] or 'application/octet-stream')
            except Exception:
                self.local.delete(saved)
                raise
        return saved

    def remove_local(self, key):
        self.local.delete(key)
        try:
            Path(self.local.path(key)).parent.rmdir()
        except OSError:
            pass  # Other variants still use this directory.

    def delete(self, key):
        from django.db import transaction
        from django.utils import timezone
        with transaction.atomic():
            row = MediaTransfer.objects.select_for_update().filter(key=key).first()
            if row:
                # A downloader already holding the old lease may still finish its
                # PUT. Delay deletion until that bounded upload lease has expired.
                row.state = 'deleting'
                row.delete_requested, row.attempts = True, 0
                row.next_attempt_at = max(row.next_attempt_at, timezone.now()) if row.lease_token else timezone.now()
                row.lease_token = ''
                row.save(update_fields=['state', 'delete_requested', 'attempts', 'next_attempt_at', 'lease_token', 'updated_at'])
            self.remove_local(key)


class S3Availability:
    """Small circuit state shared by all containers through the media volume."""
    def __init__(self, spool):
        self.spool = spool
        self.path = spool.directory / '.s3-availability.json'

    def allow_request(self):
        with self.spool.locked():
            state = self.read()
            if state.get('retry_at', 0) > time.time():
                return False
            if state.get('error'):
                # Exactly one recovery probe while the remaining requests spool.
                self.write({**state, 'retry_at': time.time() + 30})
            return True

    def read(self):
        try:
            return json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}

    def write(self, state):
        temporary = self.path.with_suffix(f'.{os.getpid()}.tmp')
        temporary.write_text(json.dumps(state))
        temporary.replace(self.path)

    def failed(self, error):
        with self.spool.locked():
            self.write({'retry_at': time.time() + 60, 'error': type(error).__name__})

    def recovered(self):
        with self.spool.locked():
            if self.read():
                self.write({})

    @staticmethod
    def is_unavailable(error):
        if isinstance(error, ClientError):
            return error.response.get('ResponseMetadata', {}).get('HTTPStatusCode', 0) >= 500 or error.response.get('Error', {}).get('Code') in {'SlowDown', 'RequestTimeout', 'ServiceUnavailable'}
        # Credentials/configuration/permission errors must not be disguised as an outage.
        from botocore.exceptions import EndpointConnectionError, ConnectionClosedError, ConnectTimeoutError, ReadTimeoutError, HTTPClientError
        return isinstance(error, (EndpointConnectionError, ConnectionClosedError, ConnectTimeoutError, ReadTimeoutError, HTTPClientError))
