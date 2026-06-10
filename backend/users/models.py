from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class AuthorAdmin(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="author_links")
    author = models.ForeignKey("feeds.Author", on_delete=models.CASCADE, related_name="admin_links")
    telegram_user_id = models.BigIntegerField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "feeds"
        unique_together = ("user", "author")

    def __str__(self) -> str:
        return f"{self.user_id}:{self.author_id}"


class AuthorVerificationCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="author_codes")
    code = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "feeds"

    def __str__(self) -> str:
        return f"{self.user_id}:{self.code}"


from telegram_integration.models import TelegramAccount


class VkAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vk_account")
    vk_id = models.BigIntegerField(unique=True)
    username = models.CharField(blank=True, max_length=255)
    email = models.EmailField(blank=True, max_length=254)
    phone = models.CharField(blank=True, max_length=32)
    first_name = models.CharField(blank=True, max_length=255)
    last_name = models.CharField(blank=True, max_length=255)
    avatar_url = models.URLField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        indexes = [
            models.Index(fields=("email",), name="feeds_vkacc_email_255939_idx"),
            models.Index(fields=("phone",), name="feeds_vkacc_phone_c5f49a_idx"),
        ]

    def __str__(self) -> str:
        return f"vk:{self.vk_id}"


class SiteUserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="site_profile")
    display_name = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    registration_source = models.CharField(max_length=80, blank=True)
    registration_path = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        verbose_name = "Профиль пользователя сайта"
        verbose_name_plural = "Профили пользователей сайта"
        indexes = [
            models.Index(fields=("phone",), name="feeds_siteu_phone_43c849_idx"),
            models.Index(fields=("registration_source",), name="feeds_siteu_regsrc_8f2c4d_idx"),
            models.Index(fields=("deleted_at",), name="feeds_siteu_deleted_idx"),
        ]

    def __str__(self) -> str:
        return f"site-profile:{self.user_id}"


class SiteAuthToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="site_auth_tokens")
    token_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        app_label = "feeds"
        indexes = [
            models.Index(fields=("user", "expires_at"), name="feeds_sitea_user_id_5f8a21_idx"),
            models.Index(fields=("revoked_at", "expires_at"), name="feeds_sitea_revoked_8b2e0c_idx"),
        ]

    def __str__(self) -> str:
        return f"site-auth-token:{self.user_id}:{self.id}"


class SiteChat(models.Model):
    user_one = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="site_chats_as_user_one",
    )
    user_two = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="site_chats_as_user_two",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(null=True, blank=True)
    last_message = models.ForeignKey(
        "SiteChatMessage",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        app_label = "feeds"
        verbose_name = "Чат пользователей"
        verbose_name_plural = "Чаты пользователей"
        unique_together = ("user_one", "user_two")
        indexes = [
            models.Index(fields=("user_one", "last_message_at"), name="feeds_sitec_userone_c5c20d_idx"),
            models.Index(fields=("user_two", "last_message_at"), name="feeds_sitec_usertwo_2c8d87_idx"),
            models.Index(fields=("last_message_at",), name="feeds_sitec_lastmsg_963d17_idx"),
        ]

    def __str__(self) -> str:
        return f"site-chat:{self.user_one_id}:{self.user_two_id}"


class SiteChatMessage(models.Model):
    chat = models.ForeignKey(SiteChat, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_site_chat_messages")
    body = models.TextField()
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        verbose_name = "Сообщение чата"
        verbose_name_plural = "Сообщения чатов"
        ordering = ("created_at", "id")
        indexes = [
            models.Index(fields=("chat", "created_at"), name="feeds_sitec_chat_cr_358d84_idx"),
            models.Index(fields=("chat", "sender", "read_at"), name="feeds_sitec_chat_se_241934_idx"),
            models.Index(fields=("sender", "created_at"), name="feeds_sitec_sender__2862b3_idx"),
        ]

    def __str__(self) -> str:
        return f"site-chat-message:{self.chat_id}:{self.id}"


class SiteChatParticipantState(models.Model):
    chat = models.ForeignKey(SiteChat, on_delete=models.CASCADE, related_name="participant_states")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="site_chat_participant_states")
    is_blocked = models.BooleanField(default=False)
    hidden_at = models.DateTimeField(null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        verbose_name = "Состояние участника чата"
        verbose_name_plural = "Состояния участников чатов"
        unique_together = ("chat", "user")
        indexes = [
            models.Index(fields=("user", "hidden_at"), name="feeds_schatst_user_hid_idx"),
            models.Index(fields=("chat", "user"), name="feeds_schatst_chat_usr_idx"),
            models.Index(fields=("is_blocked", "updated_at"), name="feeds_schatst_block_idx"),
        ]

    def __str__(self) -> str:
        return f"site-chat-state:{self.chat_id}:{self.user_id}"


class SiteChatReport(models.Model):
    STATUS_OPEN = "open"
    STATUS_REVIEWED = "reviewed"
    STATUS_DISMISSED = "dismissed"
    STATUS_CHOICES = (
        (STATUS_OPEN, "Новая"),
        (STATUS_REVIEWED, "Обработана"),
        (STATUS_DISMISSED, "Отклонена"),
    )

    chat = models.ForeignKey(SiteChat, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="site_chat_reports_made")
    reported_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="site_chat_reports_received",
    )
    message = models.ForeignKey(
        SiteChatMessage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reports",
    )
    message_body_snapshot = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_site_chat_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        verbose_name = "Жалоба на сообщение чата"
        verbose_name_plural = "Жалобы на сообщения чатов"
        indexes = [
            models.Index(fields=("status", "created_at"), name="feeds_schatrep_status_idx"),
            models.Index(fields=("reporter", "created_at"), name="feeds_schatrep_reporter_idx"),
            models.Index(fields=("reported_user", "created_at"), name="feeds_schatrep_target_idx"),
        ]

    def __str__(self) -> str:
        return f"site-chat-report:{self.chat_id}:{self.id}"


__all__ = [
    "AuthorAdmin",
    "AuthorVerificationCode",
    "SiteAuthToken",
    "SiteChat",
    "SiteChatMessage",
    "SiteChatParticipantState",
    "SiteChatReport",
    "SiteUserProfile",
    "TelegramAccount",
    "VkAccount",
]
