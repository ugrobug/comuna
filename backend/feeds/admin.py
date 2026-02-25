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
    ThematicFeed,
)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "title",
        "rubric",
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
        "rubric",
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


@admin.register(Rubric)
class RubricAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "hide_from_home",
        "is_active",
        "is_hidden",
        "sort_order",
    )
    list_filter = ("hide_from_home", "is_active", "is_hidden")
    search_fields = ("name", "slug")
    fields = (
        "name",
        "slug",
        "description",
        "icon_url",
        "cover_image_url",
        "subscribe_url",
        "home_limit",
        "hide_from_home",
        "sort_order",
        "is_active",
        "is_hidden",
    )


@admin.register(ThematicFeed)
class ThematicFeedAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "is_active",
        "sort_order",
        "moderators_count",
        "authors_count",
        "excluded_authors_count",
        "tags_count",
        "blocked_tags_count",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = (
        "moderators",
        "authors",
        "excluded_authors",
        "tags",
        "blocked_tags",
    )
    fields = (
        "name",
        "slug",
        "description",
        "moderators",
        "authors",
        "excluded_authors",
        "tags",
        "blocked_tags",
        "sort_order",
        "is_active",
    )

    def moderators_count(self, obj):
        return obj.moderators.count()

    moderators_count.short_description = "Модераторов"

    def authors_count(self, obj):
        return obj.authors.count()

    authors_count.short_description = "Авторов"

    def excluded_authors_count(self, obj):
        return obj.excluded_authors.count()

    excluded_authors_count.short_description = "Искл. авторов"

    def tags_count(self, obj):
        return obj.tags.count()

    tags_count.short_description = "Тегов"

    def blocked_tags_count(self, obj):
        return obj.blocked_tags.count()

    blocked_tags_count.short_description = "Искл. тегов"


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
