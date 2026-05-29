from __future__ import annotations

import json
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from feeds.models import Post
from legacy_migration.models import LegacyWpPostMap
from legacy_migration.wp_media import (
    build_url_mapping,
    extract_wp_upload_urls_from_post_content,
    public_media_url,
    public_media_url_relative,
    rewrite_absolute_media_urls_to_relative,
    rewrite_post_content,
    wp_thumbnail_attachment_url,
    wp_url_to_storage_path,
)
from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids


class Command(BaseCommand):
    help = (
        "Скачать картинки posletitrov.ru/wp-content/uploads для импортированных постов "
        "и переписать URL в Post.content на локальный /media/legacy-wp/..."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wp-ids",
            type=str,
            required=True,
            help="WP post ID через запятую",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только список URL, без скачивания и без save",
        )
        parser.add_argument(
            "--backend-base",
            type=str,
            default="",
            help="База для URL в контенте (по умолчанию http://127.0.0.1:8000)",
        )
        parser.add_argument(
            "--skip-content",
            action="store_true",
            help="Не менять Post.content (только скачать файлы)",
        )
        parser.add_argument(
            "--absolute-urls",
            action="store_true",
            help="Абсолютные URL с --backend-base (по умолчанию — относительные /media/…)",
        )
        parser.add_argument(
            "--rewrite-only",
            action="store_true",
            help="Не скачивать; только заменить http://…/media/ на /media/ в уже импортированных постах",
        )

    def handle(self, *args, **options):
        wp_ids = _parse_wp_ids(options["wp_ids"])
        dry_run: bool = options["dry_run"]
        skip_content: bool = options["skip_content"]
        rewrite_only: bool = options["rewrite_only"]
        relative_urls: bool = not options["absolute_urls"]
        backend_base = (options["backend_base"] or "").strip() or os.environ.get(
            "LEGACY_MEDIA_BACKEND_BASE",
            "http://127.0.0.1:8000",
        )

        total_files = 0
        total_posts = 0

        for wp_id in wp_ids:
            map_row = (
                LegacyWpPostMap.objects.filter(wp_post_id=wp_id)
                .select_related("post")
                .first()
            )
            if not map_row or not map_row.post_id:
                raise CommandError(f"wp:{wp_id} — нет LegacyWpPostMap / Post (сначала import_wp_posts)")

            post: Post = map_row.post
            urls = extract_wp_upload_urls_from_post_content(post.content or "")

            thumb_url = wp_thumbnail_attachment_url(wp_id)
            if thumb_url:
                urls.add(thumb_url)

            if not urls:
                self.stdout.write(self.style.WARNING(f"wp:{wp_id} post:{post.id} — нет URL uploads"))
                continue

            self.stdout.write(
                f"wp:{wp_id} → post:{post.id}: {len(urls)} уникальных URL uploads"
            )
            for u in sorted(urls):
                sp = wp_url_to_storage_path(u)
                self.stdout.write(f"  {u}")
                if sp:
                    self.stdout.write(f"    → media/{sp}")

            if dry_run:
                continue

            if rewrite_only:
                with transaction.atomic():
                    new_content = rewrite_absolute_media_urls_to_relative(post.content or "")
                    raw = dict(post.raw_data or {})
                    if isinstance(raw.get("legacy_cover_url"), str):
                        raw["legacy_cover_url"] = rewrite_absolute_media_urls_to_relative(
                            raw["legacy_cover_url"]
                        )
                    post.content = new_content
                    post.raw_data = raw
                    post.save(update_fields=["content", "raw_data", "updated_at"])
                total_posts += 1
                self.stdout.write(self.style.SUCCESS("  rewrite-only: /media/…"))
                continue

            try:
                mapping = build_url_mapping(
                    urls,
                    backend_base=backend_base,
                    relative_urls=relative_urls,
                )
            except OSError as exc:
                raise CommandError(f"wp:{wp_id}: {exc}") from exc

            total_files += len({wp_url_to_storage_path(u) for u in urls if wp_url_to_storage_path(u)})

            with transaction.atomic():
                new_content = post.content or ""
                if not skip_content:
                    new_content = rewrite_post_content(new_content, mapping)

                cover_url = ""
                if thumb_url:
                    storage = wp_url_to_storage_path(thumb_url)
                    if storage:
                        cover_url = (
                            public_media_url_relative(storage)
                            if relative_urls
                            else public_media_url(storage, backend_base=backend_base)
                        )
                    elif thumb_url in mapping:
                        cover_url = mapping[thumb_url]

                if cover_url and not skip_content and new_content.strip().startswith("{"):
                    try:
                        payload = json.loads(new_content)
                        additional = dict(payload.get("additional") or {})
                        additional["previewImage"] = cover_url
                        payload["additional"] = additional
                        new_content = json.dumps(payload, ensure_ascii=False)
                    except json.JSONDecodeError:
                        pass

                raw = dict(post.raw_data or {})
                if cover_url:
                    raw["legacy_cover_url"] = cover_url

                post.content = new_content
                post.raw_data = raw
                post.save(update_fields=["content", "raw_data", "updated_at"])

            total_posts += 1
            self.stdout.write(self.style.SUCCESS(f"  готово, подменено {len(mapping)} вариантов URL"))

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: файлы не скачаны, посты не изменены"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Обработано постов: {total_posts}; файлов (уник. путей): ~{total_files}. "
                f"Раздача: {backend_base}/media/legacy-wp/uploads/..."
            )
        )
