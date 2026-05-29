from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class AuthorRatingEvent(models.Model):
    EVENT_TYPE_POST_LIKE = "post_like"
    EVENT_TYPE_COMMENT_LIKE = "comment_like"
    EVENT_TYPE_CHOICES = (
        (EVENT_TYPE_POST_LIKE, "Лайк поста"),
        (EVENT_TYPE_COMMENT_LIKE, "Лайк комментария"),
    )

    author = models.ForeignKey(
        "feeds.Author",
        on_delete=models.CASCADE,
        related_name="rating_events",
    )
    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="author_rating_events",
    )
    post = models.ForeignKey(
        "feeds.Post",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="author_rating_events",
    )
    comment = models.ForeignKey(
        "feeds.PostComment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="author_rating_events",
    )
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES)
    delta = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "feeds"
        indexes = [
            models.Index(fields=["author", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
        verbose_name = "Изменение рейтинга автора"
        verbose_name_plural = "Изменения рейтинга авторов"

    def __str__(self) -> str:
        return f"{self.author_id}:{self.event_type}:{self.delta}"


class RatingSettings(models.Model):
    post_vote_weight = models.DecimalField(max_digits=8, decimal_places=3, default=1)
    post_comment_weight = models.DecimalField(max_digits=8, decimal_places=3, default=1)
    post_comment_like_weight = models.DecimalField(max_digits=8, decimal_places=3, default="0.5")
    post_community_rating_weight = models.DecimalField(max_digits=8, decimal_places=3, default=1)
    post_author_rating_weight = models.DecimalField(max_digits=8, decimal_places=3, default=1)
    community_post_rating_weight = models.DecimalField(max_digits=8, decimal_places=3, default="0.1")
    community_post_rating_days = models.PositiveSmallIntegerField(default=7)
    home_posts_per_community_per_day = models.PositiveSmallIntegerField(default=3)
    author_post_rating_weight = models.DecimalField(max_digits=8, decimal_places=3, default=1)
    author_comment_like_weight = models.DecimalField(max_digits=8, decimal_places=3, default="0.5")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройки рейтинга"
        verbose_name_plural = "Настройки рейтинга"

    def __str__(self) -> str:
        return "Настройки рейтинга"


__all__ = ["AuthorRatingEvent", "RatingSettings"]
