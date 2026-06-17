from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from legacy_migration.pt_analytics_redirects import (
    build_analytics_supplement_rows,
    format_analytics_supplement_json,
)


class Command(BaseCommand):
    help = (
        "Доп. редиректы из CSV «Просмотры URL» Метрики: вложенные ЧПУ ПТ "
        "(/articles/movies/reviews/…, /news/tv-news/…), которых нет в export_wp_redirects "
        "(там в основном /articles/{slug}/)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            required=True,
            help="Путь к CSV (Столбец1=URL, Столбец2=просмотры)",
        )
        parser.add_argument(
            "-o",
            "--output",
            type=str,
            default="",
            help="Файл JSON для Redirection; пусто — stdout",
        )
        parser.add_argument(
            "--existing",
            type=str,
            default="",
            help="Уже выгруженный pt-redirection-full.json — не дублировать match",
        )
        parser.add_argument("--min-views", type=int, default=1)
        parser.add_argument(
            "--no-db-export-check",
            action="store_true",
            help="Не сверять с collect_redirect_rows в БД (только --existing)",
        )
        parser.add_argument("--compact", action="store_true")

    def handle(self, *args, **options):
        csv_path = Path(options["csv"]).expanduser()
        if not csv_path.is_file():
            raise CommandError(f"CSV не найден: {csv_path}")

        existing = Path(options["existing"]).expanduser() if options.get("existing") else None
        if existing and not existing.is_file():
            raise CommandError(f"--existing не найден: {existing}")

        built = build_analytics_supplement_rows(
            csv_path,
            min_views=max(int(options["min_views"] or 1), 1),
            existing_json=existing,
            use_db_export_paths=not options["no_db_export_check"],
        )

        body = format_analytics_supplement_json(built.rows, compact=bool(options["compact"]))

        out = (options.get("output") or "").strip()
        if out:
            Path(out).write_text(body, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Записано {len(built.rows)} правил → {out}"))
        else:
            self.stdout.write(body)

        self.stdout.write(
            f"CSV paths (pt): {built.pt_urls}; "
            f"новых редиректов: {len(built.rows)}; "
            f"уже в export: {built.skipped_already_exported}; "
            f"пропуск шаблон: {built.skipped_pattern}; "
            f"без поста: {built.skipped_no_post}"
        )
        if built.unresolved_samples:
            self.stdout.write("Примеры без поста:")
            for sample in built.unresolved_samples[:15]:
                self.stdout.write(f"  {sample}")
