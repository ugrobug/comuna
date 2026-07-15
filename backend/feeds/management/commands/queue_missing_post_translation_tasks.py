from __future__ import annotations

from datetime import datetime, timezone as datetime_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from communities.models import Comun

from feeds.models import (
    CONTENT_TRANSLATION_KIND_POST,
    CONTENT_TRANSLATION_TASK_STATUS_PENDING,
    CONTENT_TRANSLATION_TASK_STATUS_RUNNING,
    CONTENT_TRANSLATION_TASK_STATUS_DONE,
    CONTENT_TRANSLATION_TASK_STATUS_FAILED,
    CONTENT_TRANSLATION_TASK_STATUS_SKIPPED,
    ContentTranslationTask,
    Post,
)
from feeds.translation_service import (
    CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS,
    SUPPORTED_TRANSLATION_LANGUAGES,
    _decode_post_editor_payload,
    _scheduled_at_for,
    post_translation_record_is_current,
)


WHEREFILMED_PRIORITY_AT = datetime(2000, 1, 1, tzinfo=datetime_timezone.utc)
WHEREFILMED_PRIORITY_LANGUAGES = {"tr", "id"}


class Command(BaseCommand):
    help = "Queue automatic translation tasks for translatable posts with missing translations."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--reset-exhausted", action="store_true")

    def handle(self, *args, **options):
        dry_run = bool(options["dry_run"])
        limit = max(int(options["limit"] or 0), 0)
        reset_exhausted = bool(options["reset_exhausted"])
        now = timezone.now()
        negative_comuns = Comun.objects.filter(is_active=True, rating_score__lt=0).exclude(
            slug__iexact="faq"
        )
        negative_comun_slugs = set(negative_comuns.values_list("slug", flat=True))
        negative_source_author_ids = set(
            negative_comuns.exclude(telegram_source_author_id__isnull=True).values_list(
                "telegram_source_author_id",
                flat=True,
            )
        )
        stats = {
            "scanned": 0,
            "eligible": 0,
            "missing_translations": 0,
            "created": 0,
            "reset": 0,
            "already_queued": 0,
            "retry_exhausted": 0,
            "retry_exhausted_reset": 0,
            "prioritized_wherefilmed": 0,
            "wherefilmed_missing_tr_id": 0,
            "skipped_not_translatable": 0,
        }

        queryset = (
            Post.objects.select_related("author")
            .prefetch_related("translations")
            .filter(
                is_blocked=False,
                is_pending=False,
                author__is_blocked=False,
            )
            .order_by("id")
        )
        if limit:
            queryset = queryset[:limit]

        for post in queryset.iterator(chunk_size=500):
            stats["scanned"] += 1
            if not _post_is_translatable_for_backfill(
                post,
                now=now,
                negative_comun_slugs=negative_comun_slugs,
                negative_source_author_ids=negative_source_author_ids,
            ):
                stats["skipped_not_translatable"] += 1
                continue

            stats["eligible"] += 1
            missing_languages = _missing_post_translation_languages(post)
            if not missing_languages:
                continue

            stats["missing_translations"] += 1
            is_wherefilmed = _is_wherefilmed_post(post)
            is_wherefilmed_priority = is_wherefilmed and bool(
                WHEREFILMED_PRIORITY_LANGUAGES.intersection(missing_languages)
            )
            if is_wherefilmed_priority:
                stats["wherefilmed_missing_tr_id"] += 1

            scheduled_at = _scheduled_at_for(post, CONTENT_TRANSLATION_KIND_POST)
            if is_wherefilmed_priority and scheduled_at <= now:
                scheduled_at = WHEREFILMED_PRIORITY_AT

            task = ContentTranslationTask.objects.filter(
                kind=CONTENT_TRANSLATION_KIND_POST,
                object_id=post.pk,
            ).first()

            retry_exhausted = bool(
                task
                and task.status in {
                    CONTENT_TRANSLATION_TASK_STATUS_FAILED,
                    CONTENT_TRANSLATION_TASK_STATUS_PENDING,
                }
                and task.attempts >= CONTENT_TRANSLATION_TASK_MAX_ATTEMPTS
                and task.source_updated_at
                and post.updated_at
                and task.source_updated_at >= post.updated_at
            )
            if retry_exhausted and not reset_exhausted:
                stats["retry_exhausted"] += 1
                continue
            if retry_exhausted:
                stats["retry_exhausted_reset"] += 1

            if task and task.status in {
                CONTENT_TRANSLATION_TASK_STATUS_PENDING,
                CONTENT_TRANSLATION_TASK_STATUS_RUNNING,
            } and not retry_exhausted:
                if (
                    is_wherefilmed_priority
                    and task.status == CONTENT_TRANSLATION_TASK_STATUS_PENDING
                    and task.scheduled_at != scheduled_at
                ):
                    stats["prioritized_wherefilmed"] += 1
                    if not dry_run:
                        task.scheduled_at = scheduled_at
                        task.source_updated_at = post.updated_at
                        task.last_error = ""
                        task.save(
                            update_fields=[
                                "scheduled_at",
                                "source_updated_at",
                                "last_error",
                                "updated_at",
                            ]
                        )
                stats["already_queued"] += 1
                continue

            if task and task.status == CONTENT_TRANSLATION_TASK_STATUS_DONE:
                stats["reset"] += 1
            elif task:
                stats["reset"] += 1
            else:
                stats["created"] += 1

            if dry_run:
                continue

            if task is None:
                ContentTranslationTask.objects.create(
                    kind=CONTENT_TRANSLATION_KIND_POST,
                    object_id=post.pk,
                    status=CONTENT_TRANSLATION_TASK_STATUS_PENDING,
                    scheduled_at=scheduled_at,
                    source_updated_at=post.updated_at,
                    last_error="",
                    locked_at=None,
                )
                continue

            reset_attempts = retry_exhausted or task.status in {
                CONTENT_TRANSLATION_TASK_STATUS_DONE,
                CONTENT_TRANSLATION_TASK_STATUS_SKIPPED,
            }
            task.status = CONTENT_TRANSLATION_TASK_STATUS_PENDING
            task.scheduled_at = scheduled_at
            task.source_updated_at = post.updated_at
            task.last_error = ""
            task.locked_at = None
            update_fields = [
                "status",
                "scheduled_at",
                "source_updated_at",
                "last_error",
                "locked_at",
                "updated_at",
            ]
            if reset_attempts:
                task.attempts = 0
                update_fields.append("attempts")
            task.save(
                update_fields=update_fields
            )

        prefix = "DRY_RUN " if dry_run else ""
        self.stdout.write(
            prefix
            + " ".join(f"{key}={value}" for key, value in stats.items())
        )


def _missing_post_translation_languages(post: Post) -> set[str]:
    translations = {
        translation.language: translation
        for translation in post.translations.all()
    }
    source_content_info = _decode_post_editor_payload(post.content or "")
    missing: set[str] = set()
    for language in SUPPORTED_TRANSLATION_LANGUAGES:
        translation = translations.get(language)
        if not _post_translation_is_current(post, translation, source_content_info):
            missing.add(language)
    return missing


def _post_is_translatable_for_backfill(
    post: Post,
    *,
    now,
    negative_comun_slugs: set[str],
    negative_source_author_ids: set[int],
) -> bool:
    if not post.pk or post.is_blocked or post.is_pending:
        return False
    if post.publish_at and post.publish_at > now:
        return True
    if not (post.title or "").strip() and not (post.content or "").strip():
        return False
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    comun_slug = str(raw_data.get("comun_slug") or "").strip()
    if comun_slug and comun_slug in negative_comun_slugs:
        return False
    return post.author_id not in negative_source_author_ids


def _post_translation_is_current(post: Post, translation, source_content_info=None) -> bool:
    return post_translation_record_is_current(post, translation, source_content_info)


def _is_wherefilmed_post(post: Post) -> bool:
    author = getattr(post, "author", None)
    if author and author.username == "wherefilmed":
        return True
    raw_data = post.raw_data if isinstance(post.raw_data, dict) else {}
    wherefilmed = raw_data.get("wherefilmed")
    return isinstance(wherefilmed, dict) and wherefilmed.get("source_site") == "wherefilmed"
