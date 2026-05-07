from django import forms
from django.contrib import admin

from communities.models import Comun, ComunCategory, ComunPostCategoryAssignment
from editor.models import (
    normalize_allowed_post_templates,
    post_template_type_choices,
)


class ComunAdminForm(forms.ModelForm):
    allowed_post_templates = forms.MultipleChoiceField(
        label="Доступные шаблоны поста",
        choices=(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Разрешенные шаблоны для публикации внутри комуны.",
    )

    class Meta:
        model = Comun
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allowed_post_templates"].choices = post_template_type_choices()
        self.fields["allowed_post_templates"].initial = normalize_allowed_post_templates(
            getattr(self.instance, "allowed_post_templates", None)
        )

    def clean_allowed_post_templates(self):
        return normalize_allowed_post_templates(self.cleaned_data.get("allowed_post_templates"))


@admin.register(ComunCategory)
class ComunCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("name", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    fields = ("name", "slug", "description", "sort_order", "is_active")


@admin.register(Comun)
class ComunAdmin(admin.ModelAdmin):
    form = ComunAdminForm
    list_display = (
        "name",
        "rating_score",
        "slug",
        "creator",
        "welcome_post",
        "is_active",
        "sort_order",
        "moderators_count",
        "categories_count",
    )
    list_filter = ("is_active", "categories")
    search_fields = ("name", "slug", "product_description", "target_audience")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("moderators", "categories")
    raw_id_fields = ("creator", "welcome_post")
    readonly_fields = ("rating_score",)
    ordering = ("-rating_score", "sort_order", "name")
    fields = (
        "name",
        "slug",
        "creator",
        "moderators",
        "welcome_post",
        "website_url",
        "logo_url",
        "product_description",
        "target_audience",
        "categories",
        "allowed_post_templates",
        "rating_score",
        "sort_order",
        "is_active",
    )

    def moderators_count(self, obj):
        return obj.moderators.count()

    moderators_count.short_description = "Модераторов"

    def categories_count(self, obj):
        return obj.categories.count()

    categories_count.short_description = "Категорий"


@admin.register(ComunPostCategoryAssignment)
class ComunPostCategoryAssignmentAdmin(admin.ModelAdmin):
    list_display = ("comun", "post", "category", "assigned_by", "updated_at")
    list_filter = ("comun", "category")
    search_fields = ("comun__name", "post__title", "post__author__username")
    raw_id_fields = ("comun", "post", "category", "assigned_by")
