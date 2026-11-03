from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()


class TelegramAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="telegram_account")
    telegram_id = models.BigIntegerField(unique=True)
    oidc_sub = models.CharField(max_length=64, unique=True, null=True, blank=True)
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
    verified_user_id = models.IntegerField(null=True, blank=True)
    channel_flow = models.CharField(max_length=32, blank=True)
    selected_author = models.ForeignKey(
        "feeds.Author", on_delete=models.SET_NULL, null=True, blank=True, related_name="bot_sessions"
    )
    invite_url = models.URLField(max_length=255, blank=True)
    invite_waiting = models.BooleanField(default=False)
    mode_selected = models.BooleanField(default=False)
    instructions_sent = models.BooleanField(default=False)
    pending_update_post_id = models.IntegerField(null=True, blank=True)
    pending_update_message = models.JSONField(null=True, blank=True)
    selected_comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telegram_bot_sessions",
    )
    pending_forward_comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telegram_forward_sessions",
    )
    pending_forward_messages = models.JSONField(default=list, blank=True)
    pending_forward_action_message_id = models.BigIntegerField(null=True, blank=True)
    pending_forward_started_at = models.DateTimeField(null=True, blank=True)
    pending_forward_processing = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"

    def __str__(self) -> str:
        return str(self.telegram_user_id)


class TelegramApprovalDelivery(models.Model):
    post = models.OneToOneField('feeds.Post', on_delete=models.CASCADE, related_name='telegram_approval_delivery')
    chat_id = models.BigIntegerField()
    message_id = models.BigIntegerField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_token = models.CharField(max_length=32, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'feeds'
        indexes = [models.Index(fields=['next_attempt_at', 'id'],
            condition=models.Q(sent_at__isnull=True, failed_at__isnull=True), name='tg_approval_due_idx')]


class TelegramMediaJob(models.Model):
    """Durable receipt of one photo message, independent of the polling cursor."""
    author = models.ForeignKey('feeds.Author', on_delete=models.CASCADE)
    message_id = models.BigIntegerField()
    media_group_id = models.CharField(max_length=255, blank=True)
    post = models.ForeignKey('feeds.Post', null=True, blank=True, on_delete=models.CASCADE,
                             related_name='telegram_media_jobs')
    payload = models.JSONField(default=dict)
    revision = models.CharField(max_length=64)
    state = models.CharField(max_length=16, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_token = models.CharField(max_length=32, blank=True)
    last_error = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'feeds'
        constraints = [models.UniqueConstraint(fields=['author', 'message_id'], name='tg_media_message_unique')]
        indexes = [
            models.Index(fields=['next_attempt_at', 'id'], condition=models.Q(state='pending'), name='tg_media_due_idx'),
            models.Index(fields=['author', 'media_group_id'], name='tg_media_album_idx'),
            models.Index(fields=['author'], condition=models.Q(state='pending'), name='tg_media_author_pending_idx'),
            models.Index(fields=['created_at'], condition=models.Q(state='pending'), name='tg_media_age_idx'),
            models.Index(fields=['id'], condition=models.Q(state='failed'), name='tg_media_failed_idx'),
        ]


__all__ = ["BotSession", "TelegramAccount", "TelegramApprovalDelivery", "TelegramMediaJob"]
