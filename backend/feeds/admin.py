from django.contrib import admin

from .models import (
    Author,
    Post,
    PostComment,
    PostCommentLike,
    PostLike,
    StaticPageContent,
    Tag,
    TagRelation,
    TagRelationType,
)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "title",
        "auto_publish",
        "publish_delay_days",
        "notify_comments",
        "rating_total",
        "shadow_banned",
        "force_home",
        "is_blocked",
        "created_at",
    )
    list_filter = (
        "auto_publish",
        "notify_comments",
        "shadow_banned",
        "force_home",
        "is_blocked",
    )
    search_fields = ("username", "title")



@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "message_id",
        "is_pending",
        "is_blocked",
        "publish_at",
        "created_at",
    )
    list_filter = ("is_pending", "is_blocked", "author")
    search_fields = ("title", "content", "author__username")
    raw_id_fields = ("author",)
    fields = (
        "author",
        "tags",
        "message_id",
        "title",
        "content",
        "rating",
        "comments_count",
        "source_url",
        "channel_url",
        "is_pending",
        "is_blocked",
        "publish_at",
        "raw_data",
    )
    filter_horizontal = ("tags",)


class TagRelationInline(admin.TabularInline):
    model = TagRelation
    fk_name = "from_tag"
    extra = 1
    autocomplete_fields = ("to_tag", "relation_type")


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "mood", "lemma", "is_active", "hide_from_home")
    list_filter = ("mood", "is_active", "hide_from_home")
    search_fields = ("name", "lemma")
    inlines = (TagRelationInline,)


@admin.register(TagRelation)
class TagRelationAdmin(admin.ModelAdmin):
    list_display = ("from_tag", "to_tag", "relation_type", "created_at")
    list_filter = ("relation_type",)
    search_fields = ("from_tag__name", "to_tag__name")
    raw_id_fields = ("from_tag", "to_tag")


@admin.register(TagRelationType)
class TagRelationTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_bidirectional", "created_at")
    search_fields = ("name",)


@admin.register(StaticPageContent)
class StaticPageContentAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "updated_by", "updated_at")
    search_fields = ("slug", "title")
    readonly_fields = ("created_at", "updated_at")
    fields = ("slug", "title", "content", "updated_by", "created_at", "updated_at")


@admin.register(PostComment)
class PostCommentAdmin(admin.ModelAdmin):
    list_display = ("post", "user", "persona_username", "parent", "created_at", "is_deleted")
    list_filter = ("is_deleted",)
    search_fields = ("body", "user__username", "persona_username", "post__title")
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
