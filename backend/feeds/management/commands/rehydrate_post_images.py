from __future__ import annotations

import re
from html import escape
from typing import Iterable

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from django.db.models import Q

from feeds.models import Post
from telegram_integration.media import (
    download_telegram_file_by_id,
    download_telegram_file_by_path,
    download_telegram_file_by_url,
    extract_telegram_file_path,
    is_private_telegram_file_url,
)

IMG_SRC_RE = re.compile(r"<img\b[^>]*\bsrc=[\"']([^\"']+)[\"'][^>]*>", re.IGNORECASE)
ORPHAN_IMAGE_ATTR_FRAGMENT_RE = re.compile(r"(?:\s+alt=[\"'][^\"']*[\"']\s*/>)+", re.IGNORECASE)


class Command(BaseCommand):
    help = "Re-download Telegram images and store them locally, updating post content."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--post-id", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options) -> None:
        token = self._get_token()
        if not token:
            self.stderr.write("TELEGRAM_BOT_TOKEN is not set.")
            return

        limit = options["limit"] or 0
        post_id = options["post_id"] or 0
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
        if post_id:
            qs = qs.filter(id=post_id)
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
            raw_gallery_urls = list(raw_data.get("gallery_urls") or [])
            raw_gallery_file_ids = list(raw_data.get("gallery_file_ids") or [])
            gallery_urls = self._unique_nonempty(raw_gallery_urls)
            gallery_file_ids = self._unique_nonempty(raw_gallery_file_ids)
            content_urls = list(self._extract_img_urls(content))
            source_urls = gallery_urls or content_urls
            single_file_id = raw_data.get("photo_file_id") or self._extract_file_id(raw_data)
            needs_insert = False
            rebuild_from_file_ids = bool(
                gallery_file_ids
                and (
                    len(raw_gallery_file_ids) != len(gallery_file_ids)
                    or len(gallery_urls) != len(gallery_file_ids)
                )
            )

            if gallery_urls != raw_gallery_urls or gallery_file_ids != raw_gallery_file_ids:
                changed = True

            if rebuild_from_file_ids:
                source_urls = [""] * len(gallery_file_ids)
                needs_insert = not content_urls

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

                file_path = extract_telegram_file_path(url)
                local_url = None
                if file_path:
                    local_url = download_telegram_file_by_path(file_path, token)
                elif url:
                    local_url = download_telegram_file_by_url(url)
                if not local_url:
                    file_id = None
                    if index < len(gallery_file_ids):
                        file_id = gallery_file_ids[index]
                    elif len(source_urls) == 1:
                        file_id = single_file_id
                    if file_id:
                        local_url = download_telegram_file_by_id(file_id, token)

                if local_url:
                    local_urls.append(local_url)
                elif is_private_telegram_file_url(url):
                    local_urls.append("")
                    changed = True
                else:
                    local_urls.append(url)
                if local_url:
                    changed = True

            if content_urls and local_urls:
                new_content = self._replace_img_urls(
                    content,
                    local_urls,
                    remove_extra=rebuild_from_file_ids or len(local_urls) < len(content_urls),
                )
                new_content = self._remove_orphan_image_attr_fragments(new_content)
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
                effective_gallery_urls = new_gallery_urls or gallery_urls
                if effective_gallery_urls:
                    raw_data["gallery_urls"] = effective_gallery_urls
                if gallery_file_ids:
                    raw_data["gallery_file_ids"] = gallery_file_ids
                if effective_gallery_urls or gallery_file_ids:
                    post.raw_data = raw_data
                post.updated_at = timezone.now()
                post.save(update_fields=["content", "raw_data", "updated_at"])
                updated += 1

        self.stdout.write(f"Scanned: {scanned}, updated: {updated}")

    @staticmethod
    def _extract_img_urls(content: str) -> Iterable[str]:
        return [match.group(1) for match in IMG_SRC_RE.finditer(content)]

    @staticmethod
    def _replace_img_urls(content: str, new_urls: list[str], *, remove_extra: bool = False) -> str:
        index = 0

        def replacer(match: re.Match) -> str:
            nonlocal index
            if index >= len(new_urls):
                return "" if remove_extra else match.group(0)
            next_url = new_urls[index]
            index += 1
            if not next_url:
                return ""
            replacement = match.group(0).replace(match.group(1), next_url)
            return replacement

        return IMG_SRC_RE.sub(replacer, content)

    @staticmethod
    def _inject_images(content: str, urls: list[str]) -> str:
        urls = Command._unique_nonempty(urls)
        if not urls:
            return content
        if len(urls) == 1:
            media_html = f'<img src="{escape(urls[0], quote=True)}" alt="" />'
        else:
            gallery_imgs = "".join(f'<img src="{escape(url, quote=True)}" alt="" />' for url in urls)
            media_html = f'<div class="post-gallery">{gallery_imgs}</div>'
        if content:
            return f"{media_html}<br><br>{content}"
        return media_html

    @staticmethod
    def _remove_orphan_image_attr_fragments(content: str) -> str:
        return ORPHAN_IMAGE_ATTR_FRAGMENT_RE.sub("", content or "")

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
    def _unique_nonempty(values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            normalized = str(value or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_values.append(normalized)
        return unique_values

    @staticmethod
    def _get_token() -> str:
        from django.conf import settings

        return settings.TELEGRAM_BOT_TOKEN or ""
