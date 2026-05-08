from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class SpecialProjectLetterImage(models.Model):
    project_slug = models.SlugField(max_length=80, default="landname")
    letter = models.CharField(max_length=4)
    title = models.CharField(max_length=160)
    location_name = models.CharField(max_length=220, blank=True)
    image_url = models.URLField(max_length=700, blank=True)
    map_url = models.URLField(max_length=700, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    source_name = models.CharField(max_length=160, blank=True)
    source_url = models.URLField(max_length=700, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="special_project_letter_images",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Буква спецпроекта"
        verbose_name_plural = "Буквы спецпроекта"
        ordering = ("project_slug", "letter", "sort_order", "id")
        indexes = [
            models.Index(fields=("project_slug", "letter", "is_active")),
            models.Index(fields=("project_slug", "is_active", "sort_order")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.letter}:{self.title}"


class SpecialProjectLetterSuggestion(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "На модерации"),
        (STATUS_APPROVED, "Одобрено"),
        (STATUS_REJECTED, "Отклонено"),
    )

    project_slug = models.SlugField(max_length=80, default="landname")
    letter = models.CharField(max_length=4)
    map_url = models.URLField(max_length=700, blank=True)
    coordinates_text = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_note = models.CharField(max_length=280, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="special_project_letter_suggestions",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_special_project_letter_suggestions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Предложение буквы спецпроекта"
        verbose_name_plural = "Предложения букв спецпроекта"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("project_slug", "letter", "status")),
            models.Index(fields=("submitted_by", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.letter}:{self.status}:{self.submitted_by_id}"


class SpecialProjectGeneratedPhrase(models.Model):
    project_slug = models.SlugField(max_length=80, default="landname")
    text = models.CharField(max_length=64)
    share_query = models.CharField(max_length=64)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="special_project_generated_phrases",
    )
    was_shared = models.BooleanField(default=False)
    share_clicks = models.PositiveIntegerField(default=0)
    shared_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Сгенерированная фраза спецпроекта"
        verbose_name_plural = "Сгенерированные фразы спецпроекта"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("project_slug", "created_at")),
            models.Index(fields=("project_slug", "was_shared", "created_at")),
            models.Index(fields=("project_slug", "text")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.text}:{self.created_at:%Y-%m-%d %H:%M}"
