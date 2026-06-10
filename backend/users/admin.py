from django.contrib import admin

from users.models import (
    AuthorAdmin as AuthorAdminLink,
    AuthorVerificationCode,
    SiteChatParticipantState,
    SiteChatReport,
)


@admin.register(AuthorAdminLink)
class AuthorAdminLinkAdmin(admin.ModelAdmin):
    list_display = ("author", "user", "verified_at", "created_at")
    search_fields = ("author__username", "user__username")
    raw_id_fields = ("author", "user")


@admin.register(AuthorVerificationCode)
class AuthorVerificationCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "code", "used_at", "created_at")
    search_fields = ("user__username", "code")
    raw_id_fields = ("user",)


@admin.register(SiteChatParticipantState)
class SiteChatParticipantStateAdmin(admin.ModelAdmin):
    list_display = ("chat", "user", "is_blocked", "hidden_at", "blocked_at", "updated_at")
    list_filter = ("is_blocked",)
    search_fields = ("user__username", "chat__id")
    raw_id_fields = ("chat", "user")


@admin.register(SiteChatReport)
class SiteChatReportAdmin(admin.ModelAdmin):
    list_display = ("id", "chat", "reporter", "reported_user", "status", "created_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("reporter__username", "reported_user__username", "message_body_snapshot")
    raw_id_fields = ("chat", "reporter", "reported_user", "message", "reviewed_by")

