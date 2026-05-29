from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from feeds.models import Author
from legacy_migration.legacy_posts import articles_q
from legacy_migration.models import LegacyWpUserMap
from legacy_migration.models import WpPosts, WpUsers
from legacy_migration.wp_import import resolve_author_for_wp_user


class Command(BaseCommand):
    help = "Импорт авторов статей WP → feeds.Author + LegacyWpUserMap"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только отчёт, без записи в Postgres",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Максимум WP users (0 = без лимита)",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: int = max(int(options["limit"] or 0), 0)

        wp_author_ids = list(
            WpPosts.objects.filter(articles_q())
            .values_list("post_author", flat=True)
            .distinct()
        )
        wp_author_ids = [int(x) for x in wp_author_ids if x]

        qs = WpUsers.objects.filter(id__in=wp_author_ids).order_by("id")
        if limit:
            qs = qs[:limit]

        created_authors = 0
        linked_authors = 0
        maps_created = 0
        maps_updated = 0
        skipped = 0

        for wp_user in qs:
            wp_id = int(wp_user.id)
            display = (wp_user.display_name or "").strip()

            if dry_run:
                self.stdout.write(
                    f"[dry-run] wp:{wp_id} login={wp_user.user_login!r} → Author"
                )
                continue

            with transaction.atomic():
                author, author_created = resolve_author_for_wp_user(
                    wp_user_id=wp_id,
                    user_login=wp_user.user_login,
                    user_nicename=wp_user.user_nicename,
                    display_name=display,
                )
                if author_created:
                    created_authors += 1
                else:
                    linked_authors += 1

                map_row, map_created = LegacyWpUserMap.objects.get_or_create(
                    wp_user_id=wp_id,
                    defaults={
                        "wp_login": wp_user.user_login or "",
                        "wp_email": wp_user.user_email or "",
                        "wp_display_name": display,
                        "author": author,
                        "imported_at": timezone.now(),
                    },
                )
                if map_created:
                    maps_created += 1
                else:
                    changed = False
                    if map_row.author_id != author.id:
                        map_row.author = author
                        changed = True
                    if map_row.wp_login != (wp_user.user_login or ""):
                        map_row.wp_login = wp_user.user_login or ""
                        changed = True
                    if map_row.wp_email != (wp_user.user_email or ""):
                        map_row.wp_email = wp_user.user_email or ""
                        changed = True
                    if map_row.wp_display_name != display:
                        map_row.wp_display_name = display
                        changed = True
                    if changed:
                        map_row.imported_at = timezone.now()
                        map_row.save()
                        maps_updated += 1
                    else:
                        skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                "WP authors with articles: "
                f"{len(wp_author_ids)}; processed: {qs.count() if not limit else min(limit, len(wp_author_ids))}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: в БД ничего не записано"))
            return

        self.stdout.write(
            f"Author created: {created_authors}; reused: {linked_authors}; "
            f"maps +{maps_created} ~{maps_updated}; unchanged maps: {skipped}; "
            f"total Author in DB: {Author.objects.count()}"
        )
