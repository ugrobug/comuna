from django import forms
from django.contrib import admin

from .models import (
    Author,
    AuthorAdmin as AuthorAdminLink,
    POST_TEMPLATE_TYPE_CHOICES,
    AuthorVerificationCode,
    Comun,
    ComunCategory,
    ComunPostCategoryAssignment,
    Post,
    PostComment,
    PostCommentLike,
    PostLike,
    PostTemplateConfig,
    Rubric,
    SiteNotification,
    SiteNotificationPreference,
    Tag,
    TagRelation,
    TagRelationType,
    ThematicFeed,
    default_enabled_template_editor_blocks,
    normalize_allowed_post_templates,
    normalize_template_editor_blocks_for_template,
    template_editor_block_choices_for_template,
)


_POST_TEMPLATE_TYPE_FORM_CHOICES = tuple(
    (str(value), str(label)) for value, label in POST_TEMPLATE_TYPE_CHOICES
)


class RubricAdminForm(forms.ModelForm):
    allowed_post_templates = forms.MultipleChoiceField(
        label="Доступные шаблоны поста",
        choices=_POST_TEMPLATE_TYPE_FORM_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Разрешенные шаблоны для публикации в рубрике.",
    )

    class Meta:
        model = Rubric
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allowed_post_templates"].initial = normalize_allowed_post_templates(
            getattr(self.instance, "allowed_post_templates", None)
        )

    def clean_allowed_post_templates(self):
        return normalize_allowed_post_templates(self.cleaned_data.get("allowed_post_templates"))


class ComunAdminForm(forms.ModelForm):
    allowed_post_templates = forms.MultipleChoiceField(
        label="Доступные шаблоны поста",
        choices=_POST_TEMPLATE_TYPE_FORM_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Разрешенные шаблоны для публикации внутри комуны.",
    )

    class Meta:
        model = Comun
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["allowed_post_templates"].initial = normalize_allowed_post_templates(
            getattr(self.instance, "allowed_post_templates", None)
        )

    def clean_allowed_post_templates(self):
        return normalize_allowed_post_templates(self.cleaned_data.get("allowed_post_templates"))


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
        self.fields["enabled_editor_blocks"].initial = normalize_template_editor_blocks_for_template(
            template_type,
            getattr(self.instance, "enabled_editor_blocks", None)
            or default_enabled_template_editor_blocks(template_type),
        )

    def clean_enabled_editor_blocks(self):
        template_type = str(self.cleaned_data.get("template_type") or "").strip().lower()
        return normalize_template_editor_blocks_for_template(
            template_type, self.cleaned_data.get("enabled_editor_blocks")
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
    form = RubricAdminForm
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
        "allowed_post_templates",
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
        "rubrics_count",
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
        "rubrics",
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
        "rubrics",
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

    def rubrics_count(self, obj):
        return obj.rubrics.count()

    rubrics_count.short_description = "Рубрик"

    def blocked_tags_count(self, obj):
        return obj.blocked_tags.count()

    blocked_tags_count.short_description = "Искл. тегов"


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
        "slug",
        "creator",
        "product_tag",
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
    raw_id_fields = ("creator", "product_tag", "welcome_post")
    fields = (
        "name",
        "slug",
        "creator",
        "moderators",
        "product_tag",
        "welcome_post",
        "website_url",
        "logo_url",
        "product_description",
        "target_audience",
        "categories",
        "allowed_post_templates",
        "sort_order",
        "is_active",
    )

    def moderators_count(self, obj):
        return obj.moderators.count()

    moderators_count.short_description = "Модераторов"

    def categories_count(self, obj):
        return obj.categories.count()

    categories_count.short_description = "Категорий"


@admin.register(PostTemplateConfig)
class PostTemplateConfigAdmin(admin.ModelAdmin):
    form = PostTemplateConfigAdminForm
    list_display = (
        "template_type",
        "enabled_editor_blocks_display",
        "updated_at",
    )
    fields = (
        "template_type",
        "enabled_editor_blocks",
    )
    readonly_fields = ("template_type",)

    def get_queryset(self, request):
        PostTemplateConfig.ensure_defaults()
        return super().get_queryset(request)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def enabled_editor_blocks_display(self, obj):
        choices = dict(template_editor_block_choices_for_template(obj.template_type))
        values = normalize_template_editor_blocks_for_template(
            obj.template_type, obj.enabled_editor_blocks
        )
        labels = [choices.get(value, value) for value in values]
        return ", ".join(labels) if labels else "Без дополнительных блоков"

    enabled_editor_blocks_display.short_description = "Блоки редактора"


@admin.register(ComunPostCategoryAssignment)
class ComunPostCategoryAssignmentAdmin(admin.ModelAdmin):
    list_display = ("comun", "post", "category", "assigned_by", "updated_at")
    list_filter = ("comun", "category")
    search_fields = ("comun__name", "post__title", "post__author__username")
    raw_id_fields = ("comun", "post", "category", "assigned_by")


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


@admin.register(SiteNotificationPreference)
class SiteNotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "event_key", "site_enabled", "telegram_enabled", "updated_at")
    list_filter = ("event_key", "site_enabled", "telegram_enabled")
    search_fields = ("user__username", "event_key")
    raw_id_fields = ("user",)


@admin.register(SiteNotification)
class SiteNotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "event_key",
        "title",
        "is_site",
        "is_telegram",
        "read_at",
        "telegram_sent_at",
        "created_at",
    )
    list_filter = ("event_key", "is_site", "is_telegram")
    search_fields = ("user__username", "title", "message", "event_key")
    raw_id_fields = ("user",)
