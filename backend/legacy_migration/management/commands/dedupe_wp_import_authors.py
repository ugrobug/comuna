from __future__ import annotations

from django.core.management.base import BaseCommand

from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids
from legacy_migration.models import LegacyWpUserMap
from legacy_migration.wp_import import dedupe_wp_import_authors_for_user


class Command(BaseCommand):
    help = (
        "Слить дубликаты feeds.Author от импорта WP (jeckmod-wp266, jeckmod-wp266-2, …) "
        "в одного на wp_user_id. Если найден Author с username=base и title==display_name из WP — "
        "сливаем в него (это «оригинал»)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wp-ids",
            type=str,
            default="",
            help="Только эти WP user ID; пусто — все из LegacyWpUserMap",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        wp_ids = _parse_wp_ids(options.get("wp_ids") or "")

        if wp_ids:
            id_list = wp_ids
        else:
            id_list = list(LegacyWpUserMap.objects.order_by("wp_user_id").values_list("wp_user_id", flat=True))

        merged_users = 0
        removed_authors = 0
        moved_posts = 0

        for wp_user_id in id_list:
            result = dedupe_wp_import_authors_for_user(int(wp_user_id), dry_run=dry_run)
            status = str(result.get("status"))
            if status in {"merged", "dry-run"} and int(result.get("merged") or 0) > 0:
                merged_users += 1
                removed_authors += int(result["merged"])
                moved_posts += int(result.get("posts_moved") or 0)
                self.stdout.write(
                    f"wp:{wp_user_id} → @{result.get('canonical_username')} "
                    f"(id={result.get('canonical_id')}) "
                    f"удалить author_id={result.get('dup_ids')} "
                    f"постов перенесено={result.get('posts_moved')}"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: БД не менялась"))
        self.stdout.write(
            self.style.SUCCESS(
                f"wp_users с дублями: {merged_users}; "
                f"author удалено: {removed_authors}; постов перенесено: {moved_posts}"
            )
        )
