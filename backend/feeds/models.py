from __future__ import annotations

import json
import random
import re
import inspect
import urllib.error
import urllib.parse
import urllib.request
try:
    import pymorphy2
except ImportError:  # optional dependency for lemmatization
    pymorphy2 = None

from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from editor.models import (
    POST_TEMPLATE_TYPE_BASIC,
    POST_TEMPLATE_TYPE_CHOICES,
    POST_TEMPLATE_TYPE_MOVIE_REVIEW,
    POST_TEMPLATE_TYPE_MUSIC_RELEASE,
    POST_TEMPLATE_TYPE_POST_VOTE_POLL,
    default_allowed_post_templates,
    default_enabled_template_editor_blocks,
    normalize_allowed_post_templates_override,
    normalize_template_editor_blocks_for_template,
    template_editor_block_choices_for_template,
)

User = get_user_model()

_MORPH_ANALYZER = None


def _send_bot_message_to_chat(chat_id: int, text: str) -> None:
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    if not token:
        return
    payload = urllib.parse.urlencode(
        {"chat_id": str(chat_id), "text": str(text or "").strip()[:4096]}
    ).encode("utf-8")
    if not payload:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        request = urllib.request.Request(url, data=payload, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            json.loads(response.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, ValueError):
        return
    except Exception:
        return

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

    class Meta:
        indexes = [
            models.Index(fields=["is_blocked", "shadow_banned", "force_home"], name="author_home_flags_idx"),
            models.Index(fields=["-rating_total"], name="author_rating_idx"),
        ]

    def __str__(self) -> str:
        return self.username

    def _send_blocked_notification(self) -> None:
        if not self.admin_chat_id:
            return
        channel_name = (self.title or "").strip() or f"@{self.username}"
        text = (
            f"Ваш канал {channel_name} заблокирован для кросс-постинга на сайте Тамбур. "
            "Обычно это происходит из-за низкой ценности контента для пользователей: "
            "сплошная реклама без дополнительной ценности, сгенерированный или ИИ "
            "контент, а также из-за нарушений правил сайта."
        )
        _send_bot_message_to_chat(int(self.admin_chat_id), text)

    def save(self, *args, **kwargs) -> None:
        should_notify_blocked = False
        if self.pk:
            previous = Author.objects.filter(pk=self.pk).only("is_blocked").first()
            if previous and not previous.is_blocked and self.is_blocked:
                should_notify_blocked = True
        super().save(*args, **kwargs)
        if should_notify_blocked:
            self._send_blocked_notification()


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
        indexes = [
            models.Index(fields=["hide_from_home"], name="tag_hide_home_idx"),
        ]

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


class StaticPageContent(models.Model):
    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=160)
    content = models.TextField(blank=True)
    updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_static_pages",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["slug"]
        verbose_name = "Контент страницы"
        verbose_name_plural = "Контент страниц"

    def __str__(self) -> str:
        return self.slug


class Post(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="posts")
    message_id = models.BigIntegerField()
    media_group_id = models.CharField(max_length=128, blank=True)
    title = models.CharField(max_length=255, blank=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    content = models.TextField(blank=True)
    preview_content = models.TextField(blank=True)
    preview_image_url = models.TextField(blank=True)
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
        indexes = [
            models.Index(fields=["is_blocked", "is_pending", "-created_at"], name="post_public_created_idx"),
            models.Index(fields=["author", "is_blocked", "is_pending", "-created_at"], name="post_author_created_idx"),
            models.Index(fields=["publish_at", "-created_at"], name="post_publish_created_idx"),
            models.Index(fields=["-rating", "-created_at"], name="post_rating_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.author.username}:{self.message_id}"

    @property
    def display_views_target(self) -> int:
        return self.fake_views_target

    @display_views_target.setter
    def display_views_target(self, value: int) -> None:
        self.fake_views_target = value

    def set_display_views_target(self, value: int, *, save: bool = False) -> None:
        self.display_views_target = value
        if save:
            self.save(update_fields=["fake_views_target", "updated_at"])

    def save(self, *args, **kwargs) -> None:
        update_fields = kwargs.get("update_fields")
        should_refresh_preview = update_fields is None or bool(
            {"content", "raw_data"} & set(update_fields)
        )
        if should_refresh_preview:
            from feeds.preview import build_post_preview

            preview = build_post_preview(self.content or "", self.raw_data)
            self.preview_content = preview["preview_content"]
            self.preview_image_url = preview["preview_image_url"]
            if update_fields is not None:
                kwargs["update_fields"] = list(
                    set(update_fields) | {"preview_content", "preview_image_url"}
                )
        super().save(*args, **kwargs)


from communities.models import (
    Comun,
    ComunCategory,
    ComunGlossaryTerm,
    ComunPostCategoryAssignment,
    ComunPostRatingContribution,
    ComunVote,
)


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

    class Meta:
        indexes = [
            models.Index(fields=["post", "is_deleted", "created_at"], name="comment_post_created_idx"),
            models.Index(fields=["is_deleted", "-created_at"], name="comment_recent_idx"),
        ]

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


class PostRead(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="reads")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_reads")
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")
        indexes = [
            models.Index(fields=["user", "-read_at"], name="postread_user_recent_idx"),
            models.Index(fields=["user", "post"], name="postread_user_post_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class PostFavorite(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="favorites")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_favorites")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")
        indexes = [
            models.Index(fields=["user", "-created_at"], name="favorite_user_recent_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class PublicFeedItem(models.Model):
    FEED_HOME = "home"
    FEED_CHOICES = (
        (FEED_HOME, "Главная"),
    )

    feed = models.CharField(max_length=32, choices=FEED_CHOICES, default=FEED_HOME)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="public_feed_items")
    rank = models.PositiveIntegerField()
    score = models.IntegerField(default=0)
    post_created_at = models.DateTimeField()
    author_id_snapshot = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["feed", "rank"]
        constraints = [
            models.UniqueConstraint(fields=["feed", "post"], name="feeds_public_feed_unique_post"),
            models.UniqueConstraint(fields=["feed", "rank"], name="feeds_public_feed_unique_rank"),
        ]
        indexes = [
            models.Index(fields=["feed", "rank"], name="pubfeed_feed_rank_idx"),
            models.Index(fields=["feed", "-post_created_at"], name="pubfeed_feed_created_idx"),
            models.Index(fields=["feed", "-score"], name="pubfeed_feed_score_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.feed}:{self.rank}:{self.post_id}"


from users.models import (
    AuthorAdmin,
    AuthorVerificationCode,
    SiteUserProfile,
    VkAccount,
)
