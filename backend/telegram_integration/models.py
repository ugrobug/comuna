from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class TelegramAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="telegram_account")
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"

    def __str__(self) -> str:
        return f"telegram:{self.telegram_id}"


class BotSession(models.Model):
    telegram_user_id = models.BigIntegerField(unique=True)
    auto_publish = models.BooleanField(default=True)
    publish_delay_days = models.PositiveSmallIntegerField(default=0)
    selected_author = models.ForeignKey(
        "feeds.Author", on_delete=models.SET_NULL, null=True, blank=True, related_name="bot_sessions"
    )
    invite_url = models.URLField(max_length=255, blank=True)
    invite_waiting = models.BooleanField(default=False)
    mode_selected = models.BooleanField(default=False)
    instructions_sent = models.BooleanField(default=False)
    pending_update_post_id = models.IntegerField(null=True, blank=True)
    pending_update_message = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"

    def __str__(self) -> str:
        return str(self.telegram_user_id)


__all__ = ["BotSession", "TelegramAccount"]
