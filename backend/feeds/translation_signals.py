from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from feeds.models import Post, PostComment
from communities.models import Comun
from feeds.translation_service import (
    schedule_comment_auto_translation,
    schedule_comun_auto_translation,
    schedule_post_auto_translation,
)


POST_TRANSLATION_FIELDS = {
    "author",
    "title",
    "content",
    "is_pending",
    "is_blocked",
    "publish_at",
    "raw_data",
}
COMMENT_TRANSLATION_FIELDS = {"body", "is_deleted"}
COMUN_TRANSLATION_FIELDS = {"product_description", "rules_text", "rating_score", "is_active"}


def _has_relevant_update(update_fields, fields: set[str]) -> bool:
    if update_fields is None:
        return True
    return bool(set(update_fields) & fields)


@receiver(post_save, sender=Post)
def schedule_post_translation_after_save(sender, instance: Post, update_fields=None, **kwargs):
    if _has_relevant_update(update_fields, POST_TRANSLATION_FIELDS):
        schedule_post_auto_translation(instance)


@receiver(post_save, sender=PostComment)
def schedule_comment_translation_after_save(sender, instance: PostComment, update_fields=None, **kwargs):
    if _has_relevant_update(update_fields, COMMENT_TRANSLATION_FIELDS):
        schedule_comment_auto_translation(instance)


@receiver(post_save, sender=Comun)
def schedule_comun_translation_after_save(sender, instance: Comun, update_fields=None, **kwargs):
    if _has_relevant_update(update_fields, COMUN_TRANSLATION_FIELDS):
        schedule_comun_auto_translation(instance)
