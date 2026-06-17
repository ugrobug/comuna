"""Критерии «статьи» в WordPress (romawho). Используется в скриптах миграции."""

from django.db.models import Q, QuerySet

from legacy_migration.models import WpPosts

# Статьи на ПТ: URL /articles/..., в БД — обычный WP post (не отдельный CPT)
ARTICLE_POST_TYPE = "post"
ARTICLE_POST_STATUS = "publish"

# Статусы, которые считаем реально существующими на сайте (прочие сущности)
PUBLISHED_STATUSES = ("publish", "future", "private")

# Служебные типы wp_posts — не контент для переноса
NON_ARTICLE_POST_TYPES = (
    "rp4wp_link",  # Related Posts for wp — тысячи служебных записей
    "revision",
    "attachment",
    "nav_menu_item",
    "wp_block",
    "custom_css",
    "customize_changeset",
    "oembed_cache",
    "acf-field",
    "acf-field-group",
    "wp_navigation",
    "wp_template",
    "wp_template_part",
    "wp_global_styles",
    "wp_font_family",
    "wp_font_face",
)


def articles_q() -> Q:
    return Q(post_type=ARTICLE_POST_TYPE, post_status=ARTICLE_POST_STATUS)


def articles_queryset() -> QuerySet[WpPosts]:
    return WpPosts.objects.filter(articles_q()).order_by("-post_date")


def wp_has_ez_toc(wp_post_id: int) -> bool:
    from legacy_migration.models import WpPostmeta

    return WpPostmeta.objects.filter(
        post_id=wp_post_id,
        meta_key="_ez-toc-insert",
        meta_value="1",
    ).exists()
