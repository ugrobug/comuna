from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from communities.models import Comun
from communities.service import _comun_posts_base_queryset
from feeds.models import Post
from special_projects.film_journey import (
    DISCUSSION_AUTHOR_DESCRIPTION,
    DISCUSSION_AUTHOR_TITLE,
    DISCUSSION_COMUN_SLUG,
    DISCUSSION_RATING_BLOCK_ID,
    PROJECT_TIME_ZONE,
    ensure_film_discussion_post,
    next_delivery_time,
    serialize_entry,
    send_due_deliveries,
    start_subscription,
)
from special_projects.models import FilmJourneyEntry, FilmJourneyFilm, FilmJourneySubscription


User = get_user_model()


class FilmJourneyDeliveryTests(TestCase):
    def test_next_delivery_time_keeps_same_time_before_deadline(self):
        now = datetime(2026, 5, 18, 10, 16, tzinfo=PROJECT_TIME_ZONE)

        result = next_delivery_time(now).astimezone(PROJECT_TIME_ZONE)

        self.assertEqual(result, datetime(2026, 5, 19, 10, 16, tzinfo=PROJECT_TIME_ZONE))

    def test_next_delivery_time_caps_after_deadline_at_18_moscow(self):
        now = datetime(2026, 5, 18, 19, 30, tzinfo=PROJECT_TIME_ZONE)

        result = next_delivery_time(now).astimezone(PROJECT_TIME_ZONE)

        self.assertEqual(result, datetime(2026, 5, 19, 18, 0, tzinfo=PROJECT_TIME_ZONE))

    @patch("special_projects.film_journey.create_user_notification")
    def test_start_subscription_delivers_first_film_immediately(self, notify_mock):
        user = User.objects.create_user(username="film-user", password="pass")
        film = FilmJourneyFilm.objects.create(
            title="Первый фильм",
            sort_order=1,
            is_active=True,
        )
        now = datetime(2026, 5, 18, 19, 30, tzinfo=PROJECT_TIME_ZONE)

        with patch("special_projects.film_journey.timezone.now", return_value=now):
            subscription = start_subscription(user)

        entry = subscription.entries.get()
        subscription.refresh_from_db()
        self.assertEqual(entry.film, film)
        self.assertEqual(entry.position, 1)
        self.assertEqual(entry.available_at, now)
        self.assertEqual(entry.notification_sent_at, now)
        self.assertEqual(subscription.last_delivered_at, now)
        self.assertEqual(
            subscription.next_delivery_at.astimezone(PROJECT_TIME_ZONE),
            datetime(2026, 5, 19, 18, 0, tzinfo=PROJECT_TIME_ZONE),
        )
        notify_mock.assert_called_once()

    def test_discussion_post_is_public_comun_post_with_movie_review_template(self):
        comun = Comun.objects.create(
            name="После титров",
            slug=DISCUSSION_COMUN_SLUG,
            is_active=True,
        )
        film = FilmJourneyFilm.objects.create(
            title="Первый фильм",
            original_title="First Movie",
            year=1977,
            description="Описание из списка.",
            imdb_url="https://www.imdb.com/title/tt0000001/",
            poster_url="https://example.com/poster.jpg",
            genres="drama",
            sort_order=1,
            is_active=True,
        )

        post = ensure_film_discussion_post(film)

        self.assertEqual(post.title, 'Как вам фильм "Первый фильм" 1977 года?')
        self.assertEqual(post.author.title, DISCUSSION_AUTHOR_TITLE)
        self.assertEqual(post.author.description, DISCUSSION_AUTHOR_DESCRIPTION)
        self.assertFalse(post.is_pending)
        self.assertFalse(post.is_blocked)
        self.assertIsNone(post.publish_at)
        self.assertEqual(post.raw_data.get("source"), "manual_comun")
        self.assertEqual(post.raw_data.get("comun_slug"), DISCUSSION_COMUN_SLUG)
        self.assertEqual(post.raw_data.get("special_project", {}).get("film_id"), film.id)
        self.assertEqual(post.raw_data.get("template", {}).get("type"), "movie_review")
        self.assertEqual(
            post.raw_data.get("template", {}).get("data", {}).get("poster_url"),
            "https://example.com/poster.jpg",
        )
        self.assertIn("Описание из списка.", post.content)
        self.assertIn(DISCUSSION_RATING_BLOCK_ID, post.content)
        self.assertIn(post, list(_comun_posts_base_queryset(comun)))

    @patch("special_projects.film_journey.create_user_notification")
    def test_start_subscription_creates_discussion_post_for_delivered_film(self, notify_mock):
        Comun.objects.create(
            name="После титров",
            slug=DISCUSSION_COMUN_SLUG,
            is_active=True,
        )
        user = User.objects.create_user(username="film-user-with-discussion", password="pass")
        film = FilmJourneyFilm.objects.create(
            title="Фильм дня",
            sort_order=1,
            is_active=True,
        )

        start_subscription(user)

        post = Post.objects.get(raw_data__special_project__film_id=film.id)
        self.assertEqual(post.title, 'Как вам фильм "Фильм дня"?')
        self.assertFalse(post.is_pending)
        notify_mock.assert_called_once()

    def test_entry_serialization_does_not_create_discussion_post(self):
        user = User.objects.create_user(username="film-user-preview", password="pass")
        film = FilmJourneyFilm.objects.create(
            title="Фильм для предпросмотра",
            sort_order=1,
            is_active=True,
        )
        subscription = FilmJourneySubscription.objects.create(
            project_slug=FilmJourneyFilm.PROJECT_SLUG,
            user=user,
            status=FilmJourneySubscription.STATUS_ACTIVE,
            next_delivery_at=datetime(2026, 5, 19, 12, 0, tzinfo=PROJECT_TIME_ZONE),
        )
        entry = FilmJourneyEntry.objects.create(
            subscription=subscription,
            film=film,
            position=1,
            available_at=datetime(2026, 5, 19, 12, 0, tzinfo=PROJECT_TIME_ZONE),
        )

        payload = serialize_entry(entry, include_film=True, include_discussion=True, user=user)

        self.assertIsNone(payload["discussion_post"])
        self.assertFalse(Post.objects.filter(raw_data__special_project__film_id=film.id).exists())

    @patch("special_projects.film_journey.create_user_notification")
    def test_due_deliveries_sends_first_film_for_active_subscription_without_entries(self, notify_mock):
        user = User.objects.create_user(username="film-user-no-entry", password="pass")
        film = FilmJourneyFilm.objects.create(
            title="Первый фильм без выдачи",
            sort_order=1,
            is_active=True,
        )
        now = datetime(2026, 5, 19, 12, 0, tzinfo=PROJECT_TIME_ZONE)
        future = datetime(2026, 5, 20, 12, 0, tzinfo=PROJECT_TIME_ZONE)
        subscription = FilmJourneySubscription.objects.create(
            project_slug=FilmJourneyFilm.PROJECT_SLUG,
            user=user,
            status=FilmJourneySubscription.STATUS_ACTIVE,
            started_at=now,
            next_delivery_at=future,
        )

        with patch("special_projects.film_journey.timezone.now", return_value=now):
            result = send_due_deliveries()

        entry = subscription.entries.get()
        subscription.refresh_from_db()
        self.assertEqual(result.delivered, 1)
        self.assertEqual(entry.film, film)
        self.assertEqual(entry.position, 1)
        self.assertEqual(subscription.last_delivered_at, now)
        notify_mock.assert_called_once()
        self.assertTrue(notify_mock.call_args.kwargs.get("force_telegram"))
