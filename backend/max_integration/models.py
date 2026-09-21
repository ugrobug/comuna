from django.conf import settings
from django.db import models


class MaxAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='max_account')
    max_user_id = models.BigIntegerField(unique=True)
    dialog_id = models.BigIntegerField()
    name = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    notification_events = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MaxVerificationCode(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)


class MaxChat(models.Model):
    chat_id = models.BigIntegerField(unique=True)
    chat_type = models.CharField(max_length=16)
    title = models.CharField(max_length=255, blank=True)
    link = models.URLField(max_length=500, blank=True)
    is_active = models.BooleanField(default=True)
    verified_users = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='verified_max_chats')
    comun = models.ForeignKey('feeds.Comun', on_delete=models.SET_NULL, null=True, blank=True, related_name='max_chats')
    author = models.OneToOneField('feeds.Author', on_delete=models.SET_NULL, null=True, blank=True)
    auto_publish = models.BooleanField(default=True)
    publish_delay_days = models.PositiveSmallIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class MaxImportedMessage(models.Model):
    chat = models.ForeignKey(MaxChat, on_delete=models.CASCADE)
    message_id = models.CharField(max_length=255)
    post = models.OneToOneField('feeds.Post', on_delete=models.CASCADE)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['chat', 'message_id'], name='max_imported_message_unique')]


class MaxUpdate(models.Model):
    digest = models.CharField(max_length=64, unique=True)
    payload = models.JSONField()
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    processed_at = models.DateTimeField(null=True)
    last_error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['processed_at', 'available_at'])]


class MaxNotificationDelivery(models.Model):
    account = models.ForeignKey(MaxAccount, on_delete=models.CASCADE)
    notification = models.ForeignKey('feeds.SiteNotification', on_delete=models.CASCADE)
    sent_at = models.DateTimeField(null=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    available_at = models.DateTimeField()
    last_error = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['account', 'notification'], name='max_notification_unique')]


class MaxSubmission(models.Model):
    chat = models.ForeignKey(MaxChat, on_delete=models.CASCADE)
    comun = models.ForeignKey('feeds.Comun', on_delete=models.CASCADE, related_name='max_submissions')
    message_id = models.CharField(max_length=255)
    request_type = models.CharField(max_length=16, choices=[('kb', 'База знаний'), ('glossary', 'Глоссарий')])
    source_text = models.TextField()
    status = models.CharField(max_length=16, default='pending')
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['chat', 'comun', 'message_id', 'request_type'], name='max_submission_unique')]
