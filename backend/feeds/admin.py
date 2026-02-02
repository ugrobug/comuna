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
    Tag,
    TagRelation,
    TagRelationType,
)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "title",
        "rubric",
        "auto_publish",
        "publish_delay_days",
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
        "publish_at",
        "created_at",
    )
    list_filter = ("is_pending", "is_blocked", "author", "rubric")
    search_fields = ("title", "content", "author__username")
    raw_id_fields = ("author", "rubric")
    fields = (
        "author",
        "rubric",
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
    list_display = ("name", "mood", "lemma", "synonym", "is_active")
    list_filter = ("mood", "is_active")
    search_fields = ("name", "lemma", "synonym")
    inlines = (TagRelationInline,)


@admin.register(TagRelation)
class TagRelationAdmin(admin.ModelAdmin):
    list_display = ("from_tag", "to_tag", "relation_type", "created_at")
    list_filter = ("relation_type",)
    search_fields = ("from_tag__name", "to_tag__name")
    raw_id_fields = ("from_tag", "to_tag")


@admin.register(TagRelationType)
class TagRelationTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "is_hidden", "sort_order")
    list_filter = ("is_active", "is_hidden")
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
        "is_hidden",
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
