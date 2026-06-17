from __future__ import annotations

import os

from django.core.management.base import BaseCommand
from django.db import transaction

from legacy_migration.legacy_posts import articles_q
from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids
from legacy_migration.models import LegacyWpPostMap, WpPosts
from legacy_migration.wp_post_tags import attach_wp_tags_to_post, wp_post_tag_names


class Command(BaseCommand):
    help = "Теги WP (post_tag) → Post.tags (feeds.Tag)"

    def add_arguments(self, parser):
        parser.add_argument("--wp-ids", type=str, default="", help="WP post ID через запятую")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--offset", type=int, default=0)

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: int = max(int(options["limit"] or 0), 0)
        offset: int = max(int(options["offset"] or 0), 0)
        wp_ids = _parse_wp_ids(options.get("wp_ids") or "")

        qs = WpPosts.objects.filter(articles_q()).order_by("-post_date")
        if wp_ids:
            qs = qs.filter(id__in=wp_ids)
        if offset:
            qs = qs[offset:]
        if limit:
            qs = qs[:limit]

        updated = 0
        skipped = 0

        for wp_post in qs:
            wp_id = int(wp_post.id)
            map_row = LegacyWpPostMap.objects.filter(wp_post_id=wp_id).select_related("post").first()
            if not map_row or not map_row.post_id:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"skip wp:{wp_id} — нет Post"))
                continue

            names = wp_post_tag_names(wp_id)
            if dry_run:
                self.stdout.write(f"[dry-run] wp:{wp_id} post:{map_row.post_id} tags={names!r}")
                continue

            with transaction.atomic():
                attached = attach_wp_tags_to_post(map_row.post, wp_id)
            updated += 1
            self.stdout.write(f"wp:{wp_id} → post:{map_row.post_id} tags={attached!r}")

        self.stdout.write(self.style.SUCCESS(f"Теги: обновлено {updated}, пропущено {skipped}"))
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run"))
