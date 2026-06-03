from __future__ import annotations

from django.db import models

from django.contrib.auth import get_user_model

User = get_user_model()


def default_feed_tag_rules() -> dict:
    return {
        "cw": "blur",
        "nsfl": "blur",
        "nsfw": "blur",
    }


class UserFeedSettings(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="feed_settings",
    )
    home_feed = models.CharField(max_length=20, default="hot")
    hide_read_posts = models.BooleanField(default=False)
    my_feed_authors = models.JSONField(default=list, blank=True)
    my_feed_tags = models.JSONField(default=list, blank=True)
    my_feed_comuns = models.JSONField(default=list, blank=True)
    my_feed_comun_categories = models.JSONField(default=dict, blank=True)
    hidden_authors = models.JSONField(default=list, blank=True)
    my_feed_hide_negative = models.BooleanField(default=True)
    tag_rules = models.JSONField(default=default_feed_tag_rules, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        verbose_name = "Настройки ленты пользователя"
        verbose_name_plural = "Настройки лент пользователей"

    def __str__(self) -> str:
        return f"Feed settings for {self.user}"


class FeedSourcePost(models.Model):
    SOURCE_AUTHOR = "author"
    SOURCE_COMUN = "comun"
    SOURCE_COMUN_CATEGORY = "comun_category"
    SOURCE_TAG = "tag"
    SOURCE_CHOICES = (
        (SOURCE_AUTHOR, "Автор"),
        (SOURCE_COMUN, "Комуна"),
        (SOURCE_COMUN_CATEGORY, "Категория комуны"),
        (SOURCE_TAG, "Тег"),
    )

    source_type = models.CharField(max_length=32, choices=SOURCE_CHOICES)
    source_id = models.BigIntegerField()
    post = models.ForeignKey(
        "feeds.Post",
        on_delete=models.CASCADE,
        related_name="feed_source_links",
    )
    post_created_at = models.DateTimeField()

    class Meta:
        app_label = "feeds"
        constraints = [
            models.UniqueConstraint(
                fields=["source_type", "source_id", "post"],
                name="feeds_feedsourcepost_unique",
            )
        ]
        indexes = [
            models.Index(
                fields=["source_type", "source_id", "-post_created_at", "post"],
                name="feedsrc_source_created_idx",
            ),
            models.Index(fields=["post", "source_type"], name="feedsrc_post_type_idx"),
        ]
        verbose_name = "Пост в источнике ленты"
        verbose_name_plural = "Посты в источниках ленты"

    def __str__(self) -> str:
        return f"{self.source_type}:{self.source_id}:{self.post_id}"


__all__ = ["UserFeedSettings", "FeedSourcePost", "default_feed_tag_rules"]
