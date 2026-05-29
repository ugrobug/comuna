from django import forms
from django.contrib import admin

from editor.models import (
    PostTemplateConfig,
    default_enabled_template_editor_blocks,
    normalize_template_editor_blocks_for_template,
    template_editor_block_choices_for_template,
)


class PostTemplateConfigAdminForm(forms.ModelForm):
    enabled_editor_blocks = forms.MultipleChoiceField(
        label="Доступные блоки редактора",
        choices=(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Отмеченные блоки будут доступны в редакторе для этого шаблона.",
    )

    class Meta:
        model = PostTemplateConfig
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        template_type = (
            str(
                self.instance.template_type
                or self.initial.get("template_type")
                or self.data.get("template_type")
                or ""
            )
            .strip()
            .lower()
        )
        choices = template_editor_block_choices_for_template(template_type)
        self.fields["enabled_editor_blocks"].choices = choices
        current_blocks = getattr(self.instance, "enabled_editor_blocks", None)
        if current_blocks is None:
            current_blocks = default_enabled_template_editor_blocks(template_type)
        self.fields["enabled_editor_blocks"].initial = normalize_template_editor_blocks_for_template(
            template_type,
            current_blocks,
        )

    def clean_enabled_editor_blocks(self):
        template_type = str(self.cleaned_data.get("template_type") or "").strip().lower()
        return normalize_template_editor_blocks_for_template(
            template_type, self.cleaned_data.get("enabled_editor_blocks")
        )


@admin.register(PostTemplateConfig)
class PostTemplateConfigAdmin(admin.ModelAdmin):
    form = PostTemplateConfigAdminForm
    list_display = (
        "template_type",
        "label",
        "description_short",
        "custom_template",
        "enabled_editor_blocks_display",
        "updated_at",
    )
    list_filter = ("custom_template__comun",)
    search_fields = (
        "template_type",
        "label",
        "description",
        "custom_template__name",
        "custom_template__comun__name",
    )
    fields = (
        "template_type",
        "label",
        "description",
        "custom_template",
        "enabled_editor_blocks",
        "is_active",
    )
    readonly_fields = ("template_type", "custom_template")

    def get_queryset(self, request):
        PostTemplateConfig.ensure_defaults()
        return super().get_queryset(request).filter(is_active=True)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    def delete_model(self, request, obj):
        obj.is_active = False
        obj.save(update_fields=["is_active", "updated_at"])

    def delete_queryset(self, request, queryset):
        queryset.update(is_active=False)

    def enabled_editor_blocks_display(self, obj):
        choices = dict(template_editor_block_choices_for_template(obj.template_type))
        values = normalize_template_editor_blocks_for_template(
            obj.template_type, obj.enabled_editor_blocks
        )
        labels = [choices.get(value, value) for value in values]
        return ", ".join(labels) if labels else "Без дополнительных блоков"

    enabled_editor_blocks_display.short_description = "Блоки редактора"

    def description_short(self, obj):
        description = str(getattr(obj, "description", "") or "").strip()
        if not description:
            return "—"
        return description if len(description) <= 120 else f"{description[:117]}..."

    description_short.short_description = "Описание"
