from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

from editor.models import default_allowed_post_templates

User = get_user_model()


class ComunCategory(models.Model):
    comun = models.ForeignKey(
        "feeds.Comun",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="owned_categories",
        verbose_name="Сообщество",
    )
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=120)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    allowed_post_templates = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Доступные шаблоны поста",
        help_text="Если список пустой, категория использует общие шаблоны сообщества.",
    )
    only_moderators_can_post = models.BooleanField(
        default=False,
        verbose_name="Публикация только для создателя и модераторов",
        help_text="Если включено, писать в эту категорию смогут только создатель сообщества, модераторы и администраторы сайта.",
    )
    hide_from_home = models.BooleanField(
        default=False,
        verbose_name="Не показывать в горячем",
        help_text="Посты этой категории не будут попадать в Горячее.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["comun", "slug"],
                name="feeds_unique_comun_category_slug_per_comun",
            ),
            models.UniqueConstraint(
                fields=["comun", "name"],
                name="feeds_unique_comun_category_name_per_comun",
            ),
        ]
        verbose_name = "Категория комуны"
        verbose_name_plural = "Категории коммун"

    def __str__(self) -> str:
        return self.name


class ComunGlossaryTerm(models.Model):
    comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.CASCADE,
        related_name="glossary_terms",
        verbose_name="Сообщество",
    )
    term = models.CharField(max_length=180, verbose_name="Термин")
    slug = models.SlugField(max_length=180, verbose_name="Slug термина")
    definition = models.TextField(blank=True, verbose_name="Расшифровка")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["sort_order", "term"]
        constraints = [
            models.UniqueConstraint(
                fields=["comun", "slug"],
                name="feeds_unique_comun_glossary_term_slug_per_comun",
            ),
            models.UniqueConstraint(
                fields=["comun", "term"],
                name="feeds_unique_comun_glossary_term_name_per_comun",
            ),
        ]
        verbose_name = "Термин глоссария сообщества"
        verbose_name_plural = "Термины глоссария сообществ"

    def __str__(self) -> str:
        return self.term


class Comun(models.Model):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    creator = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_comuns",
        verbose_name="Создатель",
    )
    telegram_source_author = models.OneToOneField(
        "feeds.Author",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="telegram_source_comun",
        verbose_name="Telegram-канал сообщества",
        help_text="Если указан, новые посты этого Telegram-канала попадают в сообщество.",
    )
    telegram_channel_username = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Username Telegram-канала",
        help_text="Публичный @username канала. Можно указать заранее на сайте, а затем завершить настройку в боте.",
    )
    moderators = models.ManyToManyField(
        User,
        blank=True,
        related_name="moderated_comuns",
        verbose_name="Модераторы",
        help_text="Пользователи, которые могут редактировать карточку комуны и категоризировать посты.",
    )
    excluded_authors = models.ManyToManyField(
        "feeds.Author",
        blank=True,
        related_name="excluded_from_comuns",
        verbose_name="Исключенные авторы",
        help_text="Авторы, чьи посты не будут попадать в это сообщество.",
    )
    welcome_post = models.ForeignKey(
        "feeds.Post",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="welcome_for_comuns",
        verbose_name="Приветственный пост",
    )
    categories = models.ManyToManyField(
        "feeds.ComunCategory",
        blank=True,
        related_name="comuns",
        verbose_name="Внутренние категории",
    )
    tags = models.ManyToManyField(
        "feeds.Tag",
        blank=True,
        related_name="comuns_tagged",
        verbose_name="Теги",
        help_text="Теги сообщества для поиска и сортировки.",
    )
    blocked_tags = models.ManyToManyField(
        "feeds.Tag",
        blank=True,
        related_name="comuns_blocked",
        verbose_name="Исключенные теги",
        help_text="Посты с этими тегами не будут попадать в сообщество.",
    )
    website_url = models.URLField(max_length=500, blank=True, verbose_name="Веб-сайт")
    logo_url = models.URLField(max_length=500, blank=True, verbose_name="Логотип (URL)")
    product_description = models.TextField(blank=True, verbose_name="Описание продукта")
    rules_text = models.TextField(blank=True, verbose_name="Правила сообщества")
    target_audience = models.TextField(blank=True, verbose_name="Целевая аудитория")
    glossary_enabled = models.BooleanField(
        default=False,
        verbose_name="Включить глоссарий",
        help_text="Если включено, в сообществе будет доступна публичная страница глоссария и вставка терминов в публикации.",
    )
    roadmap_enabled = models.BooleanField(
        default=False,
        verbose_name="Включить дорожную карту",
        help_text="Если включено, в сообществе будет доступна публичная дорожная карта.",
    )
    roadmap_category_ids = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Категории дорожной карты",
        help_text="ID внутренних категорий сообщества, публикации из которых попадают в дорожную карту.",
    )
    minimum_author_rating_to_post = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        verbose_name="Минимальный рейтинг автора для публикации",
        help_text="Если больше нуля, писать в коммуну смогут только авторы с указанным рейтингом или выше.",
    )
    only_moderators_can_post = models.BooleanField(
        default=False,
        verbose_name="Публикация только для создателя и модераторов",
        help_text="Если включено, писать в коммуну смогут только ее создатель, модераторы и администраторы сайта.",
    )
    forbid_external_links = models.BooleanField(
        default=False,
        verbose_name="Запретить внешние ссылки",
        help_text="Если включено, посты с внешними ссылками не будут попадать в сообщество, а новые публикации с такими ссылками будут отклоняться.",
    )
    rating_score = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Рейтинг",
    )
    votes_up = models.PositiveIntegerField(default=0, verbose_name="Буду использовать")
    votes_down = models.PositiveIntegerField(default=0, verbose_name="Не нравится")
    hide_from_home = models.BooleanField(
        default=False,
        verbose_name="Не показывать на главной",
        help_text="Посты, созданные внутри этой комуны, не будут попадать в Горячее.",
    )
    allowed_post_templates = models.JSONField(
        default=default_allowed_post_templates,
        blank=True,
        verbose_name="Доступные шаблоны поста",
        help_text="Список типов шаблонов, разрешенных для публикаций внутри комуны.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["sort_order", "name"]
        verbose_name = "Комуна"
        verbose_name_plural = "Комуны"

    def __str__(self) -> str:
        return self.name


class ComunVote(models.Model):
    comun = models.ForeignKey("feeds.Comun", on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comun_votes")
    value = models.SmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        unique_together = ("comun", "user")
        verbose_name = "Голос за коммуну"
        verbose_name_plural = "Голоса за комуны"

    def __str__(self) -> str:
        return f"{self.comun_id}:{self.user_id}:{self.value}"


class ComunPostCategoryAssignment(models.Model):
    comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.CASCADE,
        related_name="post_category_assignments",
    )
    post = models.ForeignKey(
        "feeds.Post",
        on_delete=models.CASCADE,
        related_name="comun_category_assignments",
    )
    category = models.ForeignKey(
        "feeds.ComunCategory",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="post_assignments",
    )
    assigned_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_comun_post_categories",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        unique_together = ("comun", "post")
        verbose_name = "Категория поста в комуне"
        verbose_name_plural = "Категории постов в коммунах"

    def __str__(self) -> str:
        return f"{self.comun_id}:{self.post_id}:{self.category_id or 0}"


__all__ = [
    "Comun",
    "ComunCategory",
    "ComunGlossaryTerm",
    "ComunPostCategoryAssignment",
    "ComunVote",
]
