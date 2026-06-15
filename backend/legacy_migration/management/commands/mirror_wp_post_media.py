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
    legacy_media_use_object_storage,
    rewrite_legacy_media_urls_for_delivery,
    rewrite_post_content,
    target_public_url,
    wp_thumbnail_attachment_url,
    wp_url_to_storage_path,
)
from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids


class Command(BaseCommand):
    help = (
        "Скачать картинки posletitrov.ru/wp-content/uploads для импортированных постов "
        "и переписать URL в Post.content (S3/CDN на prod, /media/… локально на диске)"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wp-ids",
            type=str,
            default="",
            help="WP post ID через запятую; пусто — все строки LegacyWpPostMap с post_id",
        )
        parser.add_argument("--limit", type=int, default=0, help="Макс. постов (после offset)")
        parser.add_argument("--offset", type=int, default=0, help="Пропустить N постов в выборке")
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
            help="Не скачивать; переписать URL медиа под текущую раздачу (/media/ или CDN)",
        )
        parser.add_argument(
            "--local-disk",
            action="store_true",
            help="Писать в MEDIA_ROOT, не в S3 (даже если MEDIA_STORAGE_BACKEND=s3)",
        )
        parser.add_argument(
            "--skip-missing",
            action="store_true",
            help="Не падать на 404/ошибке скачивания; пропустить файл, остальные URL поста обработать",
        )

    def handle(self, *args, **options):
        wp_ids = _parse_wp_ids(options.get("wp_ids") or "")
        limit = max(int(options["limit"] or 0), 0)
        offset = max(int(options["offset"] or 0), 0)
        dry_run: bool = options["dry_run"]
        skip_content: bool = options["skip_content"]
        rewrite_only: bool = options["rewrite_only"]
        skip_missing: bool = options["skip_missing"]
        use_object_storage = legacy_media_use_object_storage() and not options["local_disk"]
        relative_urls = (
            not options["absolute_urls"]
            and not use_object_storage
        )
        backend_base = (options["backend_base"] or "").strip() or os.environ.get(
            "LEGACY_MEDIA_BACKEND_BASE",
            "http://127.0.0.1:8000",
        )
        storage_label = "S3" if use_object_storage else "MEDIA_ROOT"

        total_files = 0
        total_posts = 0

        qs = (
            LegacyWpPostMap.objects.filter(post_id__isnull=False)
            .select_related("post")
            .order_by("wp_post_id")
        )
        if wp_ids:
            qs = qs.filter(wp_post_id__in=wp_ids)
        if offset:
            qs = qs[offset:]
        if limit:
            qs = qs[:limit]

        map_rows = list(qs)
        if wp_ids:
            found = {int(m.wp_post_id) for m in map_rows}
            missing = [wid for wid in wp_ids if wid not in found]
            if missing:
                raise CommandError(
                    f"нет LegacyWpPostMap / Post для wp: {','.join(str(x) for x in missing)} "
                    "(сначала import_wp_posts)"
                )
        if not map_rows:
            self.stdout.write(self.style.WARNING("Нет постов в выборке"))
            return

        self.stdout.write(f"К обработке: {len(map_rows)} пост(ов)")

        for map_row in map_rows:
            wp_id = int(map_row.wp_post_id)
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
                    self.stdout.write(f"    → {storage_label}:{sp}")
                    if not dry_run and not rewrite_only:
                        self.stdout.write(
                            f"       URL: {target_public_url(sp, backend_base=backend_base, relative_urls=relative_urls)}"
                        )

            if dry_run:
                continue

            if rewrite_only:
                with transaction.atomic():
                    new_content = rewrite_legacy_media_urls_for_delivery(post.content or "")
                    raw = dict(post.raw_data or {})
                    if isinstance(raw.get("legacy_cover_url"), str):
                        raw["legacy_cover_url"] = rewrite_legacy_media_urls_for_delivery(
                            raw["legacy_cover_url"]
                        )
                    post.content = new_content
                    post.raw_data = raw
                    post.save(update_fields=["content", "raw_data", "updated_at"])
                total_posts += 1
                self.stdout.write(self.style.SUCCESS("  rewrite-only: URL обновлены"))
                continue

            try:
                mapping, dl_errors = build_url_mapping(
                    urls,
                    backend_base=backend_base,
                    relative_urls=relative_urls,
                    use_object_storage=use_object_storage,
                    skip_missing=skip_missing,
                )
            except OSError as exc:
                raise CommandError(f"wp:{wp_id}: {exc}") from exc

            for err in dl_errors:
                self.stderr.write(self.style.WARNING(f"  пропуск: {err}\n"))
            if not mapping:
                self.stdout.write(
                    self.style.WARNING(f"  wp:{wp_id} — нет успешных медиа, пост не изменён")
                )
                continue

            total_files += len({wp_url_to_storage_path(u) for u in urls if wp_url_to_storage_path(u)})

            with transaction.atomic():
                new_content = post.content or ""
                if not skip_content:
                    new_content = rewrite_post_content(new_content, mapping)

                cover_url = ""
                if thumb_url:
                    storage = wp_url_to_storage_path(thumb_url)
                    if storage:
                        cover_url = target_public_url(
                            storage,
                            backend_base=backend_base,
                            relative_urls=relative_urls,
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

        delivery = (
            "S3/CDN (MEDIA_PUBLIC_URL_MODE)"
            if use_object_storage
            else f"{backend_base}/media/legacy-wp/uploads/..."
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Обработано постов: {total_posts}; файлов (уник. путей): ~{total_files}. "
                f"Хранилище: {storage_label}. Раздача: {delivery}"
            )
        )
