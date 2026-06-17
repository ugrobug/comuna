from __future__ import annotations

import os

from django.core.management.base import BaseCommand
from django.db import transaction

from legacy_migration.legacy_posts import articles_q
from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids
from legacy_migration.models import LegacyWpPostMap, WpPosts
from legacy_migration.wp_post_supplement import apply_post_cover, apply_post_excerpt


class Command(BaseCommand):
    help = "Врезка (post_excerpt) и обложка (_thumbnail_id) для импортированных Post"

    def add_arguments(self, parser):
        parser.add_argument("--wp-ids", type=str, default="")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--offset", type=int, default=0)
        parser.add_argument("--excerpt", action="store_true", help="Обновить previewDescription")
        parser.add_argument("--cover", action="store_true", help="Обновить previewImage (URL)")
        parser.add_argument(
            "--backend-base",
            type=str,
            default="",
            help="База URL для обложки (локально http://127.0.0.1:8000)",
        )

    def handle(self, *args, **options):
        do_excerpt = options["excerpt"]
        do_cover = options["cover"]
        if not do_excerpt and not do_cover:
            do_excerpt = do_cover = True

        dry_run: bool = options["dry_run"]
        limit: int = max(int(options["limit"] or 0), 0)
        offset: int = max(int(options["offset"] or 0), 0)
        wp_ids = _parse_wp_ids(options.get("wp_ids") or "")
        backend_base = (options["backend_base"] or "").strip() or os.environ.get(
            "LEGACY_MEDIA_BACKEND_BASE",
            "http://127.0.0.1:8000",
        )

        qs = WpPosts.objects.filter(articles_q()).order_by("-post_date")
        if wp_ids:
            qs = qs.filter(id__in=wp_ids)
        if offset:
            qs = qs[offset:]
        if limit:
            qs = qs[:limit]

        excerpt_n = 0
        cover_n = 0
        skipped = 0

        for wp_post in qs:
            wp_id = int(wp_post.id)
            map_row = LegacyWpPostMap.objects.filter(wp_post_id=wp_id).select_related("post").first()
            if not map_row or not map_row.post_id:
                skipped += 1
                continue

            post = map_row.post
            parts: list[str] = []

            if do_excerpt:
                excerpt_raw = (wp_post.post_excerpt or "").strip()
                if dry_run:
                    parts.append(f"excerpt={excerpt_raw[:80]!r}…" if len(excerpt_raw) > 80 else f"excerpt={excerpt_raw!r}")
                elif apply_post_excerpt(post, post_excerpt=wp_post.post_excerpt or "", wp_post_id=wp_id):
                    excerpt_n += 1
                    parts.append("excerpt")

            if do_cover:
                if dry_run:
                    from legacy_migration.wp_media import wp_thumbnail_attachment_url

                    thumb = wp_thumbnail_attachment_url(wp_id)
                    parts.append(f"cover={thumb or '-'}")
                else:
                    url = apply_post_cover(
                        post,
                        wp_post_id=wp_id,
                        backend_base=backend_base,
                    )
                    if url:
                        cover_n += 1
                        parts.append("cover")

            if dry_run:
                self.stdout.write(f"[dry-run] wp:{wp_id} post:{post.id} {' '.join(parts)}")
                continue

            if parts:
                with transaction.atomic():
                    post.save(update_fields=["content", "raw_data", "updated_at"])
                self.stdout.write(f"wp:{wp_id} → post:{post.id} {','.join(parts)}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Врезки: {excerpt_n}, обложки (URL): {cover_n}, пропущено {skipped}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run"))
