from django.contrib import admin

from my_feed.models import FeedSourcePost, UserFeedSettings


@admin.register(UserFeedSettings)
class UserFeedSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "home_feed",
        "hide_read_posts",
        "my_feed_hide_negative",
        "updated_at",
    )
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "user",
        "home_feed",
        "hide_read_posts",
        "my_feed_authors",
        "my_feed_tags",
        "my_feed_comuns",
        "my_feed_comun_categories",
        "hidden_authors",
        "my_feed_hide_negative",
        "tag_rules",
        "created_at",
        "updated_at",
    )


@admin.register(FeedSourcePost)
class FeedSourcePostAdmin(admin.ModelAdmin):
    list_display = ("source_type", "source_id", "post", "post_created_at")
    list_filter = ("source_type",)
    search_fields = ("post__title", "post__author__username")
    readonly_fields = ("source_type", "source_id", "post", "post_created_at")
