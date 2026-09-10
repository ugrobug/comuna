from django.contrib import admin
from django.utils import timezone

from product_analytics.models import AnalyticsApiAccessLog, AnalyticsApiCredential


@admin.register(AnalyticsApiCredential)
class AnalyticsApiCredentialAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "key_prefix",
        "expires_at",
        "revoked_at",
        "last_used_at",
        "last_used_ip",
    )
    search_fields = ("name", "key_prefix")
    readonly_fields = (
        "key_prefix",
        "token_hash",
        "created_at",
        "last_used_at",
        "last_used_ip",
    )
    actions = ("revoke_credentials",)

    def has_add_permission(self, request):
        return False

    @admin.action(description="Отозвать выбранные ключи")
    def revoke_credentials(self, request, queryset):
        queryset.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())


@admin.register(AnalyticsApiAccessLog)
class AnalyticsApiAccessLogAdmin(admin.ModelAdmin):
    list_display = ("credential", "endpoint", "community_slug", "ip_address", "created_at")
    list_filter = ("endpoint", "created_at")
    search_fields = ("credential__name", "credential__key_prefix", "community_slug", "ip_address")
    readonly_fields = ("credential", "endpoint", "community_slug", "ip_address", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
