from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from legacy_migration.models import LegacyWpUserMap, WpUsers
from legacy_migration.wordpress_hasher import wp_password_hash_usable
from legacy_migration.wp_import import (
    _find_existing_user_by_email,
    upsert_django_user_for_wp_user,
)


def _parse_wp_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        ids.append(int(part))
    return ids


class Command(BaseCommand):
    help = "Импорт wp_users → auth.User (пароль user_pass как на WP) + LegacyWpUserMap + Author"

    def add_arguments(self, parser):
        parser.add_argument(
            "--wp-ids",
            type=str,
            default="",
            help="Только эти WP user ID через запятую (по умолчанию все wp_users)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только отчёт, без записи",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Максимум записей (0 = без лимита)",
        )
        parser.add_argument(
            "--force-password",
            action="store_true",
            help="Перезаписать password из WP даже если у User уже есть пароль",
        )
        parser.add_argument(
            "--min-id",
            type=int,
            default=0,
            help="wp_users.ID >= (для пакетного прогона)",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: int = max(int(options["limit"] or 0), 0)
        force_password: bool = options["force_password"]
        min_id: int = max(int(options["min_id"] or 0), 0)
        wp_ids = _parse_wp_ids(options["wp_ids"])

        qs = WpUsers.objects.all().order_by("id")
        if wp_ids:
            qs = qs.filter(id__in=wp_ids)
        if min_id:
            qs = qs.filter(id__gte=min_id)
        if limit:
            qs = qs[:limit]

        created = 0
        updated_password = 0
        skipped_password = 0
        linked_existing = 0
        no_wp_hash = 0
        maps_linked = 0
        processed = 0

        for wp_user in qs:
            processed += 1
            wp_id = int(wp_user.id)
            usable = wp_password_hash_usable(wp_user.user_pass)
            if dry_run:
                existing_user = _find_existing_user_by_email(wp_user.user_email)
                link_note = (
                    f" link=user:{existing_user.id}"
                    if existing_user
                    and not LegacyWpUserMap.objects.filter(wp_user_id=wp_id, user_id=existing_user.id).exists()
                    else ""
                )
                self.stdout.write(
                    f"[dry-run] wp:{wp_id} login={wp_user.user_login!r} "
                    f"email={wp_user.user_email!r} wp_pass={'yes' if usable else 'no'}{link_note}"
                )
                continue

            with transaction.atomic():
                user, user_created, password_updated, linked_by_email = upsert_django_user_for_wp_user(
                    wp_user,
                    force_password=force_password,
                )
            if user_created:
                created += 1
            if linked_by_email:
                linked_existing += 1
            if password_updated:
                updated_password += 1
            elif not usable:
                no_wp_hash += 1
            else:
                skipped_password += 1
            if LegacyWpUserMap.objects.filter(wp_user_id=wp_id, user_id=user.id).exists():
                maps_linked += 1

            link_tag = " linked-by-email" if linked_by_email else ""
            self.stdout.write(
                f"wp:{wp_id} → user:{user.id} @{user.username} "
                f"email={user.email or '-'}{link_tag}"
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: в БД ничего не записано"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Обработано: {processed}; User создано: {created}; "
                f"привязано по email (без смены пароля): {linked_existing}; "
                f"пароль из WP: {updated_password}; пароль пропущен (уже был): {skipped_password}; "
                f"без хеша WP: {no_wp_hash}; маппингов с user: {maps_linked}"
            )
        )
