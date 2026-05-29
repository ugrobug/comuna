from django.contrib import admin

from ratings.models import AuthorRatingEvent, RatingSettings


@admin.register(AuthorRatingEvent)
class AuthorRatingEventAdmin(admin.ModelAdmin):
    list_display = ("author", "event_type", "delta", "actor", "post", "comment", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("author__username", "actor__username", "post__title", "comment__body")
    raw_id_fields = ("author", "actor", "post", "comment")


@admin.register(RatingSettings)
class RatingSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "home_posts_per_community_per_day", "updated_at")
