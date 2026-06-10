from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids
from legacy_migration.models import LegacyWpPostMap
from legacy_migration.pt_comun import PT_CATEGORY_SLUGS, PT_COMUN_SLUG, decide_pt_comun, legacy_pt_path_for_map
from legacy_migration.wp_comun_assign import assign_maps, load_pt_comun_context


class Command(BaseCommand):
    help = (
        "ПТ → коммуна after_the_credits + категории filmy/serialy/animatsiya "
        "(ComunPostCategoryAssignment)"
    )

    def add_arguments(self, parser):
        parser.add_argument("--wp-ids", type=str, default="")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--offset", type=int, default=0)
        parser.add_argument(
            "--comun-slug",
            type=str,
            default=PT_COMUN_SLUG,
            help=f"Slug коммуны (по умолчанию {PT_COMUN_SLUG})",
        )
        parser.add_argument("--no-path-tags", action="store_true", help="Без тегов interview/quiz из path")

    def handle(self, *args, **options):
        comun_slug = (options.get("comun_slug") or PT_COMUN_SLUG).strip()
        wp_ids = _parse_wp_ids(options.get("wp_ids") or "")
        limit = max(int(options["limit"] or 0), 0)
        offset = max(int(options["offset"] or 0), 0)
        dry_run: bool = options["dry_run"]

        comun, categories = load_pt_comun_context(comun_slug)
        if not dry_run:
            if not comun:
                raise CommandError(
                    f"Нет активной коммуны slug={comun_slug!r}. Создай на Tambur (Рома) перед импортом."
                )
            missing = [s for s in PT_CATEGORY_SLUGS if s not in categories]
            if missing:
                raise CommandError(
                    f"В коммуне {comun_slug!r} нет активных категорий: {missing}. "
                    f"Нужны slug: {list(PT_CATEGORY_SLUGS)}"
                )

        qs = LegacyWpPostMap.objects.filter(post_id__isnull=False).select_related("post").order_by(
            "wp_post_id"
        )
        if wp_ids:
            qs = qs.filter(wp_post_id__in=wp_ids)
        if offset:
            qs = qs[offset:]
        if limit:
            qs = qs[:limit]

        maps = list(qs)
        if dry_run:
            for map_row in maps[:50]:
                path = legacy_pt_path_for_map(map_row)
                d = decide_pt_comun(path, wp_post_id=int(map_row.wp_post_id))
                self.stdout.write(
                    f"[dry-run] wp:{map_row.wp_post_id} post:{map_row.post_id} "
                    f"→ {comun_slug}?category={d.category_slug} ({d.reason}) path={path!r}"
                )
            if len(maps) > 50:
                self.stdout.write(f"… ещё {len(maps) - 50} постов")

        stats = assign_maps(
            maps,
            comun_slug=comun_slug,
            dry_run=dry_run,
            with_path_tags=not options["no_path_tags"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Коммуна {comun_slug}: назначено {stats.assigned}, "
                f"без поста {stats.skipped_no_post}, без коммуны {stats.skipped_no_comun}, "
                f"без категории {stats.skipped_no_category}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run"))
