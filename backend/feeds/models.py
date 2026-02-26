from __future__ import annotations

from io import BytesIO
import random
import os
import re
import inspect
try:
    import pymorphy2
except ImportError:  # optional dependency for lemmatization
    pymorphy2 = None

from django.db import models
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

User = get_user_model()

_MORPH_ANALYZER = None


def default_post_fake_views_target() -> int:
    return random.randint(30, 400)


def _ensure_pymorphy2_compat():
    if pymorphy2 is None:
        return
    if not hasattr(inspect, "getargspec"):
        from collections import namedtuple
        ArgSpec = namedtuple("ArgSpec", "args varargs keywords defaults")

        def getargspec(func):  # type: ignore
            spec = inspect.getfullargspec(func)
            return ArgSpec(spec.args, spec.varargs, spec.varkw, spec.defaults)
        inspect.getargspec = getargspec  # type: ignore[attr-defined]


def _get_morph_analyzer():
    global _MORPH_ANALYZER
    if pymorphy2 is None:
        return None
    if _MORPH_ANALYZER is None:
        _ensure_pymorphy2_compat()
        try:
            _MORPH_ANALYZER = pymorphy2.MorphAnalyzer()
        except Exception:
            _MORPH_ANALYZER = None
    return _MORPH_ANALYZER


def _lemmatize_tag(value: str) -> str:
    morph = _get_morph_analyzer()
    if not morph:
        return ""
    text = re.sub(r"\s+", " ", value).strip().lower()
    if not text:
        return ""
    words = text.split()
    lemmas: list[str] = []
    for word in words:
        parts = [part for part in word.split("-") if part]
        if not parts:
            continue
        lemma_parts: list[str] = []
        for part in parts:
            parsed = morph.parse(part)
            if parsed:
                lemma_parts.append(parsed[0].normal_form)
            else:
                lemma_parts.append(part)
        lemmas.append("-".join(lemma_parts))
    return " ".join(lemmas).strip()


class Author(models.Model):
    username = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255, blank=True)
    channel_id = models.BigIntegerField(null=True, blank=True)
    channel_url = models.URLField(max_length=255, blank=True)
    invite_url = models.URLField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=255, blank=True)
    avatar_image = models.ImageField(upload_to="authors/avatars/", blank=True)
    avatar_file_id = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    subscribers_count = models.PositiveIntegerField(default=0)
    rubric = models.ForeignKey(
        "Rubric", on_delete=models.SET_NULL, null=True, blank=True, related_name="authors"
    )
    auto_publish = models.BooleanField(default=True)
    publish_delay_days = models.PositiveSmallIntegerField(default=0)
    notify_comments = models.BooleanField(default=False)
    # Stored reputation points, updated at vote time (so it doesn't change if content is later removed).
    rating_total = models.IntegerField(default=0)
    admin_chat_id = models.BigIntegerField(null=True, blank=True)
    is_blocked = models.BooleanField(default=False)
    shadow_banned = models.BooleanField(default=False)
    force_home = models.BooleanField(default=False)
    first_post_notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.username


class Rubric(models.Model):
    ICON_THUMB_SIZE = (64, 64)

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    icon_url = models.ImageField(upload_to="rubrics/icons/", blank=True)
    icon_thumb = models.ImageField(upload_to="rubrics/icons/thumbs/", blank=True)
    cover_image_url = models.ImageField(upload_to="rubrics/covers/", blank=True)
    description = models.TextField(blank=True)
    subscribe_url = models.URLField(max_length=255, blank=True)
    home_limit = models.PositiveIntegerField(default=3)
    hide_from_home = models.BooleanField(
        default=False,
        verbose_name="Не показывать на главной",
        help_text="Если включено, посты этой рубрики не попадут в ленту «Горячее».",
    )
    is_active = models.BooleanField(default=True)
    is_hidden = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

    def _build_icon_thumb(self) -> tuple[ContentFile, str] | None:
        if not self.icon_url:
            return None
        try:
            self.icon_url.open("rb")
            with Image.open(self.icon_url) as img:
                img = ImageOps.exif_transpose(img)
                resample = getattr(Image, "Resampling", Image).LANCZOS
                img = ImageOps.fit(img, self.ICON_THUMB_SIZE, resample)
                has_alpha = img.mode in ("RGBA", "LA") or (
                    img.mode == "P" and "transparency" in img.info
                )
                if has_alpha:
                    img = img.convert("RGBA")
                    fmt = "PNG"
                    ext = "png"
                    save_kwargs = {"optimize": True}
                else:
                    img = img.convert("RGB")
                    fmt = "JPEG"
                    ext = "jpg"
                    save_kwargs = {"quality": 85, "optimize": True}
                buffer = BytesIO()
                img.save(buffer, fmt, **save_kwargs)
                return ContentFile(buffer.getvalue()), ext
        except Exception:
            return None
        finally:
            try:
                self.icon_url.close()
            except Exception:
                pass

    def _generate_icon_thumb(self) -> None:
        result = self._build_icon_thumb()
        if not result:
            return
        content, ext = result
        base = os.path.splitext(os.path.basename(self.icon_url.name or ""))[0] or f"rubric_{self.pk}"
        filename = f"{base}_64x64.{ext}"
        if self.icon_thumb:
            self.icon_thumb.delete(save=False)
        self.icon_thumb.save(filename, content, save=False)
        self._skip_icon_thumb = True
        super().save(update_fields=["icon_thumb"])
        self._skip_icon_thumb = False

    def save(self, *args, **kwargs) -> None:
        if getattr(self, "_skip_icon_thumb", False):
            super().save(*args, **kwargs)
            return

        icon_changed = False
        if self.pk:
            previous = Rubric.objects.filter(pk=self.pk).only("icon_url").first()
            if previous and previous.icon_url.name != self.icon_url.name:
                icon_changed = True
        else:
            icon_changed = bool(self.icon_url)

        super().save(*args, **kwargs)

        if self.icon_url:
            if icon_changed or not self.icon_thumb:
                self._generate_icon_thumb()
        elif self.icon_thumb:
            self.icon_thumb.delete(save=False)
            self._skip_icon_thumb = True
            super().save(update_fields=["icon_thumb"])
            self._skip_icon_thumb = False


class TagRelationType(models.Model):
    name = models.CharField(max_length=64, unique=True)
    is_bidirectional = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Tag(models.Model):
    MOOD_NEUTRAL = "neutral"
    MOOD_SERIOUS = "serious"
    MOOD_FUNNY = "funny"
    MOOD_SAD = "sad"
    MOOD_CHOICES = (
        (MOOD_NEUTRAL, "Нейтральный"),
        (MOOD_SERIOUS, "Серьезный"),
        (MOOD_FUNNY, "Веселый"),
        (MOOD_SAD, "Грустный"),
    )

    name = models.CharField(max_length=64, unique=True)
    mood = models.CharField(
        max_length=16, choices=MOOD_CHOICES, default=MOOD_NEUTRAL
    )
    lemma = models.CharField(max_length=128, blank=True)
    is_active = models.BooleanField(default=True)
    hide_from_home = models.BooleanField(
        default=False,
        verbose_name="Не показывать на главной",
        help_text="Если включено, посты с этим тегом не попадут в ленту «Горячее».",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        if not self.lemma and self.name:
            self.lemma = _lemmatize_tag(self.name)
        super().save(*args, **kwargs)


class TagRelation(models.Model):
    from_tag = models.ForeignKey(
        Tag, on_delete=models.CASCADE, related_name="relations"
    )
    to_tag = models.ForeignKey(
        Tag, on_delete=models.CASCADE, related_name="related_to"
    )
    relation_type = models.ForeignKey(
        "feeds.TagRelationType",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="relations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["from_tag__name", "to_tag__name"]

    def __str__(self) -> str:
        relation = self.relation_type.name if self.relation_type else "без типа"
        return f"{self.from_tag.name} → {self.to_tag.name} ({relation})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if getattr(self, "_skip_bidirectional", False):
            return
        if self.relation_type and self.relation_type.is_bidirectional:
            reverse = TagRelation.objects.filter(
                from_tag=self.to_tag,
                to_tag=self.from_tag,
            ).first()
            if reverse:
                if reverse.relation_type_id != self.relation_type_id:
                    TagRelation.objects.filter(pk=reverse.pk).update(
                        relation_type=self.relation_type
                    )
            else:
                reverse = TagRelation(
                    from_tag=self.to_tag,
                    to_tag=self.from_tag,
                    relation_type=self.relation_type,
                )
                reverse._skip_bidirectional = True
                reverse.save()

    def delete(self, *args, **kwargs):
        if not getattr(self, "_skip_bidirectional", False):
            if self.relation_type and self.relation_type.is_bidirectional:
                TagRelation.objects.filter(
                    from_tag=self.to_tag,
                    to_tag=self.from_tag,
                    relation_type=self.relation_type,
                ).delete()
        super().delete(*args, **kwargs)


class ThematicFeed(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    moderators = models.ManyToManyField(
        User,
        blank=True,
        related_name="thematic_feed_moderation",
        help_text="Пользователи, которые могут редактировать состав папки.",
    )
    authors = models.ManyToManyField(
        Author,
        blank=True,
        related_name="thematic_feeds",
        help_text="Авторы, посты которых будут показаны в тематической ленте.",
    )
    excluded_authors = models.ManyToManyField(
        Author,
        blank=True,
        related_name="thematic_feeds_excluded",
        help_text="Авторы, посты которых будут исключены из папки.",
    )
    rubrics = models.ManyToManyField(
        "Rubric",
        blank=True,
        related_name="thematic_feeds_included",
        verbose_name="Рубрики",
        help_text="Посты этих рубрик будут добавляться в папку.",
    )
    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="thematic_feeds_included",
        verbose_name="Теги",
        help_text="Посты с этими тегами будут добавляться в папку.",
    )
    blocked_tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="thematic_feeds_blocked",
        verbose_name="Исключенные теги",
        help_text="Посты с этими тегами будут скрыты в папке.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Папка"
        verbose_name_plural = "Папки"

    def __str__(self) -> str:
        return self.name


class ComunCategory(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Категория комуны"
        verbose_name_plural = "Категории коммун"

    def __str__(self) -> str:
        return self.name


class Comun(models.Model):
    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_comuns",
        verbose_name="Создатель",
    )
    moderators = models.ManyToManyField(
        User,
        blank=True,
        related_name="moderated_comuns",
        verbose_name="Модераторы",
        help_text="Пользователи, которые могут редактировать карточку комуны и категоризировать посты.",
    )
    product_tag = models.ForeignKey(
        Tag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="comuns",
        verbose_name="Тег продукта",
        help_text="Все посты с этим тегом попадут в коммуну.",
    )
    welcome_post = models.ForeignKey(
        "Post",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="welcome_for_comuns",
        verbose_name="Приветственный пост",
    )
    categories = models.ManyToManyField(
        ComunCategory,
        blank=True,
        related_name="comuns",
        verbose_name="Внутренние категории",
    )
    website_url = models.URLField(max_length=500, blank=True, verbose_name="Веб-сайт")
    logo_url = models.URLField(max_length=500, blank=True, verbose_name="Логотип (URL)")
    product_description = models.TextField(blank=True, verbose_name="Описание продукта")
    target_audience = models.TextField(blank=True, verbose_name="Целевая аудитория")
    hide_from_home = models.BooleanField(
        default=False,
        verbose_name="Не показывать на главной",
        help_text="Посты, созданные внутри этой комуны, не будут попадать в Горячее.",
    )
    hide_from_fresh = models.BooleanField(
        default=False,
        verbose_name="Не показывать в свежем",
        help_text="Посты, созданные внутри этой комуны, не будут попадать в ленту Свежее.",
    )
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Комуна"
        verbose_name_plural = "Комуны"

    def __str__(self) -> str:
        return self.name


class Post(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="posts")
    message_id = models.BigIntegerField()
    media_group_id = models.CharField(max_length=128, blank=True)
    title = models.CharField(max_length=255, blank=True)
    rubric = models.ForeignKey(
        Rubric, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    content = models.TextField(blank=True)
    rating = models.IntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
    fake_views_target = models.PositiveIntegerField(default=default_post_fake_views_target)
    real_views_count = models.PositiveIntegerField(default=0)
    source_url = models.URLField(max_length=255, blank=True)
    channel_url = models.URLField(max_length=255, blank=True)
    is_pending = models.BooleanField(default=False)
    is_blocked = models.BooleanField(default=False)
    publish_at = models.DateTimeField(null=True, blank=True)
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("author", "message_id")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.author.username}:{self.message_id}"


class ComunPostCategoryAssignment(models.Model):
    comun = models.ForeignKey(
        Comun, on_delete=models.CASCADE, related_name="post_category_assignments"
    )
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="comun_category_assignments"
    )
    category = models.ForeignKey(
        ComunCategory,
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
        unique_together = ("comun", "post")
        verbose_name = "Категория поста в комуне"
        verbose_name_plural = "Категории постов в коммунах"

    def __str__(self) -> str:
        return f"{self.comun_id}:{self.post_id}:{self.category_id or 0}"


class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_comments")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.TextField()
    persona_key = models.CharField(max_length=64, blank=True, default="")
    persona_username = models.CharField(max_length=150, blank=True, default="")
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class PostCommentLike(models.Model):
    comment = models.ForeignKey(PostComment, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comment_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("comment", "user")

    def __str__(self) -> str:
        return f"{self.comment_id}:{self.user_id}"


class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_likes")
    value = models.SmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class PostPollVote(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="poll_votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_poll_votes")
    selected_options = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("post", "user")

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class PostRead(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_reads")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class PostFavorite(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="favorites")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_favorites")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class BotSession(models.Model):
    telegram_user_id = models.BigIntegerField(unique=True)
    auto_publish = models.BooleanField(default=True)
    publish_delay_days = models.PositiveSmallIntegerField(default=0)
    rubric = models.ForeignKey(
        "Rubric", on_delete=models.SET_NULL, null=True, blank=True, related_name="bot_sessions"
    )
    selected_author = models.ForeignKey(
        "Author", on_delete=models.SET_NULL, null=True, blank=True, related_name="bot_sessions"
    )
    invite_url = models.URLField(max_length=255, blank=True)
    invite_waiting = models.BooleanField(default=False)
    mode_selected = models.BooleanField(default=False)
    instructions_sent = models.BooleanField(default=False)
    pending_update_post_id = models.IntegerField(null=True, blank=True)
    pending_update_message = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return str(self.telegram_user_id)


class AuthorAdmin(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="author_links")
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="admin_links")
    telegram_user_id = models.BigIntegerField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "author")

    def __str__(self) -> str:
        return f"{self.user_id}:{self.author_id}"


class AuthorVerificationCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="author_codes")
    code = models.CharField(max_length=64, unique=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"{self.user_id}:{self.code}"


class TelegramAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="telegram_account")
    telegram_id = models.BigIntegerField(unique=True)
    username = models.CharField(max_length=255, blank=True)
    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"telegram:{self.telegram_id}"


class VkAccount(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="vk_account")
    vk_id = models.BigIntegerField(unique=True)
    username = models.CharField(blank=True, max_length=255)
    first_name = models.CharField(blank=True, max_length=255)
    last_name = models.CharField(blank=True, max_length=255)
    avatar_url = models.URLField(blank=True, max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"vk:{self.vk_id}"


class SiteUserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="site_profile")
    display_name = models.CharField(max_length=120, blank=True)
    avatar_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Профиль пользователя сайта"
        verbose_name_plural = "Профили пользователей сайта"

    def __str__(self) -> str:
        return f"site-profile:{self.user_id}"
