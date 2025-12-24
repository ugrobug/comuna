from django.contrib import admin

from .models import Author, Post, Rubric


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ("username", "title", "is_blocked", "created_at")
    list_filter = ("is_blocked",)
    search_fields = ("username", "title")



@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "author", "rubric", "message_id", "is_blocked", "created_at")
    list_filter = ("is_blocked", "author", "rubric")
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
