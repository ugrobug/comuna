from django.contrib import admin

from special_projects import film_journey
from special_projects.models import (
    FilmJourneyEntry,
    FilmJourneyFilm,
    FilmJourneySubscription,
    SpecialProjectGeneratedPhrase,
    SpecialProjectLetterImage,
    SpecialProjectLetterSuggestion,
)


@admin.register(SpecialProjectLetterImage)
class SpecialProjectLetterImageAdmin(admin.ModelAdmin):
    list_display = (
        "project_slug",
        "letter",
        "title",
        "location_name",
        "is_active",
        "sort_order",
        "updated_at",
    )
    list_filter = ("project_slug", "letter", "is_active")
    search_fields = ("letter", "title", "location_name", "map_url", "source_name")
    ordering = ("project_slug", "letter", "sort_order")


@admin.register(SpecialProjectLetterSuggestion)
class SpecialProjectLetterSuggestionAdmin(admin.ModelAdmin):
    list_display = (
        "project_slug",
        "letter",
        "status",
        "submitted_by",
        "coordinates_text",
        "created_at",
    )
    list_filter = ("project_slug", "letter", "status", "created_at")
    search_fields = ("letter", "map_url", "coordinates_text", "location_note", "submitted_by__username")
    autocomplete_fields = ("submitted_by", "reviewed_by")


@admin.register(SpecialProjectGeneratedPhrase)
class SpecialProjectGeneratedPhraseAdmin(admin.ModelAdmin):
    list_display = (
        "project_slug",
        "text",
        "was_shared",
        "share_clicks",
        "generated_by",
        "created_at",
        "shared_at",
    )
    list_filter = ("project_slug", "was_shared", "created_at", "shared_at")
    search_fields = ("text", "share_query", "generated_by__username")
    autocomplete_fields = ("generated_by",)
    readonly_fields = ("created_at", "updated_at", "shared_at")


@admin.register(FilmJourneyFilm)
class FilmJourneyFilmAdmin(admin.ModelAdmin):
    list_display = (
        "sort_order",
        "title",
        "original_title",
        "year",
        "category",
        "imdb_rating",
        "is_active",
        "updated_at",
    )
    list_filter = ("project_slug", "category", "is_active", "year")
    search_fields = ("title", "original_title", "description", "imdb_url", "director", "genres")
    ordering = ("project_slug", "sort_order", "id")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        data = {
            "project_slug": obj.project_slug,
            "title": obj.title,
            "original_title": obj.original_title,
            "year": obj.year,
            "category": obj.category,
            "description": obj.description,
            "imdb_url": obj.imdb_url,
            "imdb_rating": obj.imdb_rating,
            "poster_url": obj.poster_url,
            "runtime_minutes": obj.runtime_minutes,
            "director": obj.director,
            "country": obj.country,
            "genres": obj.genres,
            "sort_order": obj.sort_order,
            "is_active": obj.is_active,
        }
        film_journey.apply_imdb_autofill_to_film_payload(data)
        for field, value in data.items():
            setattr(obj, field, value)
        super().save_model(request, obj, form, change)


class FilmJourneyEntryInline(admin.TabularInline):
    model = FilmJourneyEntry
    extra = 0
    readonly_fields = (
        "access_token",
        "available_at",
        "notification_sent_at",
        "first_reminder_sent_at",
        "second_reminder_sent_at",
        "completed_at",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("film",)
    fields = (
        "position",
        "film",
        "rating",
        "comment",
        "access_token",
        "notification_sent_at",
        "completed_at",
    )


@admin.register(FilmJourneySubscription)
class FilmJourneySubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "started_at",
        "next_delivery_at",
        "last_delivered_at",
        "paused_at",
        "completed_at",
    )
    list_filter = ("project_slug", "status", "started_at", "paused_at")
    search_fields = ("user__username", "user__email", "pause_reason")
    autocomplete_fields = ("user",)
    readonly_fields = ("started_at", "created_at", "updated_at")
    inlines = (FilmJourneyEntryInline,)


@admin.register(FilmJourneyEntry)
class FilmJourneyEntryAdmin(admin.ModelAdmin):
    list_display = (
        "subscription",
        "position",
        "film",
        "rating",
        "notification_sent_at",
        "completed_at",
    )
    list_filter = ("completed_at", "notification_sent_at", "first_reminder_sent_at", "second_reminder_sent_at")
    search_fields = ("film__title", "film__original_title", "subscription__user__username", "comment")
    autocomplete_fields = ("subscription", "film")
    readonly_fields = (
        "access_token",
        "available_at",
        "notification_sent_at",
        "first_reminder_sent_at",
        "second_reminder_sent_at",
        "created_at",
        "updated_at",
    )
