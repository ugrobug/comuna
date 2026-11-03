from django.db import models
from django.utils import timezone


class MediaTransfer(models.Model):
    """One immutable local object and its idempotent transfer to the same S3 key."""
    key = models.CharField(max_length=500, unique=True)
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    content_type = models.CharField(max_length=120, default='application/octet-stream')
    state = models.CharField(max_length=16, default='pending')
    attempts = models.PositiveIntegerField(default=0)
    delete_requested = models.BooleanField(default=False)
    local_deleted_at = models.DateTimeField(null=True, blank=True)
    lease_token = models.CharField(max_length=32, blank=True)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    last_error = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['next_attempt_at', 'id'], condition=models.Q(state__in=['pending', 'deleting']), name='media_transfer_due_idx'),
            models.Index(fields=['id'], condition=models.Q(state__in=['uploaded', 'deleted'], local_deleted_at__isnull=True), name='media_cleanup_idx'),
            models.Index(fields=['created_at'], condition=models.Q(state__in=['pending', 'failed']), name='media_transfer_age_idx'),
        ]
