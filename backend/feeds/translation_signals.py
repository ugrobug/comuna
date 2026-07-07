from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from feeds.models import Post, PostComment, StaticPageContent
from communities.models import Comun, ComunCategory, ComunGlossaryTerm
from feeds.translation_service import (
    schedule_comment_auto_translation,
    schedule_comun_auto_translation,
    schedule_post_auto_translation,
    schedule_static_page_auto_translation,
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
COMUN_TRANSLATION_FIELDS = {
    "name",
    "product_description",
    "rules_text",
    "target_audience",
    "rating_score",
    "is_active",
    "glossary_enabled",
}
COMUN_CATEGORY_TRANSLATION_FIELDS = {"name", "description", "is_active"}
COMUN_GLOSSARY_TRANSLATION_FIELDS = {"term", "term_en", "definition", "is_active"}
STATIC_PAGE_TRANSLATION_FIELDS = {"title", "content"}


def _has_relevant_update(update_fields, fields: set[str]) -> bool:
    if update_fields is None:
        return True
    return bool(set(update_fields) & fields)


def _schedule_parent_comun_translation(instance) -> None:
    comun_id = getattr(instance, "comun_id", None)
    if not comun_id:
        return
    try:
        comun = getattr(instance, "comun", None)
    except Comun.DoesNotExist:
        comun = None
    if comun is None or getattr(comun, "pk", None) != comun_id:
        comun = Comun.objects.filter(pk=comun_id).first()
    if comun:
        schedule_comun_auto_translation(comun)


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


@receiver(post_save, sender=ComunCategory)
def schedule_comun_translation_after_category_save(sender, instance: ComunCategory, update_fields=None, **kwargs):
    if _has_relevant_update(update_fields, COMUN_CATEGORY_TRANSLATION_FIELDS):
        _schedule_parent_comun_translation(instance)


@receiver(post_save, sender=ComunGlossaryTerm)
def schedule_comun_translation_after_glossary_save(sender, instance: ComunGlossaryTerm, update_fields=None, **kwargs):
    if _has_relevant_update(update_fields, COMUN_GLOSSARY_TRANSLATION_FIELDS):
        _schedule_parent_comun_translation(instance)


@receiver(post_save, sender=StaticPageContent)
def schedule_static_page_translation_after_save(sender, instance: StaticPageContent, update_fields=None, **kwargs):
    if _has_relevant_update(update_fields, STATIC_PAGE_TRANSLATION_FIELDS):
        schedule_static_page_auto_translation(instance)


@receiver(post_delete, sender=ComunCategory)
def schedule_comun_translation_after_category_delete(sender, instance: ComunCategory, **kwargs):
    _schedule_parent_comun_translation(instance)


@receiver(post_delete, sender=ComunGlossaryTerm)
def schedule_comun_translation_after_glossary_delete(sender, instance: ComunGlossaryTerm, **kwargs):
    _schedule_parent_comun_translation(instance)
