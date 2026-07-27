from __future__ import annotations

import signal
import time

from django.core.management.base import BaseCommand

from feeds.translation_service import process_due_translation_tasks


class Command(BaseCommand):
    help = "Process due automatic content translation tasks."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=20)
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=int, default=30)
        parser.add_argument("--run-timeout", type=int, default=720)

    def handle(self, *args, **options):
        limit = max(int(options["limit"] or 20), 1)
        interval = max(int(options["interval"] or 30), 1)
        run_timeout = max(int(options["run_timeout"] or 720), 1)

        while True:
            stats = {"processed": 0, "done": 0, "failed": 0, "skipped": 0}
            for _ in range(limit):
                signal.signal(signal.SIGALRM, _raise_timeout)
                signal.alarm(run_timeout)
                try:
                    result = process_due_translation_tasks(limit=1)
                finally:
                    signal.alarm(0)
                for key in stats:
                    stats[key] += result.get(key, 0)
                if result["processed"] == 0:
                    break
            self.stdout.write(
                "processed={processed} done={done} failed={failed} skipped={skipped}".format(
                    **stats
                )
            )
            if not options["loop"]:
                break
            time.sleep(interval)


def _raise_timeout(signum, frame):
    raise TimeoutError("Translation task processor exceeded run timeout")
