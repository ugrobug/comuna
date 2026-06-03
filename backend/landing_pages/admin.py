from django.contrib import admin

from landing_pages.models import LandingPage, LandingPageImage, LandingPageLead


class LandingPageImageInline(admin.TabularInline):
    model = LandingPageImage
    extra = 0
    fields = ("slot", "title", "alt_text", "image", "image_url", "is_active", "sort_order")


@admin.register(LandingPage)
class LandingPageAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "template_slug", "is_published", "sort_order", "updated_at")
    list_filter = ("is_published", "template_slug", "created_at", "updated_at")
    search_fields = ("title", "slug", "description")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at")
    inlines = (LandingPageImageInline,)

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LandingPageImage)
class LandingPageImageAdmin(admin.ModelAdmin):
    list_display = ("page", "slot", "title", "is_active", "sort_order", "updated_at")
    list_filter = ("page", "slot", "is_active", "created_at", "updated_at")
    search_fields = ("page__title", "page__slug", "slot", "title", "alt_text", "image_url")
    autocomplete_fields = ("page", "created_by")
    readonly_fields = ("created_at", "updated_at")

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(LandingPageLead)
class LandingPageLeadAdmin(admin.ModelAdmin):
    list_display = ("page", "source", "contact", "community_url", "created_at")
    list_filter = ("page", "source", "created_at")
    search_fields = ("contact", "community_url", "note", "page__slug", "page__title")
    readonly_fields = ("created_at",)
