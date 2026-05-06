from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class ThematicFeed(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    moderators = models.ManyToManyField(
        User,
        blank=True,
        related_name="thematic_feed_moderation",
        help_text="Пользователи, которые могут редактировать состав папки.",
    )
    authors = models.ManyToManyField(
        "feeds.Author",
        blank=True,
        related_name="thematic_feeds",
        help_text="Авторы, посты которых будут показаны в тематической ленте.",
    )
    excluded_authors = models.ManyToManyField(
        "feeds.Author",
        blank=True,
        related_name="thematic_feeds_excluded",
        help_text="Авторы, посты которых будут исключены из папки.",
    )
    rubrics = models.ManyToManyField(
        "feeds.Rubric",
        blank=True,
        related_name="thematic_feeds_included",
        verbose_name="Рубрики",
        help_text="Посты этих рубрик будут добавляться в папку.",
    )
    tags = models.ManyToManyField(
        "feeds.Tag",
        blank=True,
        related_name="thematic_feeds_included",
        verbose_name="Теги",
        help_text="Посты с этими тегами будут добавляться в папку.",
    )
    blocked_tags = models.ManyToManyField(
        "feeds.Tag",
        blank=True,
        related_name="thematic_feeds_blocked",
        verbose_name="Исключенные теги",
        help_text="Посты с этими тегами будут скрыты в папке.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["sort_order", "name"]
        verbose_name = "Папка"
        verbose_name_plural = "Папки"

    def __str__(self) -> str:
        return self.name


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
    my_feed_rubrics = models.JSONField(default=list, blank=True)
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


__all__ = ["ThematicFeed", "UserFeedSettings", "default_feed_tag_rules"]
