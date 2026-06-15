from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids
from legacy_migration.models import LegacyWpPostMap
from legacy_migration.wp_redirects import (
    RedirectBuildResult,
    TagRedirectBuildResult,
    collect_redirect_rows,
    collect_tag_redirect_rows,
    format_csv,
    format_json,
    format_nginx_map,
    format_redirection_plugin_csv,
    format_redirection_plugin_json,
    merge_redirect_rows,
)


class Command(BaseCommand):
    help = "Файл редиректов ПТ → Tambur из LegacyWpPostMap (для импорта в Redirection на ПТ)"

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
            choices=(
                "redirection-json",
                "redirection-csv",
                "nginx-map",
                "csv",
                "json",
            ),
            default="redirection-json",
        )
        parser.add_argument("--wp-ids", type=str, default="", help="Только эти wp_post_id")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument(
            "--tambur-base-url",
            type=str,
            default="https://tambur.pub",
            help="Базовый URL цели 301 (redirection-json / redirection-csv)",
        )
        parser.add_argument("--no-guid", action="store_true", help="Не добавлять пути из wp_posts.guid")
        parser.add_argument("--no-canonical", action="store_true")
        parser.add_argument("--no-slug-fallback", action="store_true")
        parser.add_argument(
            "--include-tags",
            action="store_true",
            help="Добавить /tag/{wp_slug}/ → /tags/{lemma}/ (wp_terms.slug → lemma как у import_wp_post_tags)",
        )
        parser.add_argument(
            "--tags-all",
            action="store_true",
            help="Все post_tag из зеркала (с --tags-min-count); иначе только метки постов из выборки map",
        )
        parser.add_argument(
            "--tags-min-count",
            type=int,
            default=1,
            help="Минимум wp_term_taxonomy.count для --tags-all (0 = без фильтра)",
        )

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

        tag_result: TagRedirectBuildResult | None = None
        merge_conflicts: list[str] = []
        rows = result.rows
        if options["include_tags"]:
            mapped_ids = None if options["tags_all"] else [int(m.wp_post_id) for m in maps]
            min_count = int(options["tags_min_count"]) if options["tags_all"] else 0
            tag_result = collect_tag_redirect_rows(
                mapped_wp_post_ids=mapped_ids,
                min_term_count=max(min_count, 0),
            )
            rows, merge_conflicts = merge_redirect_rows(result.rows, tag_result.rows)

        unique_from = len({r.from_path for r in rows})
        tambur_base = (options.get("tambur_base_url") or "https://tambur.pub").strip()
        fmt = options["format"]
        if fmt == "csv":
            body = format_csv(rows)
        elif fmt == "json":
            body = format_json(rows)
        elif fmt == "redirection-json":
            body = format_redirection_plugin_json(rows, tambur_base_url=tambur_base)
        elif fmt == "redirection-csv":
            body = format_redirection_plugin_csv(rows, tambur_base_url=tambur_base)
        elif fmt == "nginx-map":
            body = format_nginx_map(rows)
        else:
            body = format_redirection_plugin_json(rows, tambur_base_url=tambur_base)

        out_path = (options.get("output") or "").strip()
        report = self.stderr
        if out_path:
            path = Path(out_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            report.write(self.style.SUCCESS(f"Записано {path} ({unique_from} путей)"))
        else:
            self.stdout.write(body)
            report = self.stderr

        report.write(
            f"маппингов={len(maps)} строк={len(rows)} уникальных from={unique_from} "
            f"skip_post={result.skipped_no_post} конфликтов_post={len(result.conflicts)}"
        )
        if tag_result is not None:
            report.write(
                f" тегов_строк={len(tag_result.rows)} skip_tag_slug={tag_result.skipped_no_slug} "
                f"skip_tag_dest={tag_result.skipped_no_dest} конфликтов_tag={len(tag_result.conflicts)} "
                f"merge={len(merge_conflicts)}"
            )
        report.write("\n")
        for msg in result.conflicts[:20]:
            report.write(self.style.WARNING(f"{msg}\n"))
        if tag_result:
            for msg in tag_result.conflicts[:20]:
                report.write(self.style.WARNING(f"{msg}\n"))
        for msg in merge_conflicts[:20]:
            report.write(self.style.WARNING(f"{msg}\n"))
        total_conflicts = len(result.conflicts) + (
            len(tag_result.conflicts) if tag_result else 0
        ) + len(merge_conflicts)
        if total_conflicts > 20:
            report.write(self.style.WARNING(f"… ещё конфликтов (см. выше)\n"))
