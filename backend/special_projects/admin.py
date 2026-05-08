from django.contrib import admin

from special_projects.models import (
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
