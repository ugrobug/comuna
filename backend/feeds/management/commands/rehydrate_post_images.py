from __future__ import annotations

import re
from typing import Iterable

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from django.db.models import Q

from feeds.models import Post
from feeds.telegram_media import (
    download_telegram_file_by_id,
    download_telegram_file_by_path,
    download_telegram_file_by_url,
    extract_telegram_file_path,
)

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

        qs = (
            Post.objects.filter(
                Q(content__contains="api.telegram.org/file/bot")
                | Q(raw_data__has_key="gallery_urls")
                | Q(raw_data__has_key="photo")
                | Q(raw_data__has_key="gallery_file_ids")
                | Q(raw_data__has_key="photo_file_id")
            )
            .order_by("-id")
        )
        if limit:
            qs = qs[:limit]

        updated = 0
        scanned = 0

        for post in qs.iterator():
            scanned += 1
            changed = False
            content = post.content or ""
            new_content = content

            raw_data = dict(post.raw_data or {})
            gallery_urls = list(raw_data.get("gallery_urls") or [])
            gallery_file_ids = list(raw_data.get("gallery_file_ids") or [])
            content_urls = list(self._extract_img_urls(content))
            source_urls = gallery_urls or content_urls
            single_file_id = raw_data.get("photo_file_id") or self._extract_file_id(raw_data)
            needs_insert = False

            if not source_urls:
                if gallery_file_ids:
                    source_urls = [""] * len(gallery_file_ids)
                    needs_insert = True
                elif single_file_id:
                    source_urls = [""]
                    needs_insert = True

            local_urls: list[str] = []
            for index, url in enumerate(source_urls):
                if self._is_local_url(url):
                    local_urls.append(url)
                    continue

                local_url = download_telegram_file_by_url(url)
                if not local_url:
                    file_path = extract_telegram_file_path(url)
                    if file_path:
                        local_url = download_telegram_file_by_path(file_path, token)

                if not local_url:
                    file_id = None
                    if index < len(gallery_file_ids):
                        file_id = gallery_file_ids[index]
                    elif len(source_urls) == 1:
                        file_id = single_file_id
                    if file_id:
                        local_url = download_telegram_file_by_id(file_id, token)

                local_urls.append(local_url or url)
                if local_url:
                    changed = True

            if content_urls and local_urls:
                new_content = self._replace_img_urls(content, local_urls)
                if new_content != content:
                    changed = True
            elif not content_urls and needs_insert and local_urls:
                new_content = self._inject_images(content, local_urls)
                if new_content != content:
                    changed = True

            new_gallery_urls = []
            if gallery_urls or gallery_file_ids:
                new_gallery_urls = [url for url in local_urls if url]

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
    def _replace_img_urls(content: str, new_urls: list[str]) -> str:
        index = 0

        def replacer(match: re.Match) -> str:
            nonlocal index
            if index >= len(new_urls):
                return match.group(0)
            replacement = match.group(0).replace(match.group(1), new_urls[index])
            index += 1
            return replacement

        return IMG_SRC_RE.sub(replacer, content)

    @staticmethod
    def _inject_images(content: str, urls: list[str]) -> str:
        urls = [url for url in urls if url]
        if not urls:
            return content
        if len(urls) == 1:
            media_html = f'<img src="{urls[0]}" alt="" />'
        else:
            gallery_imgs = "".join(f'<img src="{url}" alt="" />' for url in urls)
            media_html = f'<div class="post-gallery">{gallery_imgs}</div>'
        if content:
            return f"{media_html}<br><br>{content}"
        return media_html

    @staticmethod
    def _extract_file_id(raw_data: dict) -> str | None:
        photos = raw_data.get("photo") or []
        if not photos:
            return None
        largest = max(
            photos,
            key=lambda item: (item.get("file_size", 0), item.get("width", 0) * item.get("height", 0)),
        )
        return largest.get("file_id")

    @staticmethod
    def _is_local_url(url: str) -> bool:
        if not url:
            return False
        if url.startswith("/media/"):
            return True
        return url.startswith(settings.SITE_BASE_URL.rstrip("/") + settings.MEDIA_URL)

    @staticmethod
    def _get_token() -> str:
        from django.conf import settings

        return settings.TELEGRAM_BOT_TOKEN or ""
