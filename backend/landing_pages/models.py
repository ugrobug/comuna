from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.text import get_valid_filename

User = get_user_model()


def landing_page_image_path(instance, filename: str) -> str:
    page_slug = get_valid_filename(getattr(instance.page, "slug", "") or "landing")
    base_name = get_valid_filename(os.path.splitext(filename or "image")[0] or "image")
    ext = os.path.splitext(filename or "")[1].lower() or ".jpg"
    return f"landing-pages/{page_slug}/{timezone.now():%Y%m%d%H%M%S}-{base_name}{ext}"


class LandingPage(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)
    template_slug = models.SlugField(max_length=80, default="community-platform")
    is_published = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_landing_pages",
    )
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_landing_pages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Посадочная страница"
        verbose_name_plural = "Посадочные страницы"
        ordering = ("sort_order", "title", "id")
        indexes = [
            models.Index(fields=("is_published", "sort_order")),
            models.Index(fields=("template_slug", "is_published")),
        ]

    def __str__(self) -> str:
        return f"{self.title} (/l/{self.slug})"


class LandingPageImage(models.Model):
    page = models.ForeignKey(
        LandingPage,
        on_delete=models.CASCADE,
        related_name="images",
    )
    slot = models.SlugField(max_length=80, default="hero")
    title = models.CharField(max_length=160)
    alt_text = models.CharField(max_length=220, blank=True)
    image = models.ImageField(upload_to=landing_page_image_path, blank=True)
    image_url = models.URLField(max_length=700, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_landing_page_images",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Картинка посадочной страницы"
        verbose_name_plural = "Картинки посадочных страниц"
        ordering = ("page", "sort_order", "id")
        indexes = [
            models.Index(fields=("page", "slot", "is_active")),
            models.Index(fields=("page", "is_active", "sort_order")),
        ]

    def __str__(self) -> str:
        return f"{self.page.slug}:{self.slot}:{self.title}"

    @property
    def effective_image_url(self) -> str:
        if self.image:
            try:
                return self.image.url
            except ValueError:
                return ""
        return self.image_url


class LandingPageLead(models.Model):
    page = models.ForeignKey(
        LandingPage,
        on_delete=models.CASCADE,
        related_name="leads",
    )
    source = models.CharField(max_length=80, blank=True)
    contact = models.CharField(max_length=180)
    community_url = models.URLField(max_length=700, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Заявка с посадочной страницы"
        verbose_name_plural = "Заявки с посадочных страниц"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("page", "created_at")),
            models.Index(fields=("source", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.page.slug}:{self.contact}:{self.created_at:%Y-%m-%d %H:%M}"
