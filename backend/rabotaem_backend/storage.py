from __future__ import annotations

from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

from rabotaem_backend.media_urls import public_media_urls_prefer_s3


class S3MediaStorage(Storage):
    """Store new media in S3 while still serving legacy local files."""

    @cached_property
    def s3_storage(self) -> Storage:
        try:
            storage_class = import_string("storages.backends.s3.S3Storage")
        except ImportError:
            storage_class = import_string("storages.backends.s3boto3.S3Boto3Storage")
        return storage_class()

    @cached_property
    def local_storage(self) -> FileSystemStorage:
        return FileSystemStorage(
            location=settings.MEDIA_ROOT,
            base_url=getattr(settings, "MEDIA_LEGACY_URL", settings.MEDIA_URL),
        )

    def _open(self, name: str, mode: str = "rb"):
        if self.local_storage.exists(name):
            return self.local_storage.open(name, mode)
        return self.s3_storage.open(name, mode)

    def _save(self, name: str, content) -> str:
        return self.s3_storage.save(name, content)

    def delete(self, name: str) -> None:
        try:
            self.s3_storage.delete(name)
        finally:
            if self.local_storage.exists(name):
                self.local_storage.delete(name)

    def exists(self, name: str) -> bool:
        if self.local_storage.exists(name):
            return True
        return self.s3_storage.exists(name)

    def size(self, name: str) -> int:
        if self.local_storage.exists(name):
            return self.local_storage.size(name)
        return self.s3_storage.size(name)

    def url(self, name: str) -> str:
        if public_media_urls_prefer_s3():
            return self.s3_storage.url(name)
        if self.local_storage.exists(name):
            return self.local_storage.url(name)
        return self.s3_storage.url(name)

    def get_modified_time(self, name: str):
        if self.local_storage.exists(name):
            return self.local_storage.get_modified_time(name)
        return self.s3_storage.get_modified_time(name)
