from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

PUSH_PLATFORM_CHOICES = (
    ("ios", "iOS"),
    ("android", "Android"),
)

NOTIFICATION_GROUPING_PERIOD_CHOICES = (
    ("none", "Не группировать"),
    ("day", "За день"),
    ("week", "За неделю"),
)


class SiteNotificationPreference(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    event_key = models.CharField(max_length=80)
    site_enabled = models.BooleanField(default=True)
    telegram_enabled = models.BooleanField(default=False)
    push_enabled = models.BooleanField(default=True)
    grouping_period = models.CharField(
        max_length=20,
        choices=NOTIFICATION_GROUPING_PERIOD_CHOICES,
        default="none",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        verbose_name = "Настройка уведомления"
        verbose_name_plural = "Настройки уведомлений"
        unique_together = ("user", "event_key")
        indexes = [
            models.Index(fields=("user", "event_key")),
        ]

    def __str__(self) -> str:
        return f"notification-pref:{self.user_id}:{self.event_key}"


class SiteNotification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="site_notifications")
    event_key = models.CharField(max_length=80)
    title = models.CharField(max_length=255)
    message = models.TextField(blank=True)
    link_url = models.CharField(max_length=500, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    group_key = models.CharField(max_length=160, blank=True)
    group_count = models.PositiveIntegerField(default=1)
    is_site = models.BooleanField(default=True)
    is_telegram = models.BooleanField(default=False)
    is_push = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    delivery_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    telegram_sent_at = models.DateTimeField(null=True, blank=True)
    telegram_error = models.TextField(blank=True)
    push_sent_at = models.DateTimeField(null=True, blank=True)
    push_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("user", "created_at")),
            models.Index(fields=("user", "read_at")),
            models.Index(fields=("user", "is_site")),
            models.Index(fields=("user", "is_push")),
            models.Index(fields=("user", "event_key", "group_key")),
            models.Index(fields=("delivered_at", "delivery_at")),
        ]

    def __str__(self) -> str:
        return f"notification:{self.user_id}:{self.event_key}:{self.id}"


class MobilePushDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mobile_push_devices")
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=20, choices=PUSH_PLATFORM_CHOICES)
    device_id = models.CharField(max_length=191, blank=True)
    device_name = models.CharField(max_length=120, blank=True)
    app_version = models.CharField(max_length=40, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    last_push_sent_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        verbose_name = "Push-устройство"
        verbose_name_plural = "Push-устройства"
        ordering = ("platform", "-last_seen_at", "-id")
        indexes = [
            models.Index(fields=("user", "is_active")),
            models.Index(fields=("user", "platform", "is_active")),
            models.Index(fields=("user", "device_id")),
        ]

    def __str__(self) -> str:
        return f"push-device:{self.user_id}:{self.platform}:{self.id}"


__all__ = [
    "MobilePushDevice",
    "NOTIFICATION_GROUPING_PERIOD_CHOICES",
    "PUSH_PLATFORM_CHOICES",
    "SiteNotification",
    "SiteNotificationPreference",
]
