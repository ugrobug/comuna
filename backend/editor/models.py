from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()

POST_TEMPLATE_TYPE_BASIC = "basic"
POST_TEMPLATE_TYPE_MOVIE_REVIEW = "movie_review"
POST_TEMPLATE_TYPE_POST_VOTE_POLL = "post_vote_poll"
POST_TEMPLATE_TYPE_MUSIC_RELEASE = "music_release"
POST_TEMPLATE_TYPE_CHOICES = (
    (POST_TEMPLATE_TYPE_BASIC, "Пост"),
    (POST_TEMPLATE_TYPE_MOVIE_REVIEW, "Кинообзор"),
    (POST_TEMPLATE_TYPE_POST_VOTE_POLL, "Голосование за посты"),
    (POST_TEMPLATE_TYPE_MUSIC_RELEASE, "Музыкальный релиз"),
)
POST_TEMPLATE_TYPE_VALUES = {value for value, _label in POST_TEMPLATE_TYPE_CHOICES}

POST_TEMPLATE_EDITOR_BLOCK_HEADER = "header"
POST_TEMPLATE_EDITOR_BLOCK_TOC = "toc"
POST_TEMPLATE_EDITOR_BLOCK_LIST = "list"
POST_TEMPLATE_EDITOR_BLOCK_TABLE = "table"
POST_TEMPLATE_EDITOR_BLOCK_IMAGE = "image"
POST_TEMPLATE_EDITOR_BLOCK_QUOTE = "quote"
POST_TEMPLATE_EDITOR_BLOCK_CALLOUT = "callout"
POST_TEMPLATE_EDITOR_BLOCK_AUTHOR = "author"
POST_TEMPLATE_EDITOR_BLOCK_CODE = "code"
POST_TEMPLATE_EDITOR_BLOCK_POLL = "poll"
POST_TEMPLATE_EDITOR_BLOCK_DIVIDER = "divider"
POST_TEMPLATE_EDITOR_BLOCK_SPOILER = "spoiler"
POST_TEMPLATE_EDITOR_BLOCK_GALLERY = "gallery"
POST_TEMPLATE_EDITOR_BLOCK_MAP = "map"
POST_TEMPLATE_EDITOR_BLOCK_COMPARE = "compare"
POST_TEMPLATE_EDITOR_BLOCK_LINK = "link"
POST_TEMPLATE_EDITOR_BLOCK_EMBED = "embed"
POST_TEMPLATE_EDITOR_BLOCK_POST_LINK = "post_link"
POST_TEMPLATE_EDITOR_BLOCK_MUSIC = "music"
POST_TEMPLATE_EDITOR_BLOCK_MOVIE_TIME = "movie_time"
POST_TEMPLATE_EDITOR_BLOCK_MOVIE_CARD = "movie_card"
POST_TEMPLATE_EDITOR_BLOCK_POST_RATING = "post_rating"
POST_TEMPLATE_EDITOR_BLOCK_CHOICES = (
    (POST_TEMPLATE_EDITOR_BLOCK_TOC, "Оглавление"),
    (POST_TEMPLATE_EDITOR_BLOCK_HEADER, "Заголовок"),
    (POST_TEMPLATE_EDITOR_BLOCK_LIST, "Список"),
    (POST_TEMPLATE_EDITOR_BLOCK_TABLE, "Таблица"),
    (POST_TEMPLATE_EDITOR_BLOCK_IMAGE, "Изображение"),
    (POST_TEMPLATE_EDITOR_BLOCK_QUOTE, "Цитата"),
    (POST_TEMPLATE_EDITOR_BLOCK_CALLOUT, "Врезка"),
    (POST_TEMPLATE_EDITOR_BLOCK_AUTHOR, "Автор"),
    (POST_TEMPLATE_EDITOR_BLOCK_CODE, "Код"),
    (POST_TEMPLATE_EDITOR_BLOCK_POLL, "Опрос"),
    (POST_TEMPLATE_EDITOR_BLOCK_DIVIDER, "Разделитель"),
    (POST_TEMPLATE_EDITOR_BLOCK_SPOILER, "Спойлер"),
    (POST_TEMPLATE_EDITOR_BLOCK_GALLERY, "Галерея"),
    (POST_TEMPLATE_EDITOR_BLOCK_MAP, "Карта"),
    (POST_TEMPLATE_EDITOR_BLOCK_COMPARE, "Сравнение изображений"),
    (POST_TEMPLATE_EDITOR_BLOCK_LINK, "Ссылка"),
    (POST_TEMPLATE_EDITOR_BLOCK_EMBED, "Встраивание (Embed)"),
    (POST_TEMPLATE_EDITOR_BLOCK_POST_LINK, "Ссылка на пост"),
    (POST_TEMPLATE_EDITOR_BLOCK_MUSIC, "Музыка"),
    (POST_TEMPLATE_EDITOR_BLOCK_MOVIE_TIME, "Время в фильме"),
    (POST_TEMPLATE_EDITOR_BLOCK_MOVIE_CARD, "Карточка фильма"),
    (POST_TEMPLATE_EDITOR_BLOCK_POST_RATING, "Рейтинг"),
)
POST_TEMPLATE_EDITOR_BLOCK_VALUES = {
    value for value, _label in POST_TEMPLATE_EDITOR_BLOCK_CHOICES
}
POST_TEMPLATE_EDITOR_BLOCK_OPTION_ITEMS = [
    {"value": value, "label": label} for value, label in POST_TEMPLATE_EDITOR_BLOCK_CHOICES
]
POST_TEMPLATE_EDITOR_BLOCK_ALL_VALUES = tuple(
    value for value, _label in POST_TEMPLATE_EDITOR_BLOCK_CHOICES
)
POST_TEMPLATE_EDITOR_BLOCK_BASIC_VALUES = tuple(
    value
    for value in POST_TEMPLATE_EDITOR_BLOCK_ALL_VALUES
    if value != POST_TEMPLATE_EDITOR_BLOCK_MOVIE_CARD
)
POST_TEMPLATE_EDITOR_BLOCKS_BY_TEMPLATE = {
    POST_TEMPLATE_TYPE_BASIC: POST_TEMPLATE_EDITOR_BLOCK_BASIC_VALUES,
    POST_TEMPLATE_TYPE_MOVIE_REVIEW: POST_TEMPLATE_EDITOR_BLOCK_ALL_VALUES,
    POST_TEMPLATE_TYPE_POST_VOTE_POLL: POST_TEMPLATE_EDITOR_BLOCK_BASIC_VALUES,
    POST_TEMPLATE_TYPE_MUSIC_RELEASE: POST_TEMPLATE_EDITOR_BLOCK_BASIC_VALUES,
}

COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_AVAILABLE = "available"
COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_HEADER = "header"
COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_FOOTER = "footer"
COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_CHOICES = (
    (COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_AVAILABLE, "Доступен в шаблоне"),
    (COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_HEADER, "Хедер"),
    (COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_FOOTER, "Футер"),
)
COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_VALUES = {
    value for value, _label in COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_CHOICES
}
COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_OPTION_ITEMS = [
    {"value": value, "label": label}
    for value, label in COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_CHOICES
]

COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_TEXT = "text"
COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_FILE = "file"
COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_SELECT = "select"
COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHECKBOX = "checkbox"
COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHOICES = (
    (COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_TEXT, "Текст"),
    (COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_FILE, "Файл"),
    (COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_SELECT, "Выбор значений"),
    (COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHECKBOX, "Чекбокс"),
)
COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_VALUES = {
    value for value, _label in COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHOICES
}
COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_OPTION_ITEMS = [
    {"value": value, "label": label}
    for value, label in COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHOICES
]

COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_HEADER = "header"
COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_FOOTER = "footer"
COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_CHOICES = (
    (COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_HEADER, "Хедер"),
    (COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_FOOTER, "Футер"),
)
COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_VALUES = {
    value for value, _label in COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_CHOICES
}
COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_OPTION_ITEMS = [
    {"value": value, "label": label}
    for value, label in COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_CHOICES
]


def default_allowed_post_templates() -> list[str]:
    return [POST_TEMPLATE_TYPE_BASIC]


def normalize_allowed_post_templates(raw_value: object) -> list[str]:
    if isinstance(raw_value, str):
        candidates = [raw_value]
    elif isinstance(raw_value, (list, tuple, set)):
        candidates = list(raw_value)
    else:
        candidates = []

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = str(candidate or "").strip().lower()
        if not value or value not in POST_TEMPLATE_TYPE_VALUES:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    if not normalized:
        return default_allowed_post_templates()
    return normalized


def normalize_allowed_post_templates_override(raw_value: object) -> list[str]:
    if isinstance(raw_value, str):
        candidates = [raw_value]
    elif isinstance(raw_value, (list, tuple, set)):
        candidates = list(raw_value)
    else:
        candidates = []

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        value = str(candidate or "").strip().lower()
        if not value or value not in POST_TEMPLATE_TYPE_VALUES:
            continue
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def template_editor_block_choices_for_template(template_type: str) -> tuple[tuple[str, str], ...]:
    normalized_template_type = str(template_type or "").strip().lower()
    available_blocks = set(
        POST_TEMPLATE_EDITOR_BLOCKS_BY_TEMPLATE.get(
            normalized_template_type, POST_TEMPLATE_EDITOR_BLOCK_ALL_VALUES
        )
    )
    if not available_blocks:
        return ()
    return tuple(
        (value, label)
        for value, label in POST_TEMPLATE_EDITOR_BLOCK_CHOICES
        if value in available_blocks
    )


def default_enabled_template_editor_blocks(template_type: str) -> list[str]:
    return [
        value
        for value, _label in template_editor_block_choices_for_template(template_type)
    ]


def normalize_template_editor_blocks_for_template(
    template_type: str,
    raw_value: object,
) -> list[str]:
    available_choices = template_editor_block_choices_for_template(template_type)
    available_blocks = {value for value, _label in available_choices}
    if not available_blocks:
        return []

    if isinstance(raw_value, str):
        candidates = [raw_value]
    elif isinstance(raw_value, (list, tuple, set)):
        candidates = list(raw_value)
    else:
        candidates = []

    selected: set[str] = set()
    for candidate in candidates:
        value = str(candidate or "").strip().lower()
        if not value or value not in available_blocks:
            continue
        selected.add(value)

    return [value for value, _label in available_choices if value in selected]


class PostTemplateConfig(models.Model):
    template_type = models.CharField(
        max_length=32,
        choices=POST_TEMPLATE_TYPE_CHOICES,
        unique=True,
        verbose_name="Тип шаблона",
    )
    enabled_editor_blocks = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Доступные блоки редактора",
        help_text="Блоки редактора, которые можно использовать внутри шаблона.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["template_type"]
        verbose_name = "Настройка шаблона поста"
        verbose_name_plural = "Настройки шаблонов постов"

    def __str__(self) -> str:
        return self.get_template_type_display()

    @classmethod
    def ensure_defaults(cls) -> None:
        existing_types = set(cls.objects.values_list("template_type", flat=True))
        missing_types = [
            template_type
            for template_type, _label in POST_TEMPLATE_TYPE_CHOICES
            if template_type not in existing_types
        ]
        if not missing_types:
            return
        cls.objects.bulk_create(
            [
                cls(
                    template_type=template_type,
                    enabled_editor_blocks=default_enabled_template_editor_blocks(template_type),
                )
                for template_type in missing_types
            ]
        )

    def clean(self) -> None:
        super().clean()
        template_type = (self.template_type or "").strip().lower()
        self.template_type = template_type
        self.enabled_editor_blocks = normalize_template_editor_blocks_for_template(
            template_type, self.enabled_editor_blocks
        )

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class ComunCustomPostTemplate(models.Model):
    comun = models.ForeignKey(
        "feeds.Comun",
        on_delete=models.CASCADE,
        related_name="custom_post_templates",
    )
    name = models.CharField(max_length=120, verbose_name="Название шаблона")
    slug = models.SlugField(max_length=160, verbose_name="Слаг шаблона")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["sort_order", "name", "id"]
        unique_together = (("comun", "slug"),)
        verbose_name = "Пользовательский шаблон сообщества"
        verbose_name_plural = "Пользовательские шаблоны сообществ"

    def __str__(self) -> str:
        return self.name


class ComunCustomPostTemplateBlock(models.Model):
    template = models.ForeignKey(
        ComunCustomPostTemplate,
        on_delete=models.CASCADE,
        related_name="block_rules",
    )
    block_type = models.CharField(
        max_length=64,
        choices=POST_TEMPLATE_EDITOR_BLOCK_CHOICES,
        verbose_name="Блок редактора",
    )
    placement = models.CharField(
        max_length=16,
        choices=COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_CHOICES,
        default=COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_AVAILABLE,
        verbose_name="Расположение",
    )
    is_required = models.BooleanField(default=False, verbose_name="Обязательный")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["sort_order", "id"]
        unique_together = (("template", "block_type"),)
        verbose_name = "Блок пользовательского шаблона сообщества"
        verbose_name_plural = "Блоки пользовательских шаблонов сообществ"

    def __str__(self) -> str:
        return f"{self.template_id}:{self.block_type}"


class ComunCustomPostTemplateField(models.Model):
    template = models.ForeignKey(
        ComunCustomPostTemplate,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    key = models.SlugField(max_length=160, verbose_name="Ключ поля")
    label = models.CharField(max_length=120, verbose_name="Название поля")
    field_type = models.CharField(
        max_length=16,
        choices=COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHOICES,
        default=COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_TEXT,
        verbose_name="Тип поля",
    )
    placement = models.CharField(
        max_length=16,
        choices=COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_CHOICES,
        default=COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_HEADER,
        verbose_name="Расположение",
    )
    is_required = models.BooleanField(default=False, verbose_name="Обязательное")
    options = models.JSONField(default=list, blank=True, verbose_name="Опции выбора")
    settings = models.JSONField(default=dict, blank=True, verbose_name="Настройки поля")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="Порядок")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        ordering = ["sort_order", "id"]
        unique_together = (("template", "key"),)
        verbose_name = "Поле пользовательского шаблона сообщества"
        verbose_name_plural = "Поля пользовательских шаблонов сообществ"

    def __str__(self) -> str:
        return f"{self.template_id}:{self.key}"


class PostPollVote(models.Model):
    post = models.ForeignKey("feeds.Post", on_delete=models.CASCADE, related_name="poll_votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_poll_votes")
    selected_options = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        unique_together = ("post", "user")

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class PostRatingVote(models.Model):
    post = models.ForeignKey("feeds.Post", on_delete=models.CASCADE, related_name="rating_votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_rating_votes")
    block_id = models.CharField(max_length=64, blank=True, default="")
    value = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "feeds"
        unique_together = ("post", "user", "block_id")
        verbose_name = "Оценка поста"
        verbose_name_plural = "Оценки постов"

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}:{self.block_id}:{self.value}"


__all__ = [
    "COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_AVAILABLE",
    "COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_HEADER",
    "COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_FOOTER",
    "COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_CHOICES",
    "COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_VALUES",
    "COMUN_CUSTOM_TEMPLATE_BLOCK_PLACEMENT_OPTION_ITEMS",
    "COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_HEADER",
    "COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_FOOTER",
    "COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_CHOICES",
    "COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_VALUES",
    "COMUN_CUSTOM_TEMPLATE_FIELD_PLACEMENT_OPTION_ITEMS",
    "COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_TEXT",
    "COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_FILE",
    "COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_SELECT",
    "COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHECKBOX",
    "COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_CHOICES",
    "COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_VALUES",
    "COMUN_CUSTOM_TEMPLATE_FIELD_TYPE_OPTION_ITEMS",
    "POST_TEMPLATE_TYPE_BASIC",
    "POST_TEMPLATE_TYPE_MOVIE_REVIEW",
    "POST_TEMPLATE_TYPE_POST_VOTE_POLL",
    "POST_TEMPLATE_TYPE_MUSIC_RELEASE",
    "POST_TEMPLATE_TYPE_CHOICES",
    "POST_TEMPLATE_TYPE_VALUES",
    "POST_TEMPLATE_EDITOR_BLOCK_CHOICES",
    "POST_TEMPLATE_EDITOR_BLOCK_OPTION_ITEMS",
    "POST_TEMPLATE_EDITOR_BLOCK_VALUES",
    "POST_TEMPLATE_EDITOR_BLOCK_ALL_VALUES",
    "POST_TEMPLATE_EDITOR_BLOCK_BASIC_VALUES",
    "POST_TEMPLATE_EDITOR_BLOCKS_BY_TEMPLATE",
    "ComunCustomPostTemplate",
    "ComunCustomPostTemplateBlock",
    "ComunCustomPostTemplateField",
    "PostTemplateConfig",
    "PostPollVote",
    "PostRatingVote",
    "default_allowed_post_templates",
    "normalize_allowed_post_templates",
    "normalize_allowed_post_templates_override",
    "template_editor_block_choices_for_template",
    "default_enabled_template_editor_blocks",
    "normalize_template_editor_blocks_for_template",
]
