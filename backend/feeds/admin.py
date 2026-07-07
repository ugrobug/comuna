from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponseRedirect
from django.urls import path, reverse
from django.utils.html import format_html_join

from .models import (
    Author,
    ComunTranslation,
    ContentTranslationTask,
    ContentTranslationRun,
    ContentTranslationSettings,
    Post,
    PostComment,
    PostCommentLike,
    PostCommentTranslation,
    PostLike,
    PostTranslation,
    PostViewSettings,
    StaticPageContent,
    StaticPageTranslation,
    Tag,
    TagRelation,
    TagRelationType,
)
from .translation_service import (
    PostTranslationError,
    SUPPORTED_TRANSLATION_LANGUAGES,
    get_translation_language_label,
    queue_post_translation,
)


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = (
        "username",
        "title",
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
        "message_id",
        "is_pending",
        "is_blocked",
        "publish_at",
        "created_at",
        "translation_actions",
    )
    list_filter = ("is_pending", "is_blocked", "author")
    search_fields = ("title", "content", "author__username")
    raw_id_fields = ("author",)
    readonly_fields = ("translation_actions",)
    fields = (
        "author",
        "tags",
        "message_id",
        "title",
        "content",
        "translation_actions",
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/translate/<str:language>/",
                self.admin_site.admin_view(self.translate_view),
                name="feeds_post_translate",
            ),
        ]
        return custom_urls + urls

    @admin.display(description="Перевод")
    def translation_actions(self, obj: Post):
        if not obj or not obj.pk:
            return "Сохраните пост перед переводом"
        links = [
            (
                reverse("admin:feeds_post_translate", args=[obj.pk, language]),
                f"Перевести {language.upper()}",
            )
            for language in SUPPORTED_TRANSLATION_LANGUAGES
        ]
        links.append(
            (
                reverse("admin:feeds_post_translate", args=[obj.pk, "all"]),
                "Перевести все",
            )
        )
        return format_html_join(" ", '<a class="button" href="{}">{}</a>', links)

    def translate_view(self, request: HttpRequest, object_id: str, language: str):
        post = self.get_object(request, object_id)
        if post is None:
            messages.error(request, "Пост не найден")
            return HttpResponseRedirect(reverse("admin:feeds_post_changelist"))
        if not self.has_change_permission(request, post):
            raise PermissionDenied

        try:
            if language == "all":
                translations = queue_post_translation(
                    post,
                    list(SUPPORTED_TRANSLATION_LANGUAGES),
                )
            else:
                translations = queue_post_translation(post, [language])
            labels = ", ".join(
                get_translation_language_label(translation.language)
                for translation in translations
            )
            messages.success(
                request,
                f"Перевод запущен: {labels}. Обновите страницу через минуту.",
            )
        except PostTranslationError as exc:
            messages.error(request, f"Не удалось запустить перевод: {exc}")

        fallback_url = reverse("admin:feeds_post_change", args=[post.pk])
        return HttpResponseRedirect(request.META.get("HTTP_REFERER") or fallback_url)


class PostTranslationInline(admin.StackedInline):
    model = PostTranslation
    extra = 0
    show_change_link = True
    fields = (
        "language",
        "status",
        "title",
        "content",
        "preview_content",
        "model",
        "error_message",
        "created_at",
        "updated_at",
    )
    readonly_fields = ("status", "model", "error_message", "created_at", "updated_at")


PostAdmin.inlines = (PostTranslationInline,)


@admin.register(PostTranslation)
class PostTranslationAdmin(admin.ModelAdmin):
    list_display = ("post", "language", "status", "model", "updated_at")
    list_filter = ("language", "status", "model")
    search_fields = ("post__title", "title", "content")
    raw_id_fields = ("post",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ContentTranslationSettings)
class ContentTranslationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "enabled",
        "post_daily_limit",
        "comment_daily_limit",
        "post_object_daily_limit",
        "updated_at",
    )


@admin.register(ContentTranslationRun)
class ContentTranslationRunAdmin(admin.ModelAdmin):
    list_display = ("kind", "object_id", "task", "created_at")
    list_filter = ("kind",)
    search_fields = ("object_id",)
    raw_id_fields = ("task",)
    date_hierarchy = "created_at"


@admin.register(PostCommentTranslation)
class PostCommentTranslationAdmin(admin.ModelAdmin):
    list_display = ("comment", "language", "status", "model", "updated_at")
    list_filter = ("language", "status", "model")
    search_fields = ("comment__body", "body", "comment__post__title")
    raw_id_fields = ("comment",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(ComunTranslation)
class ComunTranslationAdmin(admin.ModelAdmin):
    list_display = ("comun", "language", "status", "model", "updated_at")
    list_filter = ("language", "status", "model")
    search_fields = ("comun__name", "name", "product_description", "target_audience", "rules_text")
    raw_id_fields = ("comun",)
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "comun",
        "language",
        "status",
        "name",
        "product_description",
        "target_audience",
        "rules_text",
        "categories",
        "glossary_terms",
        "model",
        "error_message",
        "raw_response",
        "created_at",
        "updated_at",
    )


@admin.register(ContentTranslationTask)
class ContentTranslationTaskAdmin(admin.ModelAdmin):
    list_display = ("kind", "object_id", "status", "scheduled_at", "attempts", "updated_at")
    list_filter = ("kind", "status")
    search_fields = ("object_id", "last_error")
    readonly_fields = ("created_at", "updated_at", "locked_at")


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


@admin.register(StaticPageContent)
class StaticPageContentAdmin(admin.ModelAdmin):
    list_display = ("slug", "title", "updated_by", "updated_at")
    search_fields = ("slug", "title")
    readonly_fields = ("created_at", "updated_at")
    fields = ("slug", "title", "content", "updated_by", "created_at", "updated_at")


@admin.register(StaticPageTranslation)
class StaticPageTranslationAdmin(admin.ModelAdmin):
    list_display = ("page", "language", "status", "model", "updated_at")
    list_filter = ("language", "status")
    search_fields = ("page__slug", "title", "content", "error_message")
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "page",
        "language",
        "status",
        "title",
        "content",
        "model",
        "error_message",
        "raw_response",
        "created_at",
        "updated_at",
    )


@admin.register(PostViewSettings)
class PostViewSettingsAdmin(admin.ModelAdmin):
    list_display = ("id", "fake_views_target_min", "fake_views_target_max", "updated_at")
    readonly_fields = ("updated_at",)


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
