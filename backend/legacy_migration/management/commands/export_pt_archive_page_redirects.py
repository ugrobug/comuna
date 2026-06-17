from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from legacy_migration.pt_archive_page_redirects import (
    TAMBUR_COMUN_FILMY,
    TAMBUR_COMUN_SERIALY,
    format_archive_pages_json,
    paths_for_section,
    paths_from_csv_archive_pages,
    redirection_plugin_items_to_url,
)


class Command(BaseCommand):
    help = (
        "JSON для Redirection: /articles/movies/page/N/ → category=filmy, "
        "/articles/tv-series/page/N/ → category=serialy. Пути из CSV Метрики и/или --max-page."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            type=str,
            default="",
            help="CSV просмотров URL (дополняет список страниц из трафика)",
        )
        parser.add_argument("--min-views", type=int, default=1)
        parser.add_argument(
            "-o-movies",
            "--output-movies",
            type=str,
            default="",
            help="Файл JSON для /articles/movies/page/…",
        )
        parser.add_argument(
            "-o-tv-series",
            "--output-tv-series",
            type=str,
            default="",
            help="Файл JSON для /articles/tv-series/page/…",
        )
        parser.add_argument(
            "--movies-max-page",
            type=int,
            default=0,
            help="Добавить страницы 1..N для movies (0 = только из CSV)",
        )
        parser.add_argument(
            "--tv-series-max-page",
            type=int,
            default=0,
            help="Добавить страницы 1..N для tv-series (0 = только из CSV)",
        )
        parser.add_argument("--compact", action="store_true")

    def handle(self, *args, **options):
        movies_paths: set[str] = set()
        tv_paths: set[str] = set()

        csv_raw = (options.get("csv") or "").strip()
        if csv_raw:
            csv_path = Path(csv_raw).expanduser()
            if not csv_path.is_file():
                raise CommandError(f"CSV не найден: {csv_path}")
            built = paths_from_csv_archive_pages(
                csv_path, min_views=max(int(options["min_views"] or 1), 1)
            )
            movies_paths.update(built.movies_paths)
            tv_paths.update(built.tv_series_paths)

        movies_max = max(int(options.get("movies_max_page") or 0), 0)
        tv_max = max(int(options.get("tv_series_max_page") or 0), 0)
        if movies_max:
            movies_paths.update(paths_for_section("movies", max_page=movies_max))
        if tv_max:
            tv_paths.update(paths_for_section("tv-series", max_page=tv_max))

        out_movies = (options.get("output_movies") or "").strip()
        out_tv = (options.get("output_tv_series") or "").strip()
        if not out_movies and not out_tv:
            raise CommandError("Укажите -o-movies и/или -o-tv-series")

        compact = bool(options.get("compact"))

        if out_movies:
            items = redirection_plugin_items_to_url(sorted(movies_paths), TAMBUR_COMUN_FILMY)
            path = Path(out_movies)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(format_archive_pages_json(items, compact=compact), encoding="utf-8")
            self.stdout.write(
                self.style.SUCCESS(f"movies: {len(items)} правил → {path}")
            )

        if out_tv:
            items = redirection_plugin_items_to_url(sorted(tv_paths), TAMBUR_COMUN_SERIALY)
            path = Path(out_tv)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(format_archive_pages_json(items, compact=compact), encoding="utf-8")
            self.stdout.write(
                self.style.SUCCESS(f"tv-series: {len(items)} правил → {path}")
            )

        if not movies_paths and out_movies:
            self.stdout.write(self.style.WARNING("movies: 0 путей (добавьте --csv или --movies-max-page)"))
        if not tv_paths and out_tv:
            self.stdout.write(self.style.WARNING("tv-series: 0 путей (добавьте --csv или --tv-series-max-page)"))
