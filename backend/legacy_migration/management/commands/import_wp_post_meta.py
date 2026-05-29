from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from legacy_migration.management.commands.import_wp_posts import _parse_wp_ids
from legacy_migration.wp_post_meta import import_post_meta


class Command(BaseCommand):
    help = (
        "Этап 3 (пилот): комментарии wp_comments, лайки wp_ulike / wp_ulike_comments, "
        "просмотры wp_post_views → Post / PostComment / PostLike"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--wp-ids",
            type=str,
            required=True,
            help="WP post ID через запятую",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Только сводка из MySQL, без записи",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Пересоздать комментарии и лайки поста",
        )

    def handle(self, *args, **options):
        wp_ids = _parse_wp_ids(options["wp_ids"])
        dry_run: bool = options["dry_run"]
        force: bool = options["force"]

        from legacy_migration.models import LegacyWpPostMap, WpComments, WpUlike, WpUlikeComments
        from legacy_migration.wp_post_meta import wp_post_total_views

        for wp_id in wp_ids:
            if not LegacyWpPostMap.objects.filter(wp_post_id=wp_id, post__isnull=False).exists():
                raise CommandError(f"wp:{wp_id} — сначала import_wp_posts")

            comments_n = (
                WpComments.objects.filter(
                    comment_post_id=wp_id,
                    comment_approved="1",
                )
                .exclude(comment_type__in=("pingback", "trackback", "spam"))
                .count()
            )
            post_likes = WpUlike.objects.filter(post_id=wp_id, status="like").count()
            comment_ids = list(
                WpComments.objects.filter(comment_post_id=wp_id).values_list(
                    "comment_id", flat=True
                )
            )
            comment_likes = WpUlikeComments.objects.filter(
                comment_id__in=comment_ids,
                status="like",
            ).count()
            views = wp_post_total_views(wp_id)

            self.stdout.write(
                f"wp:{wp_id} — в WP: comments={comments_n}, post_likes={post_likes}, "
                f"comment_likes={comment_likes}, views={views}"
            )

            if dry_run:
                continue

            with transaction.atomic():
                stats = import_post_meta(wp_post_id=wp_id, force=force)

            self.stdout.write(
                self.style.SUCCESS(
                    f"  → comments +{stats.comments_created} skip={stats.comments_skipped}, "
                    f"post_likes +{stats.post_likes_created}, "
                    f"comment_likes +{stats.comment_likes_created}"
                )
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("dry-run: в Postgres ничего не записано"))
