from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

from editor.models import default_allowed_post_templates

User = get_user_model()


def comun_glossary_image_path(instance: "ComunGlossaryTerm", filename: str) -> str:
    return f"comuns/glossary/{instance.comun_id or 'new'}/{filename}"


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
        help_text="Если включено, писать в эту категорию смогут только создатель сообщества и модераторы.",
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
        indexes = [
            models.Index(fields=["hide_from_home"], name="comcat_hide_home_idx"),
            models.Index(fields=["comun", "is_active", "sort_order"], name="comcat_active_sort_idx"),
        ]
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
    term_en = models.CharField(max_length=180, blank=True, verbose_name="Термин на английском")
    slug = models.SlugField(max_length=180, verbose_name="Slug термина")
    definition = models.TextField(blank=True, verbose_name="Расшифровка")
    image = models.ImageField(
        upload_to=comun_glossary_image_path,
        blank=True,
        verbose_name="Картинка",
    )
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
    telegram_chat_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        verbose_name="ID Telegram-чата",
        help_text="Группа или супергруппа Telegram, из которой можно предлагать материалы в базу знаний и глоссарий.",
    )
    telegram_chat_title = models.CharField(max_length=255, blank=True, verbose_name="Название Telegram-чата")
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
    glossary_auto_link_enabled = models.BooleanField(
        default=False,
        verbose_name="Автоматически искать термины в тексте",
        help_text="Если включено, при публикации автору будут предложены найденные в тексте термины глоссария.",
    )
    roadmap_enabled = models.BooleanField(
        default=False,
        verbose_name="Включить дорожную карту",
        help_text="Если включено, в сообществе будет доступна публичная дорожная карта.",
    )
    knowledge_base_enabled = models.BooleanField(
        default=False,
        verbose_name="Включить базу знаний",
        help_text="Если включено, в сообществе будет доступна публичная база знаний из отмеченных постов.",
    )
    community_map_enabled = models.BooleanField(
        default=False,
        verbose_name="Включить общую карту",
        help_text="Если включено, в сообществе будет доступна публичная карта с GPS-метками из публикаций.",
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
        help_text="Если включено, писать в коммуну смогут только ее создатель и модераторы.",
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
    subscribers_count = models.PositiveIntegerField(default=0, verbose_name="Подписчиков")
    authors_count = models.PositiveIntegerField(default=0, verbose_name="Авторов")
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
        indexes = [
            models.Index(fields=["is_active", "-rating_score", "sort_order"], name="comun_active_rating_idx"),
            models.Index(fields=["hide_from_home"], name="comun_hide_home_idx"),
        ]
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
        indexes = [
            models.Index(fields=["category", "post"], name="compost_cat_post_idx"),
            models.Index(fields=["post", "comun"], name="compost_post_comun_idx"),
            models.Index(fields=["comun", "category", "post"], name="compost_comun_cat_post_idx"),
        ]
        verbose_name = "Категория поста в комуне"
        verbose_name_plural = "Категории постов в коммунах"

    def __str__(self) -> str:
        return f"{self.comun_id}:{self.post_id}:{self.category_id or 0}"


class ComunPostRatingContribution(models.Model):
    comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.CASCADE,
        related_name="post_rating_contributions",
    )
    post = models.ForeignKey(
        "feeds.Post",
        on_delete=models.CASCADE,
        related_name="comun_rating_contributions",
    )
    score = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        unique_together = ("comun", "post")
        indexes = [
            models.Index(fields=["comun", "-score"], name="comprc_comun_score_idx"),
            models.Index(fields=["post", "comun"], name="comprc_post_comun_idx"),
        ]
        verbose_name = "Вклад поста в рейтинг комуны"
        verbose_name_plural = "Вклады постов в рейтинг коммун"

    def __str__(self) -> str:
        return f"{self.comun_id}:{self.post_id}:{self.score}"


class ComunKnowledgeBaseItem(models.Model):
    TYPE_GROUP = "group"
    TYPE_POST = "post"
    TYPE_CHOICES = (
        (TYPE_GROUP, "Группа"),
        (TYPE_POST, "Пост"),
    )

    comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.CASCADE,
        related_name="knowledge_base_items",
    )
    post = models.ForeignKey(
        "feeds.Post",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="knowledge_base_items",
    )
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="children",
    )
    item_type = models.CharField(max_length=16, choices=TYPE_CHOICES, default=TYPE_POST)
    title = models.CharField(max_length=255, blank=True)
    sort_order = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_comun_knowledge_base_items",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["sort_order", "title", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["comun", "post"],
                condition=models.Q(post__isnull=False),
                name="comun_kb_unique_post",
            )
        ]
        indexes = [
            models.Index(fields=["comun", "parent", "sort_order"], name="comun_kb_tree_idx"),
            models.Index(fields=["post"], name="comun_kb_post_idx"),
        ]
        verbose_name = "Элемент базы знаний"
        verbose_name_plural = "База знаний сообществ"

    def __str__(self) -> str:
        return self.title or f"{self.comun_id}:{self.post_id or self.item_type}"


class ComunMapPoint(models.Model):
    comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.CASCADE,
        related_name="map_points",
        verbose_name="Сообщество",
    )
    post = models.ForeignKey(
        "feeds.Post",
        on_delete=models.CASCADE,
        related_name="comun_map_points",
        verbose_name="Пост",
    )
    block_index = models.PositiveIntegerField(default=0, verbose_name="Индекс блока")
    lat = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Широта")
    lng = models.DecimalField(max_digits=9, decimal_places=6, verbose_name="Долгота")
    zoom = models.PositiveSmallIntegerField(default=14, verbose_name="Масштаб")
    raw = models.CharField(max_length=255, blank=True, verbose_name="Исходная строка")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["-post__created_at", "post_id", "block_index", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["post", "block_index"],
                name="comun_map_point_unique_post_block",
            )
        ]
        indexes = [
            models.Index(fields=["comun", "post"], name="comun_map_comun_post_idx"),
            models.Index(fields=["post"], name="comun_map_post_idx"),
            models.Index(fields=["lat", "lng"], name="comun_map_lat_lng_idx"),
        ]
        verbose_name = "Точка общей карты"
        verbose_name_plural = "Точки общих карт"

    def __str__(self) -> str:
        return f"{self.comun_id}:{self.post_id}:{self.lat},{self.lng}"


class ComunTelegramSubmission(models.Model):
    TYPE_KNOWLEDGE_BASE = "knowledge_base"
    TYPE_GLOSSARY = "glossary"
    TYPE_CHOICES = (
        (TYPE_KNOWLEDGE_BASE, "База знаний"),
        (TYPE_GLOSSARY, "Глоссарий"),
    )

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "На модерации"),
        (STATUS_APPROVED, "Утверждено"),
        (STATUS_REJECTED, "Отклонено"),
    )

    comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.CASCADE,
        related_name="telegram_submissions",
        verbose_name="Сообщество",
    )
    request_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_PENDING)
    requested_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comun_telegram_submissions",
        verbose_name="Предложил пользователь",
    )
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_comun_telegram_submissions",
        verbose_name="Проверил пользователь",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    telegram_user_id = models.BigIntegerField(null=True, blank=True)
    telegram_username = models.CharField(max_length=255, blank=True)
    telegram_chat_id = models.BigIntegerField()
    telegram_chat_title = models.CharField(max_length=255, blank=True)
    telegram_source_message_id = models.BigIntegerField()
    telegram_request_message_id = models.BigIntegerField(null=True, blank=True)
    telegram_source_url = models.URLField(max_length=500, blank=True)
    source_author_name = models.CharField(max_length=255, blank=True)
    source_text = models.TextField()
    title = models.CharField(max_length=255, blank=True)
    glossary_term = models.CharField(max_length=180, blank=True)
    glossary_definition = models.TextField(blank=True)
    created_post = models.ForeignKey(
        "feeds.Post",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="telegram_knowledge_base_submissions",
    )
    created_glossary_term = models.ForeignKey(
        "feeds.ComunGlossaryTerm",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="telegram_submissions",
    )
    source_payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["comun", "status", "-created_at"], name="comtgsub_comun_status_idx"),
            models.Index(fields=["telegram_chat_id", "telegram_source_message_id"], name="comtgsub_tg_msg_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["comun", "request_type", "telegram_chat_id", "telegram_source_message_id"],
                condition=models.Q(status="pending"),
                name="comtgsub_unique_pending_source",
            )
        ]
        verbose_name = "Telegram-заявка сообщества"
        verbose_name_plural = "Telegram-заявки сообществ"

    def __str__(self) -> str:
        return f"{self.comun_id}:{self.request_type}:{self.status}:{self.id}"


__all__ = [
    "Comun",
    "ComunCategory",
    "ComunGlossaryTerm",
    "ComunKnowledgeBaseItem",
    "ComunPostCategoryAssignment",
    "ComunPostRatingContribution",
    "ComunTelegramSubmission",
    "ComunVote",
]
