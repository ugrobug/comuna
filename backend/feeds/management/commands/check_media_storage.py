from __future__ import annotations

import secrets

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Save and delete a small file through the configured media storage."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep",
            action="store_true",
            help="Keep the test file instead of deleting it.",
        )

    def handle(self, *args, **options):
        backend = getattr(settings, "MEDIA_STORAGE_BACKEND", "local")
        path = f"storage-healthcheck/{secrets.token_hex(8)}.txt"
        saved_path = default_storage.save(path, ContentFile(b"tambur media storage ok\n"))
        url = default_storage.url(saved_path)

        self.stdout.write(f"backend={backend}")
        self.stdout.write(f"path={saved_path}")
        self.stdout.write(f"url={url}")

        if not default_storage.exists(saved_path):
            raise SystemExit("saved file is not visible through default_storage.exists()")

        if not options["keep"]:
            default_storage.delete(saved_path)
            self.stdout.write("deleted=1")
        else:
            self.stdout.write("deleted=0")
