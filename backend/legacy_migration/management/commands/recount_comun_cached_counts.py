from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from communities.models import Comun
from legacy_migration.comun_cached_counts import (
    compute_comun_cached_counts,
    recalculate_comun_cached_counts,
)
from legacy_migration.pt_comun import PT_COMUN_SLUG


class Command(BaseCommand):
    help = (
        "Пересчёт Comun.subscribers_count и Comun.authors_count по фактическим данным. "
        "Нужно после массового import_wp_posts + assign_wp_post_comuns: счётчики на карточке "
        "не обновляются при импорте (только при живой публикации / смене подписки в ленте)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--comun-slug",
            type=str,
            default=PT_COMUN_SLUG,
            help=f"Slug коммуны (по умолчанию {PT_COMUN_SLUG})",
        )
        parser.add_argument(
            "--comun-id",
            type=int,
            default=0,
            help="ID коммуны (если задан, slug игнорируется)",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        comun_id = int(options.get("comun_id") or 0)
        comun_slug = (options.get("comun_slug") or PT_COMUN_SLUG).strip()
        dry_run: bool = options["dry_run"]

        if comun_id:
            comun = Comun.objects.filter(id=comun_id).first()
        else:
            comun = Comun.objects.filter(slug=comun_slug).first()

        if not comun:
            raise CommandError(f"Коммуна не найдена (id={comun_id or '-'}, slug={comun_slug!r})")

        old_subs = int(comun.subscribers_count or 0)
        old_authors = int(comun.authors_count or 0)

        counts = (
            compute_comun_cached_counts(comun)
            if dry_run
            else recalculate_comun_cached_counts(comun)
        )
        prefix = "[dry-run] " if dry_run else ""
        style = self.style.WARNING if dry_run else self.style.SUCCESS
        self.stdout.write(
            style(
                f"{prefix}comun {comun.slug} (id={comun.id}): "
                f"подписчики {old_subs} → {counts['subscribers_count']}, "
                f"авторы {old_authors} → {counts['authors_count']}"
            )
        )
        if dry_run:
            return
