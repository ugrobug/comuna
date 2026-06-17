from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from feeds.models import Post
from legacy_migration.models import LegacyWpPostMap, WpPosts
from legacy_migration.pt_tambur_post_links import (
    DEFAULT_LINKS_CSV,
    apply_title_post_links,
    resolve_links_path,
)
from legacy_migration.wp_content import legacy_article_source_url


def _normalize_url(url: str) -> str:
    """
    Привести URL к виду для сравнения:
    - lower
    - убрать trailing slash
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    raw = raw.rstrip("/").lower()
    return raw


def _legacy_url_key_from_wp(wp_post: WpPosts) -> str:
    slug = (wp_post.post_name or "").strip()
    guid = wp_post.guid or ""
    legacy_url = legacy_article_source_url(slug, guid)
    return _normalize_url(legacy_url)


@dataclass
class LinkMatch:
    wp_post_id: int
    post_id: int
    match_source: str


class Command(BaseCommand):
    help = (
        "Связать WP post_id с уже существующими Post в Tambur "
        "(сначала pt_tambur_post_links.csv, затем source_url / raw_data), "
        "чтобы import_wp_posts не создавал дубли."
    )

    def add_arguments(self, parser):
        parser.add_argument("--wp-ids", type=str, default="", help="Только эти WP post ID (через запятую)")
        parser.add_argument("--dry-run", action="store_true", help="Только отчёт")
        parser.add_argument(
            "--title-links-csv",
            type=str,
            default=DEFAULT_LINKS_CSV,
            help="CSV tambur_post_id ↔ wp_post_id (по умолчанию из репо)",
        )
        parser.add_argument(
            "--no-title-links-csv",
            action="store_true",
            help="Не применять файл связей по title",
        )
        parser.add_argument(
            "--only-after-comun",
            action="store_true",
            help="Ограничить кандидатов по Post.source_url posletitrov.ru/articles/ (если выключено — всё равно по этому источнику)",
        )
        parser.add_argument(
            "--force-overwrite-map",
            action="store_true",
            help="Если для wp_post_id уже есть LegacyWpPostMap, перезаписать связанный post_id",
        )
        parser.add_argument(
            "--no-match-by-raw-data",
            action="store_true",
            help="Не использовать Post.raw_data.legacy_wp_id как ключ",
        )
        parser.add_argument(
            "--no-match-by-source-url",
            action="store_true",
            help="Не использовать совпадение Post.source_url с legacy_article_source_url(slug,guid)",
        )

    def handle(self, *args, **options):
        from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids

        dry_run: bool = bool(options["dry_run"])
        force_overwrite: bool = bool(options["force_overwrite_map"])
        match_by_raw_data: bool = not bool(options["no_match_by_raw_data"])
        match_by_source_url: bool = not bool(options["no_match_by_source_url"])
        use_title_csv = not bool(options["no_title_links_csv"])

        if use_title_csv:
            links_path = resolve_links_path(options.get("title_links_csv") or DEFAULT_LINKS_CSV)
            title_stats = apply_title_post_links(
                path=links_path,
                dry_run=dry_run,
                force_overwrite=force_overwrite,
            )
            if title_stats.get("missing_file"):
                self.stderr.write(
                    self.style.WARNING(f"title links: нет файла {links_path} (пропуск)")
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"title links ({links_path.name}): "
                        f"+{title_stats['created']} ~{title_stats['updated']} "
                        f"skip={title_stats['skipped']} err={title_stats['errors']}"
                    )
                )

        wp_ids_raw = options.get("wp_ids") or ""
        wp_ids = _parse_wp_ids(wp_ids_raw)

        from legacy_migration.legacy_posts import articles_q

        qs = WpPosts.objects.filter(articles_q()).order_by("id")
        if wp_ids:
            qs = qs.filter(id__in=wp_ids)
        wp_rows = list(qs)
        if not wp_rows:
            self.stdout.write("WP posts: 0")
            return

        wp_post_id_list = [int(wp.id) for wp in wp_rows]

        existing_maps = LegacyWpPostMap.objects.filter(wp_post_id__in=wp_post_id_list).values(
            "wp_post_id", "post_id"
        )
        existing_map_by_wp_id = {int(r["wp_post_id"]): r["post_id"] for r in existing_maps}

        # Кандидаты Post для сопоставления по уникальным ключам.
        # 1) raw_data.legacy_wp_id (если заполнено на ручных постах)
        # 2) source_url == legacy_article_source_url(slug,guid)
        candidates_q = Q()
        if match_by_raw_data:
            candidates_q |= Q(raw_data__legacy_wp_id__isnull=False)
        if match_by_source_url:
            candidates_q |= Q(source_url__icontains="posletitrov.ru/articles/")
        if not candidates_q:
            raise RuntimeError("Нельзя отключить оба типа сопоставления")

        candidate_posts = Post.objects.filter(candidates_q).only("id", "source_url", "raw_data")

        post_by_raw_legacy_wp_id: dict[int, int] = {}
        post_by_legacy_source_url: dict[str, int] = {}

        for p in candidate_posts:
            raw = p.raw_data if isinstance(p.raw_data, dict) else {}
            if match_by_raw_data:
                legacy_wp_id = raw.get("legacy_wp_id")
                if legacy_wp_id is not None:
                    try:
                        legacy_wp_id_int = int(legacy_wp_id)
                    except (TypeError, ValueError):
                        legacy_wp_id_int = 0
                    if legacy_wp_id_int:
                        post_by_raw_legacy_wp_id[legacy_wp_id_int] = int(p.id)
            if match_by_source_url:
                key = _normalize_url(p.source_url or "")
                if key:
                    post_by_legacy_source_url[key] = int(p.id)

        created = 0
        updated = 0
        skipped = 0
        not_found = 0
        collisions: list[str] = []

        now = timezone.now()

        self.stdout.write(
            f"WP rows={len(wp_rows)} candidates={candidate_posts.count()} dry_run={dry_run}"
        )

        for wp_post in wp_rows:
            wp_id = int(wp_post.id)

            map_post_id = existing_map_by_wp_id.get(wp_id)
            if map_post_id and not force_overwrite:
                skipped += 1
                continue

            matched_post_id: int | None = None
            match_source = ""

            if match_by_raw_data:
                matched_post_id = post_by_raw_legacy_wp_id.get(wp_id)
                if matched_post_id:
                    match_source = "post.raw_data.legacy_wp_id"

            if not matched_post_id and match_by_source_url:
                key = _legacy_url_key_from_wp(wp_post)
                matched_post_id = post_by_legacy_source_url.get(key)
                if matched_post_id:
                    match_source = "Post.source_url == legacy_url"

            if not matched_post_id:
                not_found += 1
                continue

            if not force_overwrite and map_post_id and int(map_post_id) != int(matched_post_id):
                collisions.append(
                    f"wp:{wp_id} existing_post_id={map_post_id} candidate_post_id={matched_post_id}"
                )
                continue

            if dry_run:
                if map_post_id:
                    updated += 1
                else:
                    created += 1
                continue

            with transaction.atomic():
                defaults = {
                    "legacy_slug": (wp_post.post_name or "").strip(),
                    "legacy_url": legacy_article_source_url(
                        (wp_post.post_name or "").strip(), wp_post.guid or ""
                    ),
                    "post_id": int(matched_post_id),
                    "imported_at": now,
                }
                # update_or_create нельзя использовать напрямую, т.к. нужно аккуратно
                # обрабатывать case force_overwrite.
                LegacyWpPostMap.objects.update_or_create(
                    wp_post_id=wp_id,
                    defaults={
                        "legacy_slug": defaults["legacy_slug"],
                        "legacy_url": defaults["legacy_url"],
                        "post_id": defaults["post_id"],
                        "imported_at": defaults["imported_at"],
                    },
                )

            if map_post_id:
                updated += 1
            else:
                created += 1

        if collisions:
            self.stderr.write(self.style.WARNING("Коллизии (нужен --force-overwrite-map):"))
            for msg in collisions[:30]:
                self.stderr.write(self.style.WARNING(msg))
            if len(collisions) > 30:
                self.stderr.write(self.style.WARNING(f"... ещё {len(collisions) - 30} коллизий"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: created={created} updated={updated} skipped={skipped} "
                f"not_found={not_found} collisions={len(collisions)}"
            )
        )

