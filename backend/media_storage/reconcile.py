"""Bounded cleanup of files left behind by rolled-back application transactions."""
import os
import re
import time
from media_storage.models import MediaTransfer


class MediaReserveReconciler:
    grace_seconds = 24 * 3600

    def __init__(self, spool, clock=time.time):
        self.spool, self.clock = spool, clock
        self.entries = self.scan()

    def scan(self):
        try:
            with os.scandir(self.spool.directory) as directories:
                for directory in directories:
                    yield None
                    if not re.fullmatch('[a-f0-9]{32}', directory.name) or not directory.is_dir(follow_symlinks=False):
                        continue
                    try:
                        with os.scandir(directory.path) as files:
                            for file in files:
                                yield (f'_spool/{directory.name}/{file.name}', file.path) if file.is_file(follow_symlinks=False) else None
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            return

    def run(self, limit=200):
        candidates = []
        for _ in range(max(1, min(limit, 500))):
            try:
                item = next(self.entries)
            except StopIteration:
                self.entries = self.scan()
                break
            if item:
                try:
                    if self.spool.is_key(item[0]) and os.stat(item[1]).st_mtime < self.clock() - self.grace_seconds:
                        candidates.append(item)
                except FileNotFoundError:
                    pass
        known = set(MediaTransfer.objects.filter(key__in=[key for key, _ in candidates]).values_list('key', flat=True)) if candidates else set()
        removed = 0
        for key, path in candidates:
            if key not in known:
                with self.spool.locked():
                    if not MediaTransfer.objects.filter(key=key).exists():
                        self.spool.remove_local(key)
                        removed += 1
        return removed
