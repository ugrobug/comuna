from django.contrib import admin

from .models import (
    Author,
    AuthorAdmin as AuthorAdminLink,
    AuthorVerificationCode,
    Post,
    PostComment,
    PostCommentLike,
    PostLike,
    Rubric,
)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "title",
        "rubric",
        "auto_publish",
        "shadow_banned",
        "force_home",
        "is_blocked",
        "created_at",
    )
    list_filter = ("rubric", "auto_publish", "shadow_banned", "force_home", "is_blocked")
    search_fields = ("username", "title")



@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "rubric",
        "message_id",
        "is_pending",
        "is_blocked",
        "created_at",
    )
    list_filter = ("is_pending", "is_blocked", "author", "rubric")
    search_fields = ("title", "content", "author__username")
    raw_id_fields = ("author", "rubric")
    fields = (
        "author",
        "rubric",
        "message_id",
        "title",
        "content",
        "rating",
        "comments_count",
        "source_url",
        "channel_url",
        "is_pending",
        "is_blocked",
        "raw_data",
    )


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    fields = (
        "name",
        "slug",
        "description",
        "icon_url",
        "cover_image_url",
        "subscribe_url",
        "home_limit",
        "sort_order",
        "is_active",
    )


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "parent", "created_at", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("body", "user__username", "post__title")
    raw_id_fields = ("post", "user", "parent")


@admin.register(PostLike)
class PostLikeAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "value", "created_at")
    search_fields = ("user__username", "post__title")
    raw_id_fields = ("post", "user")


@admin.register(PostCommentLike)
class PostCommentLikeAdmin(admin.ModelAdmin):
    list_display = ("comment", "user", "created_at")
    search_fields = ("user__username", "comment__post__title")
    raw_id_fields = ("comment", "user")


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
