from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from feeds.models import Post
from feeds.views import _generate_manual_message_id
from legacy_migration.legacy_posts import articles_q, wp_has_ez_toc
from legacy_migration.models import LegacyWpPostMap, LegacyWpUserMap, WpPostmeta, WpPosts
from legacy_migration.pt_comun import PT_COMUN_SLUG, merge_pt_comun_manual_membership_raw
from legacy_migration.wp_content import (
    editor_payload_to_content_string,
    gutenberg_to_editor_payload,
    legacy_article_source_url,
)


def _parse_wp_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in (raw or "").replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.isdigit():
            raise CommandError(f"Некорректный WP ID: {part!r}")
        ids.append(int(part))
    return ids


class Command(BaseCommand):
    help = "Импорт статей WP (post/publish) → feeds.Post + LegacyWpPostMap"

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
            help="Максимум постов (0 = без лимита)",
        )
        parser.add_argument(
            "--wp-ids",
            type=str,
            default="",
            help="Список WP post ID через запятую (пилот)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Перезаписать уже импортированные (по LegacyWpPostMap): контент и raw_data "
                "(в т.ч. с --comun-manual-membership)"
            ),
        )
        parser.add_argument(
            "--offset",
            type=int,
            default=0,
            help="Пропустить N записей после сортировки по post_date DESC",
        )
        parser.add_argument(
            "--comun-manual-membership",
            action="store_true",
            help=(
                "raw_data source=manual_comun + comun_slug для ленты after_the_credits "
                "(вариант B до правки membership в communities)"
            ),
        )
        parser.add_argument(
            "--comun-slug",
            type=str,
            default=PT_COMUN_SLUG,
            help=f"comun_slug в raw_data (с --comun-manual-membership), по умолчанию {PT_COMUN_SLUG}",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        limit: int = max(int(options["limit"] or 0), 0)
        offset: int = max(int(options["offset"] or 0), 0)
        force: bool = options["force"]
        wp_ids = _parse_wp_ids(options.get("wp_ids") or "")
        comun_manual_membership: bool = bool(options["comun_manual_membership"])
        comun_slug: str = (options.get("comun_slug") or PT_COMUN_SLUG).strip()

        qs = WpPosts.objects.filter(articles_q()).order_by("-post_date")
        if wp_ids:
            qs = qs.filter(id__in=wp_ids)
        if offset:
            qs = qs[offset:]
        if limit:
            qs = qs[:limit]

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        for wp_post in qs:
            wp_id = int(wp_post.id)
            slug = (wp_post.post_name or "").strip()

            try:
                result = self._import_one(
                    wp_post,
                    dry_run=dry_run,
                    force=force,
                    comun_manual_membership=comun_manual_membership,
                    comun_slug=comun_slug,
                )
            except Exception as exc:
                errors += 1
                self.stderr.write(self.style.ERROR(f"wp:{wp_id} {exc}"))
                continue

            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Готово: +{created} ~{updated} skip={skipped} err={errors}"
            )
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: в БД ничего не записано"))

    def _import_one(
        self,
        wp_post: WpPosts,
        *,
        dry_run: bool,
        force: bool,
        comun_manual_membership: bool = False,
        comun_slug: str = PT_COMUN_SLUG,
    ) -> str:
        wp_id = int(wp_post.id)
        slug = (wp_post.post_name or "").strip()

        existing_map = LegacyWpPostMap.objects.filter(wp_post_id=wp_id).select_related("post").first()
        if existing_map and existing_map.post_id and not force:
            self.stdout.write(f"skip wp:{wp_id} → post:{existing_map.post_id}")
            return "skipped"

        author_map = LegacyWpUserMap.objects.filter(wp_user_id=int(wp_post.post_author)).first()
        if not author_map or not author_map.author_id:
            raise CommandError(
                f"нет LegacyWpUserMap для wp_user_id={wp_post.post_author} "
                f"(сначала import_wp_authors)"
            )

        include_toc = wp_has_ez_toc(wp_id)
        payload = gutenberg_to_editor_payload(
            wp_post.post_content or "",
            post_excerpt=wp_post.post_excerpt or "",
            include_toc=include_toc,
        )
        content = editor_payload_to_content_string(payload)
        block_count = len(payload.get("blocks") or [])

        title = (wp_post.post_title or "").strip()[:255]
        publish_at = wp_post.post_date
        if publish_at and timezone.is_naive(publish_at):
            publish_at = timezone.make_aware(publish_at, timezone.get_current_timezone())

        source_url = legacy_article_source_url(slug, wp_post.guid or "")
        legacy_url = source_url
        comments_count = max(int(wp_post.comment_count or 0), 0)

        raw_data = {
            "legacy_wp_id": wp_id,
            "legacy_slug": slug,
            "source": "wordpress",
        }
        if comun_manual_membership:
            raw_data = merge_pt_comun_manual_membership_raw(raw_data, comun_slug=comun_slug)

        if dry_run:
            self.stdout.write(
                f"[dry-run] wp:{wp_id} slug={slug!r} blocks={block_count} "
                f"author={author_map.author_id} membership={comun_manual_membership} "
                f"title={title[:60]!r}…"
            )
            return "skipped"

        author = author_map.author
        assert author is not None

        with transaction.atomic():
            if existing_map and existing_map.post_id and force:
                post = existing_map.post
                assert post is not None
                post.title = title
                post.content = content
                post.source_url = source_url
                post.publish_at = publish_at
                post.comments_count = comments_count
                post.raw_data = {**(post.raw_data or {}), **raw_data}
                post.is_pending = False
                post.is_blocked = False
                post.save()
                Post.objects.filter(pk=post.pk).update(created_at=publish_at or wp_post.post_date)
                existing_map.legacy_slug = slug
                existing_map.legacy_url = legacy_url
                existing_map.imported_at = timezone.now()
                existing_map.save()
                self.stdout.write(f"update wp:{wp_id} → post:{post.id} blocks={block_count}")
                return "updated"

            message_id = _generate_manual_message_id(author)
            post = Post.objects.create(
                author=author,
                message_id=message_id,
                title=title,
                content=content,
                source_url=source_url,
                publish_at=publish_at,
                comments_count=comments_count,
                raw_data=raw_data,
                is_pending=False,
                is_blocked=False,
            )
            if publish_at:
                Post.objects.filter(pk=post.pk).update(created_at=publish_at)

            LegacyWpPostMap.objects.update_or_create(
                wp_post_id=wp_id,
                defaults={
                    "legacy_slug": slug,
                    "legacy_url": legacy_url,
                    "post": post,
                    "imported_at": timezone.now(),
                },
            )
            self.stdout.write(f"create wp:{wp_id} → post:{post.id} blocks={block_count}")
            return "created"
