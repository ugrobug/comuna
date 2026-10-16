from django.contrib import admin

from telegram_integration.models import BotSession, TelegramAccount, TelegramApprovalDelivery


@admin.register(TelegramApprovalDelivery)
class TelegramApprovalDeliveryAdmin(admin.ModelAdmin):
    list_display = ('id', 'post_id', 'attempts', 'next_attempt_at', 'sent_at', 'failed_at')
    list_filter = ('sent_at', 'failed_at')
    readonly_fields = ('post', 'chat_id', 'message_id', 'attempts', 'next_attempt_at', 'sent_at', 'failed_at')
    exclude = ('lease_token',)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TelegramAccount)
class TelegramAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "telegram_id", "username", "first_name", "updated_at")
    search_fields = ("user__username", "username", "first_name", "last_name")
    raw_id_fields = ("user",)


@admin.register(BotSession)
class BotSessionAdmin(admin.ModelAdmin):
    list_display = (
        "telegram_user_id",
        "verified_user_id",
        "channel_flow",
        "selected_author",
        "selected_comun",
        "pending_forward_comun",
        "auto_publish",
        "publish_delay_days",
        "instructions_sent",
        "updated_at",
    )
    list_filter = (
        "auto_publish",
        "pending_forward_processing",
        "instructions_sent",
        "mode_selected",
        "invite_waiting",
        "channel_flow",
    )
    search_fields = (
        "telegram_user_id",
        "selected_author__username",
        "selected_comun__name",
        "pending_forward_comun__name",
    )
    raw_id_fields = ("selected_author", "selected_comun", "pending_forward_comun")
