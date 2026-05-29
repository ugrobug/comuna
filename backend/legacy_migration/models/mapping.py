"""Таблицы маппинга WP → Comuna (Postgres, managed=True)."""

from __future__ import annotations

from django.conf import settings
from django.db import models


class LegacyWpUserMap(models.Model):
    wp_user_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    wp_login = models.CharField(max_length=60, blank=True)
    wp_email = models.CharField(max_length=100, blank=True)
    wp_display_name = models.CharField(max_length=250, blank=True)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_wp_maps",
    )
    author = models.ForeignKey(
        "feeds.Author",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_wp_maps",
    )

    imported_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Маппинг WP user"
        verbose_name_plural = "Маппинги WP users"

    def __str__(self) -> str:
        return f"wp:{self.wp_user_id} → user:{self.user_id} author:{self.author_id}"


class LegacyWpPostMap(models.Model):
    wp_post_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    legacy_slug = models.CharField(max_length=200, blank=True, db_index=True)
    legacy_url = models.URLField(max_length=500, blank=True)

    post = models.ForeignKey(
        "feeds.Post",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_wp_maps",
    )

    imported_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Маппинг WP post"
        verbose_name_plural = "Маппинги WP posts"

    def __str__(self) -> str:
        return f"wp:{self.wp_post_id} → post:{self.post_id}"


class LegacyWpCommentMap(models.Model):
    wp_comment_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    wp_post_id = models.PositiveBigIntegerField(db_index=True)

    comment = models.ForeignKey(
        "feeds.PostComment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="legacy_wp_maps",
    )

    imported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Маппинг WP comment"
        verbose_name_plural = "Маппинги WP comments"

    def __str__(self) -> str:
        return f"wp:{self.wp_comment_id} → comment:{self.comment_id}"
