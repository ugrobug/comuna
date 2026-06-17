from __future__ import annotations

from django.core.management.base import BaseCommand

from legacy_migration.models import LegacyWpUserMap
from legacy_migration.wp_import import ensure_author_admin_for_legacy_map


def _parse_wp_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


class Command(BaseCommand):
    help = (
        "Создать AuthorAdmin (verified) для пар user+author из LegacyWpUserMap. "
        "Нужно после import_wp_users, чтобы /{author} редиректил на /id{user}."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wp-ids",
            type=str,
            default="",
            help="Только эти WP user ID через запятую",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только отчёт",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Максимум строк (0 = без лимита)",
        )
        parser.add_argument(
            "--min-id",
            type=int,
            default=0,
            help="wp_user_id >=",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: int = max(int(options["limit"] or 0), 0)
        min_id: int = max(int(options["min_id"] or 0), 0)
        wp_ids = _parse_wp_ids(options["wp_ids"])

        qs = (
            LegacyWpUserMap.objects.filter(user_id__isnull=False, author_id__isnull=False)
            .select_related("user", "author")
            .order_by("wp_user_id")
        )
        if wp_ids:
            qs = qs.filter(wp_user_id__in=wp_ids)
        if min_id:
            qs = qs.filter(wp_user_id__gte=min_id)
        if limit:
            qs = qs[:limit]

        stats = {
            "created": 0,
            "verified": 0,
            "exists": 0,
            "missing": 0,
            "conflict": 0,
        }

        for map_row in qs:
            result = ensure_author_admin_for_legacy_map(map_row, dry_run=dry_run)
            stats[result] = stats.get(result, 0) + 1
            if result in {"created", "verified", "conflict"}:
                self.stdout.write(
                    f"wp:{map_row.wp_user_id} author:{map_row.author_id} "
                    f"(@{map_row.author.username}) user:{map_row.user_id} "
                    f"(@{map_row.user.username}) → {result}"
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: AuthorAdmin не создавались"))

        self.stdout.write(
            self.style.SUCCESS(
                "AuthorAdmin: "
                f"created={stats['created']} verified={stats['verified']} "
                f"exists={stats['exists']} missing={stats['missing']} "
                f"conflict={stats['conflict']}"
            )
        )
