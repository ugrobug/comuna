from __future__ import annotations

import secrets

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.text import get_valid_filename

User = get_user_model()


def film_journey_access_token() -> str:
    return secrets.token_urlsafe(32)


def public_book_final_pdf_path(instance, filename: str) -> str:
    safe_name = get_valid_filename(str(filename or "book.pdf").strip() or "book.pdf")
    return f"special-projects/book/final/{timezone.now():%Y%m%d%H%M%S}-{safe_name}"


class SpecialProjectLetterImage(models.Model):
    project_slug = models.SlugField(max_length=80, default="landname")
    letter = models.CharField(max_length=4)
    title = models.CharField(max_length=160)
    location_name = models.CharField(max_length=220, blank=True)
    image_url = models.URLField(max_length=700, blank=True)
    map_url = models.URLField(max_length=700, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    source_name = models.CharField(max_length=160, blank=True)
    source_url = models.URLField(max_length=700, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=100)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="special_project_letter_images",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Буква спецпроекта"
        verbose_name_plural = "Буквы спецпроекта"
        ordering = ("project_slug", "letter", "sort_order", "id")
        indexes = [
            models.Index(fields=("project_slug", "letter", "is_active")),
            models.Index(fields=("project_slug", "is_active", "sort_order")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.letter}:{self.title}"


class SpecialProjectLetterSuggestion(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = (
        (STATUS_PENDING, "На модерации"),
        (STATUS_APPROVED, "Одобрено"),
        (STATUS_REJECTED, "Отклонено"),
    )

    project_slug = models.SlugField(max_length=80, default="landname")
    letter = models.CharField(max_length=4)
    map_url = models.URLField(max_length=700, blank=True)
    coordinates_text = models.CharField(max_length=120, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_note = models.CharField(max_length=280, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="special_project_letter_suggestions",
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_special_project_letter_suggestions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Предложение буквы спецпроекта"
        verbose_name_plural = "Предложения букв спецпроекта"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("project_slug", "letter", "status")),
            models.Index(fields=("submitted_by", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.letter}:{self.status}:{self.submitted_by_id}"


class SpecialProjectGeneratedPhrase(models.Model):
    project_slug = models.SlugField(max_length=80, default="landname")
    text = models.CharField(max_length=64)
    share_query = models.CharField(max_length=64)
    generated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="special_project_generated_phrases",
    )
    was_shared = models.BooleanField(default=False)
    share_clicks = models.PositiveIntegerField(default=0)
    shared_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Сгенерированная фраза спецпроекта"
        verbose_name_plural = "Сгенерированные фразы спецпроекта"
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=("project_slug", "created_at")),
            models.Index(fields=("project_slug", "was_shared", "created_at")),
            models.Index(fields=("project_slug", "text")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.text}:{self.created_at:%Y-%m-%d %H:%M}"


class PublicBookState(models.Model):
    PROJECT_SLUG = "book"

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG, unique=True)
    total_words = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Состояние книги сообщества"
        verbose_name_plural = "Состояния книги сообщества"

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.total_words}"


class PublicBookWord(models.Model):
    PROJECT_SLUG = PublicBookState.PROJECT_SLUG

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG)
    position = models.PositiveIntegerField()
    word = models.CharField(max_length=30)
    normalized_word = models.CharField(max_length=30)
    is_censored = models.BooleanField(default=False)
    censored_at = models.DateTimeField(null=True, blank=True)
    censored_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="censored_public_book_words",
    )

    class Meta:
        verbose_name = "Слово книги сообщества"
        verbose_name_plural = "Слова книги сообщества"
        ordering = ("project_slug", "position")
        constraints = [
            models.UniqueConstraint(
                fields=("project_slug", "position"),
                name="special_projects_public_book_unique_position",
            ),
        ]
        indexes = [
            models.Index(fields=("project_slug", "position")),
            models.Index(fields=("project_slug", "is_censored")),
            models.Index(fields=("project_slug", "normalized_word")),
        ]

    def __str__(self) -> str:
        return f"{self.position}. {self.word}"


class PublicBookSubmissionState(models.Model):
    PROJECT_SLUG = PublicBookState.PROJECT_SLUG

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="public_book_submission_states",
    )
    words_count = models.PositiveIntegerField(default=0)
    next_available_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Состояние отправок в книгу"
        verbose_name_plural = "Состояния отправок в книгу"
        ordering = ("project_slug", "user_id")
        constraints = [
            models.UniqueConstraint(
                fields=("project_slug", "user"),
                name="special_projects_public_book_unique_submission_state",
            ),
        ]
        indexes = [
            models.Index(fields=("project_slug", "next_available_at")),
            models.Index(fields=("user", "next_available_at")),
            models.Index(fields=("project_slug", "words_count")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.user_id}:{self.words_count}"


class PublicBookProjectSettings(models.Model):
    PROJECT_SLUG = PublicBookState.PROJECT_SLUG

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG, unique=True)
    rules_text = models.TextField(blank=True)
    final_pdf = models.FileField(upload_to=public_book_final_pdf_path, blank=True)
    final_pdf_uploaded_at = models.DateTimeField(null=True, blank=True)
    final_pdf_announced_at = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_public_book_settings",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройки книги сообщества"
        verbose_name_plural = "Настройки книги сообщества"

    def __str__(self) -> str:
        return self.project_slug


class PublicBookReminder(models.Model):
    PROJECT_SLUG = PublicBookState.PROJECT_SLUG

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="public_book_reminders",
    )
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Напоминание книги сообщества"
        verbose_name_plural = "Напоминания книги сообщества"
        ordering = ("scheduled_at", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("project_slug", "user", "scheduled_at"),
                name="special_projects_public_book_unique_reminder",
            ),
        ]
        indexes = [
            models.Index(fields=("project_slug", "sent_at", "scheduled_at")),
            models.Index(fields=("user", "sent_at", "scheduled_at")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.user_id}:{self.scheduled_at:%Y-%m-%d %H:%M}"


class PublicBookFinalNotificationSubscription(models.Model):
    PROJECT_SLUG = PublicBookState.PROJECT_SLUG

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="public_book_final_subscriptions",
    )
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Подписка на финальную книгу"
        verbose_name_plural = "Подписки на финальную книгу"
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("project_slug", "user"),
                name="special_projects_public_book_unique_final_subscription",
            ),
        ]
        indexes = [
            models.Index(fields=("project_slug", "notified_at", "created_at")),
            models.Index(fields=("user", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.user_id}"


class PublicBookBlockedWord(models.Model):
    PROJECT_SLUG = PublicBookState.PROJECT_SLUG

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG)
    word = models.CharField(max_length=64)
    normalized_word = models.CharField(max_length=64)
    is_active = models.BooleanField(default=True)
    note = models.CharField(max_length=240, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="public_book_blocked_words",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Запрещенное слово книги"
        verbose_name_plural = "Запрещенные слова книги"
        ordering = ("project_slug", "normalized_word")
        constraints = [
            models.UniqueConstraint(
                fields=("project_slug", "normalized_word"),
                name="special_projects_public_book_unique_blocked_word",
            ),
        ]
        indexes = [
            models.Index(fields=("project_slug", "is_active", "normalized_word")),
        ]

    def save(self, *args, **kwargs) -> None:
        from special_projects.public_book import normalize_public_book_moderation_text

        self.word = str(self.word or "").strip()
        normalized_word = normalize_public_book_moderation_text(self.word)
        if not normalized_word:
            raise ValueError("Запрещенное выражение должно содержать буквы или цифры.")
        self.normalized_word = normalized_word[:64]
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.word


class PublicBookModerationState(models.Model):
    PROJECT_SLUG = PublicBookState.PROJECT_SLUG

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="public_book_moderation_states",
    )
    consecutive_violations = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_violation_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Состояние модерации книги"
        verbose_name_plural = "Состояния модерации книги"
        ordering = ("project_slug", "user_id")
        constraints = [
            models.UniqueConstraint(
                fields=("project_slug", "user"),
                name="special_projects_public_book_unique_moderation_user",
            ),
        ]
        indexes = [
            models.Index(fields=("project_slug", "locked_until")),
            models.Index(fields=("user", "locked_until")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.user_id}:{self.consecutive_violations}"


class FilmJourneyFilm(models.Model):
    PROJECT_SLUG = "1001-films"

    project_slug = models.SlugField(max_length=80, default=PROJECT_SLUG)
    title = models.CharField(max_length=220)
    original_title = models.CharField(max_length=220, blank=True)
    year = models.PositiveSmallIntegerField(null=True, blank=True)
    category = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    imdb_url = models.URLField(max_length=700, blank=True)
    imdb_rating = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    poster_url = models.URLField(max_length=700, blank=True)
    runtime_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    director = models.CharField(max_length=220, blank=True)
    country = models.CharField(max_length=160, blank=True)
    genres = models.CharField(max_length=240, blank=True)
    sort_order = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Фильм спецпроекта 365"
        verbose_name_plural = "Фильмы спецпроекта 365"
        ordering = ("project_slug", "sort_order", "id")
        indexes = [
            models.Index(fields=("project_slug", "is_active", "sort_order")),
            models.Index(fields=("project_slug", "title")),
            models.Index(fields=("project_slug", "original_title")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("project_slug", "sort_order"),
                name="special_projects_film_journey_unique_order",
            ),
        ]

    def __str__(self) -> str:
        label = self.title
        if self.year:
            label = f"{label} ({self.year})"
        return f"{self.sort_order}. {label}"


class FilmJourneySubscription(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_COMPLETED = "completed"
    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Активна"),
        (STATUS_PAUSED, "Пауза"),
        (STATUS_COMPLETED, "Завершена"),
    )

    project_slug = models.SlugField(max_length=80, default=FilmJourneyFilm.PROJECT_SLUG)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="film_journey_subscriptions",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    started_at = models.DateTimeField(default=timezone.now)
    next_delivery_at = models.DateTimeField()
    last_delivered_at = models.DateTimeField(null=True, blank=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    pause_reason = models.CharField(max_length=160, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Подписка на спецпроект 365"
        verbose_name_plural = "Подписки на спецпроект 365"
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("project_slug", "user"),
                name="special_projects_film_journey_unique_user",
            ),
        ]
        indexes = [
            models.Index(fields=("project_slug", "status", "next_delivery_at")),
            models.Index(fields=("user", "status")),
        ]

    def __str__(self) -> str:
        return f"{self.project_slug}:{self.user_id}:{self.status}"


class FilmJourneyEntry(models.Model):
    subscription = models.ForeignKey(
        FilmJourneySubscription,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    film = models.ForeignKey(
        FilmJourneyFilm,
        on_delete=models.PROTECT,
        related_name="journey_entries",
    )
    position = models.PositiveIntegerField()
    access_token = models.CharField(max_length=96, unique=True, default=film_journey_access_token)
    available_at = models.DateTimeField(default=timezone.now)
    notification_sent_at = models.DateTimeField(null=True, blank=True)
    first_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    second_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    comment = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Выдача фильма спецпроекта 365"
        verbose_name_plural = "Выдачи фильмов спецпроекта 365"
        ordering = ("subscription", "position")
        constraints = [
            models.UniqueConstraint(
                fields=("subscription", "position"),
                name="special_projects_film_journey_unique_position",
            ),
            models.UniqueConstraint(
                fields=("subscription", "film"),
                name="special_projects_film_journey_unique_film",
            ),
        ]
        indexes = [
            models.Index(fields=("access_token",)),
            models.Index(fields=("subscription", "completed_at")),
            models.Index(fields=("available_at", "notification_sent_at")),
        ]

    def __str__(self) -> str:
        return f"{self.subscription_id}:{self.position}:{self.film_id}"
