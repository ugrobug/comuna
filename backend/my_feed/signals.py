from __future__ import annotations

from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from communities.models import Comun, ComunPostCategoryAssignment
from feeds.models import Post
from my_feed import source_index


@receiver(post_save, sender=Post)
def _sync_post_feed_sources(
    sender,
    instance: Post,
    created: bool,
    update_fields=None,
    **kwargs,
) -> None:
    if not created and update_fields is not None:
        relevant_fields = {"author", "author_id", "created_at", "raw_data"}
        if not relevant_fields.intersection(set(update_fields)):
            return
    source_index.sync_feed_sources_for_post_id(instance.id)


@receiver(post_delete, sender=Post)
def _delete_post_feed_sources(sender, instance: Post, **kwargs) -> None:
    source_index.sync_feed_sources_for_post_id(instance.id)


@receiver(m2m_changed, sender=Post.tags.through)
def _sync_post_tag_feed_sources(
    sender,
    instance,
    action: str,
    reverse: bool,
    pk_set,
    **kwargs,
) -> None:
    if action not in {"post_add", "post_remove", "post_clear"}:
        return
    if reverse:
        if pk_set:
            source_index.sync_feed_sources_for_posts(pk_set)
        return
    source_index.sync_feed_sources_for_post_id(instance.id)


@receiver(post_save, sender=ComunPostCategoryAssignment)
def _sync_assignment_feed_sources(sender, instance: ComunPostCategoryAssignment, **kwargs) -> None:
    source_index.sync_feed_sources_for_post_id(instance.post_id)


@receiver(post_delete, sender=ComunPostCategoryAssignment)
def _sync_deleted_assignment_feed_sources(
    sender,
    instance: ComunPostCategoryAssignment,
    **kwargs,
) -> None:
    source_index.sync_feed_sources_for_post_id(instance.post_id)


@receiver(pre_save, sender=Comun)
def _capture_comun_feed_source_fields(sender, instance: Comun, **kwargs) -> None:
    if not instance.pk:
        instance._feed_source_previous_slug = None
        instance._feed_source_previous_author_id = None
        return
    previous = Comun.objects.filter(pk=instance.pk).values(
        "slug",
        "telegram_source_author_id",
    ).first()
    instance._feed_source_previous_slug = previous["slug"] if previous else None
    instance._feed_source_previous_author_id = (
        previous["telegram_source_author_id"] if previous else None
    )


@receiver(post_save, sender=Comun)
def _sync_comun_feed_sources(
    sender,
    instance: Comun,
    created: bool,
    update_fields=None,
    **kwargs,
) -> None:
    if not created and update_fields is not None:
        relevant_fields = {"slug", "telegram_source_author", "telegram_source_author_id"}
        if not relevant_fields.intersection(set(update_fields)):
            return

    previous_slug = getattr(instance, "_feed_source_previous_slug", None)
    previous_author_id = getattr(instance, "_feed_source_previous_author_id", None)
    if previous_slug and previous_slug != instance.slug:
        source_index.sync_feed_sources_for_manual_comun_slug(previous_slug)
    source_index.sync_feed_sources_for_manual_comun_slug(instance.slug)

    if previous_author_id and previous_author_id != instance.telegram_source_author_id:
        source_index.sync_feed_sources_for_author_posts(previous_author_id)
    source_index.sync_feed_sources_for_author_posts(instance.telegram_source_author_id)
