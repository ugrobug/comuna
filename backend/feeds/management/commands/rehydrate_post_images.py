from __future__ import annotations

import re
from typing import Iterable

from django.core.management.base import BaseCommand
from django.utils import timezone

from feeds.models import Post
from feeds.telegram_media import download_telegram_file_by_path, extract_telegram_file_path

IMG_SRC_RE = re.compile(r'<img[^>]+src="([^"]+)"')


class Command(BaseCommand):
    help = "Re-download Telegram images and store them locally, updating post content."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options) -> None:
        token = self._get_token()
        if not token:
            self.stderr.write("TELEGRAM_BOT_TOKEN is not set.")
            return

        limit = options["limit"] or 0
        dry_run = options["dry_run"]

        qs = Post.objects.filter(content__contains="api.telegram.org/file/bot").order_by("-id")
        if limit:
            qs = qs[:limit]

        updated = 0
        scanned = 0

        for post in qs.iterator():
            scanned += 1
            changed = False
            content = post.content or ""
            new_content = content

            for url in self._extract_img_urls(content):
                file_path = extract_telegram_file_path(url)
                if not file_path:
                    continue
                local_url = download_telegram_file_by_path(file_path, token)
                if not local_url:
                    continue
                new_content = new_content.replace(url, local_url)
                changed = True

            raw_data = dict(post.raw_data or {})
            gallery_urls = list(raw_data.get("gallery_urls") or [])
            new_gallery_urls = []
            for url in gallery_urls:
                file_path = extract_telegram_file_path(url)
                if file_path:
                    local_url = download_telegram_file_by_path(file_path, token)
                    new_gallery_urls.append(local_url or url)
                    if local_url:
                        changed = True
                else:
                    new_gallery_urls.append(url)

            if changed and not dry_run:
                if new_content != content:
                    post.content = new_content
                if new_gallery_urls:
                    raw_data["gallery_urls"] = new_gallery_urls
                    post.raw_data = raw_data
                post.updated_at = timezone.now()
                post.save(update_fields=["content", "raw_data", "updated_at"])
                updated += 1

        self.stdout.write(f"Scanned: {scanned}, updated: {updated}")

    @staticmethod
    def _extract_img_urls(content: str) -> Iterable[str]:
        return [match.group(1) for match in IMG_SRC_RE.finditer(content)]

    @staticmethod
    def _get_token() -> str:
        from django.conf import settings

        return settings.TELEGRAM_BOT_TOKEN or ""
