from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from communities.models import Comun
from legacy_migration.models import LegacyWpUserMap
from legacy_migration.pt_comun import PT_COMUN_SLUG
from legacy_migration.wp_pt_comun_moderators import (
    add_pt_author_moderators,
    pt_imported_post_author_ids,
    user_ids_for_pt_authors,
)


class Command(BaseCommand):
    help = (
        "Добавить модераторами коммуны after_the_credits пользователей сайта, "
        "связанных с авторами импортированных статей ПТ (LegacyWpPostMap). "
        "Существующих модераторов не снимает."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--comun-slug",
            type=str,
            default=PT_COMUN_SLUG,
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--all-wp-mapped-users",
            action="store_true",
            help="Все user_id из LegacyWpUserMap (не только авторы с импортированными постами)",
        )
        parser.add_argument(
            "--list-usernames",
            action="store_true",
            help="Вывести username пользователей, которых добавим (dry-run или вместе с записью)",
        )

    def handle(self, *args, **options):
        comun_slug = (options.get("comun_slug") or PT_COMUN_SLUG).strip()
        dry_run: bool = options["dry_run"]
        all_mapped: bool = options["all_wp_mapped_users"]
        list_names: bool = options["list_usernames"]

        comun = Comun.objects.filter(slug=comun_slug, is_active=True).first()
        if not comun:
            raise CommandError(f"Нет активной коммуны slug={comun_slug!r}")

        if all_mapped:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user_ids = {
                int(uid)
                for uid in LegacyWpUserMap.objects.filter(user_id__isnull=False).values_list("user_id", flat=True)
            }
            author_ids = None
        else:
            author_ids = pt_imported_post_author_ids()
            user_ids = user_ids_for_pt_authors(author_ids=author_ids)

        if list_names:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            existing = set(comun.moderators.values_list("id", flat=True))
            to_add = sorted(user_ids - existing)
            for u in User.objects.filter(id__in=to_add).order_by("username"):
                self.stdout.write(f"  + @{u.username} (id={u.id})")

        if all_mapped:
            existing = set(comun.moderators.values_list("id", flat=True))
            to_add = sorted(user_ids - existing)
            stats = {
                "author_count": 0,
                "user_candidates": len(user_ids),
                "added": len(to_add),
                "already_moderators": len(user_ids & existing),
                "authors_without_site_user": 0,
            }
            if not dry_run and to_add:
                comun.moderators.add(*to_add)
        else:
            stats = add_pt_author_moderators(comun, dry_run=dry_run, author_ids=author_ids)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}comun {comun.slug}: авторов с постами ПТ={stats['author_count']}, "
                f"пользователей к добавлению={stats['user_candidates']}, "
                f"добавлено модераторов={stats['added']}, "
                f"уже были={stats['already_moderators']}, "
                f"авторов без User на сайте={stats['authors_without_site_user']}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: moderators не менялись"))
