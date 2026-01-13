from __future__ import annotations

from django.db import models
from django.contrib.auth import get_user_model

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
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    icon_url = models.ImageField(upload_to="rubrics/icons/", blank=True)
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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("post", "user")

    def __str__(self) -> str:
        return f"{self.post_id}:{self.user_id}"


class BotSession(models.Model):
    telegram_user_id = models.BigIntegerField(unique=True)
    auto_publish = models.BooleanField(default=True)
    rubric = models.ForeignKey(
        "Rubric", on_delete=models.SET_NULL, null=True, blank=True, related_name="bot_sessions"
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
