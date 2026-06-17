from __future__ import annotations

import json
import zipfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

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
    redirection_plugin_items,
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
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=0,
            help="redirection-json: разбить на части по N правил (файлы …-part001.json)",
        )
        parser.add_argument(
            "--compact",
            action="store_true",
            help="redirection-json: без отступов (меньше размер файла)",
        )
        parser.add_argument(
            "--chunk-zip",
            action="store_true",
            help="С --chunk-size: собрать part*.json в один .zip (имя: <stem>-parts.zip)",
        )
        parser.add_argument(
            "--tags-only",
            action="store_true",
            help="Только /tag/… → /tags/… (без статей). По умолчанию все post_tag (--tags-all)",
        )

    def handle(self, *args, **options):
        tags_only: bool = bool(options.get("tags_only"))
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
        tag_result: TagRedirectBuildResult | None = None
        merge_conflicts: list[str] = []

        if tags_only:
            result = RedirectBuildResult()
            if wp_ids and not options["tags_all"]:
                mapped_ids = [int(m.wp_post_id) for m in maps]
                min_count = 0
            else:
                mapped_ids = None
                min_count = max(int(options["tags_min_count"]), 0) or 1
            tag_result = collect_tag_redirect_rows(
                mapped_wp_post_ids=mapped_ids,
                min_term_count=min_count,
            )
            rows = tag_result.rows
        else:
            result = collect_redirect_rows(
                maps,
                include_wp_guid=not options["no_guid"],
                include_canonical_meta=not options["no_canonical"],
                include_slug_fallback=not options["no_slug_fallback"],
            )
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
        chunk_size = max(int(options.get("chunk_size") or 0), 0)
        compact: bool = bool(options.get("compact"))
        chunk_zip: bool = bool(options.get("chunk_zip"))

        out_path = (options.get("output") or "").strip()
        report = self.stderr

        if fmt == "redirection-json" and chunk_size > 0 and not out_path:
            raise CommandError("Для --chunk-size нужен -o /tmp/pt-redirection-full.json")

        if fmt == "csv":
            body = format_csv(rows)
        elif fmt == "json":
            body = format_json(rows)
        elif fmt == "redirection-json":
            if chunk_size > 0 and out_path:
                items = redirection_plugin_items(rows, tambur_base_url=tambur_base)
                base = Path(out_path)
                base.parent.mkdir(parents=True, exist_ok=True)
                stem = base.stem
                suffix = base.suffix or ".json"
                written: list[Path] = []
                for idx in range(0, len(items), chunk_size):
                    part_no = idx // chunk_size + 1
                    chunk = items[idx : idx + chunk_size]
                    if compact:
                        body = json.dumps(chunk, ensure_ascii=False, separators=(",", ":")) + "\n"
                    else:
                        body = json.dumps(chunk, ensure_ascii=False, indent=2) + "\n"
                    part_path = base.parent / f"{stem}-part{part_no:03d}{suffix}"
                    part_path.write_text(body, encoding="utf-8")
                    written.append(part_path)
                report.write(
                    self.style.SUCCESS(
                        f"Записано {len(written)} файлов по {chunk_size} правил "
                        f"(всего {len(items)}): {written[0].name} … {written[-1].name}"
                    )
                )
                if chunk_zip and written:
                    zip_path = base.parent / f"{stem}-parts.zip"
                    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                        for part_path in written:
                            zf.write(part_path, arcname=part_path.name)
                    report.write(
                        self.style.SUCCESS(f"Архив: {zip_path} ({len(written)} JSON внутри)")
                    )
                body = ""
            else:
                body = format_redirection_plugin_json(
                    rows, tambur_base_url=tambur_base, compact=compact
                )
        elif fmt == "redirection-csv":
            body = format_redirection_plugin_csv(rows, tambur_base_url=tambur_base)
        elif fmt == "nginx-map":
            body = format_nginx_map(rows)
        else:
            body = format_redirection_plugin_json(
                rows, tambur_base_url=tambur_base, compact=compact
            )

        if body and out_path:
            path = Path(out_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
            report.write(self.style.SUCCESS(f"Записано {path} ({unique_from} путей)"))
        elif body:
            self.stdout.write(body)
            report = self.stderr

        report.write(
            f"маппингов={len(maps)} строк={len(rows)} уникальных from={unique_from} "
            f"skip_post={result.skipped_no_post} конфликтов_post={len(result.conflicts)}"
        )
        if tags_only:
            report.write(" [только теги]")
        if tag_result is not None:
            report.write(
                f" тегов_строк={len(tag_result.rows)} skip_tag_slug={tag_result.skipped_no_slug} "
                f"skip_tag_dest={tag_result.skipped_no_dest} конфликтов_tag={len(tag_result.conflicts)} "
                f"merge={len(merge_conflicts)}"
            )
        report.write("\n")
        if not tags_only:
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
