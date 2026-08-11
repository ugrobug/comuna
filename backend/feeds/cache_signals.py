from django.db.models.signals import post_save
from django.dispatch import receiver

from rabotaem_backend.cache import bump_public_cache_prefix

from .models import Post


_POST_DETAIL_FIELDS = {
    "author",
    "title",
    "content",
    "original_language",
    "channel_url",
    "source_url",
    "is_pending",
    "is_blocked",
    "publish_at",
    "raw_data",
    "accepted_answer",
    "question_solved_at",
}


@receiver(post_save, sender=Post, dispatch_uid="feeds.invalidate_post_detail_cache")
def invalidate_post_detail_cache(sender, instance, created, update_fields, **kwargs):
    if created or update_fields is None or _POST_DETAIL_FIELDS.intersection(update_fields):
        bump_public_cache_prefix("post-detail")
