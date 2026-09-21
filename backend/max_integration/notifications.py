from django.utils import timezone
from .models import MaxAccount, MaxNotificationDelivery


def enabled(user, event_key):
    from notifications.service import _notification_preference_key
    key = _notification_preference_key(event_key)
    return MaxAccount.objects.filter(user=user, user__is_active=True, is_active=True, notification_events__contains=[key]).exists()


def enqueue(notification):
    from notifications.service import _notification_preference_key
    if not notification.delivered_at:
        return
    key = _notification_preference_key(notification.event_key)
    account = MaxAccount.objects.filter(user=notification.user, user__is_active=True, is_active=True, notification_events__contains=[key]).first()
    if account:
        MaxNotificationDelivery.objects.update_or_create(account=account, notification=notification, defaults={
            'sent_at': None, 'available_at': timezone.now(), 'attempts': 0, 'last_error': '',
        })
