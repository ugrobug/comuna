from django.contrib import admin

from notifications.models import MobilePushDevice, SiteNotification, SiteNotificationPreference


@admin.register(SiteNotificationPreference)
class SiteNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "event_key",
        "site_enabled",
        "telegram_enabled",
        "push_enabled",
        "grouping_period",
        "updated_at",
    )
    list_filter = (
        "event_key",
        "site_enabled",
        "telegram_enabled",
        "push_enabled",
        "grouping_period",
    )
    search_fields = ("user__username", "event_key")
    raw_id_fields = ("user",)


@admin.register(SiteNotification)
class SiteNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "event_key",
        "title",
        "group_key",
        "group_count",
        "is_site",
        "is_telegram",
        "is_push",
        "read_at",
        "telegram_sent_at",
        "push_sent_at",
        "created_at",
    )
    list_filter = ("event_key", "is_site", "is_telegram", "is_push", "group_key")
    search_fields = ("user__username", "title", "message", "event_key")
    raw_id_fields = ("user",)


@admin.register(MobilePushDevice)
class MobilePushDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "platform",
        "device_name",
        "app_version",
        "is_active",
        "last_seen_at",
        "last_push_sent_at",
    )
    list_filter = ("platform", "is_active")
    search_fields = ("user__username", "device_id", "device_name", "app_version", "token")
    raw_id_fields = ("user",)
