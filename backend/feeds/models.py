from __future__ import annotations

from io import BytesIO
import os

from django.db import models
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

User = get_user_model()


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
    is_active = models.BooleanField(default=True)
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


class Post(models.Model):
    author = models.ForeignKey(Author, on_delete=models.CASCADE, related_name="posts")
    message_id = models.BigIntegerField()
    media_group_id = models.CharField(max_length=128, blank=True)
    title = models.CharField(max_length=255, blank=True)
    rubric = models.ForeignKey(
        Rubric, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts"
    )
    content = models.TextField(blank=True)
    rating = models.IntegerField(default=0)
    comments_count = models.PositiveIntegerField(default=0)
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


class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="post_comments")
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True, related_name="replies"
    )
    body = models.TextField()
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
