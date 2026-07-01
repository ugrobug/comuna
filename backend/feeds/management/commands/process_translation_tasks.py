from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from feeds.translation_service import process_due_translation_tasks


class Command(BaseCommand):
    help = "Process due automatic content translation tasks."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=30)

    def handle(self, *args, **options):
        limit = max(int(options["limit"] or 20), 1)
        interval = max(int(options["interval"] or 30), 1)

        while True:
            stats = process_due_translation_tasks(limit=limit)
            self.stdout.write(
                "processed={processed} done={done} failed={failed} skipped={skipped}".format(
                    **stats
                )
            )
            if not options["loop"]:
                break
            time.sleep(interval)
