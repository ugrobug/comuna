from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids
from legacy_migration.models import LegacyWpPostMap
from legacy_migration.wp_redirects import (
    RedirectBuildResult,
    collect_redirect_rows,
    format_csv,
    format_json,
    format_nginx_map,
)


class Command(BaseCommand):
    help = "Файл редиректов ПТ → /b/post/{id} из LegacyWpPostMap (для nginx map на стенде/prod)"

    def add_arguments(self, parser):
        parser.add_argument(
            "-o",
            "--output",
            type=str,
            default="",
            help="Путь к файлу (иначе stdout)",
        )
        parser.add_argument(
            "--format",
            choices=("nginx-map", "csv", "json"),
            default="nginx-map",
        )
        parser.add_argument("--wp-ids", type=str, default="", help="Только эти wp_post_id")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--no-guid", action="store_true", help="Не добавлять пути из wp_posts.guid")
        parser.add_argument("--no-canonical", action="store_true")
        parser.add_argument("--no-slug-fallback", action="store_true")

    def handle(self, *args, **options):
        wp_ids = _parse_wp_ids(options.get("wp_ids") or "")
        limit = max(int(options["limit"] or 0), 0)

        qs = LegacyWpPostMap.objects.filter(post_id__isnull=False).select_related("post").order_by(
            "wp_post_id"
        )
        if wp_ids:
            qs = qs.filter(wp_post_id__in=wp_ids)
        if limit:
            qs = qs[:limit]

        maps = list(qs)
        result: RedirectBuildResult = collect_redirect_rows(
            maps,
            include_wp_guid=not options["no_guid"],
            include_canonical_meta=not options["no_canonical"],
            include_slug_fallback=not options["no_slug_fallback"],
        )

        unique_from = len({r.from_path for r in result.rows})
        if options["format"] == "csv":
            body = format_csv(result.rows)
        elif options["format"] == "json":
            body = format_json(result.rows)
        else:
            body = format_nginx_map(result.rows)

        out_path = (options.get("output") or "").strip()
        if out_path:
            path = Path(out_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Записано {path} ({unique_from} путей)"))
        else:
            self.stdout.write(body)

        self.stdout.write(
            f"маппингов={len(maps)} строк={len(result.rows)} уникальных from={unique_from} "
            f"skip={result.skipped_no_post} конфликтов={len(result.conflicts)}"
        )
        for msg in result.conflicts[:20]:
            self.stdout.write(self.style.WARNING(msg))
        if len(result.conflicts) > 20:
            self.stdout.write(self.style.WARNING(f"… ещё {len(result.conflicts) - 20} конфликтов"))
