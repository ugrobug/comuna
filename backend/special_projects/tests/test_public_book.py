from __future__ import annotations

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from feeds.models import Post, PostComment
from special_projects.public_book import (
    BLOCKED_WORD_WARNING,
    DISCUSSION_AUTHOR_TITLE,
    MAX_WORDS,
    PROJECT_SLUG,
    SOCIAL_IDENTITY_REQUIRED_MESSAGE,
    admin_stats_payload,
    cancel_reminder_for_user,
    censor_admin_selection,
    censor_admin_word,
    ensure_public_book_discussion_post,
    notify_final_pdf_subscribers,
    normalize_public_book_blocked_word_key,
    normalize_public_book_moderation_text,
    normalize_public_book_translit_text,
    normalize_public_book_word,
    project_status_for_user,
    schedule_reminder_for_user,
    send_due_reminders,
    subscribe_final_pdf_notification,
    submit_word,
)
from special_projects.models import (
    PublicBookBlockedWord,
    PublicBookModerationState,
    PublicBookProjectSettings,
    PublicBookReminder,
    PublicBookState,
    PublicBookSubmissionState,
    PublicBookWord,
)
from telegram_integration.models import TelegramAccount
from users.models import SiteUserProfile, VkAccount
from users.service import _issue_token


User = get_user_model()


class PublicBookTests(TestCase):
    def make_user(self, username: str, *, telegram: bool = False, vk: bool = False):
        user = User.objects.create_user(username=username, password="pass")
        if telegram:
            TelegramAccount.objects.create(
                user=user,
                telegram_id=100000 + user.id,
                username=f"{username}_tg",
            )
        if vk:
            VkAccount.objects.create(
                user=user,
                vk_id=200000 + user.id,
                username=f"{username}_vk",
            )
        return user

    def set_book_next_available_at(self, user, value):
        state = PublicBookSubmissionState.objects.get(user=user, project_slug=PROJECT_SLUG)
        state.next_available_at = value
        state.save(update_fields=("next_available_at",))
        return state

    def test_normalize_allows_letters_and_punctuation(self):
        self.assertEqual(
            normalize_public_book_word("Ёлка"),
            {"word": "Ёлка", "normalized_word": "елка"},
        )
        self.assertEqual(
            normalize_public_book_word("слово!"),
            {"word": "слово!", "normalized_word": "слово"},
        )
        self.assertEqual(
            normalize_public_book_word("..."),
            {"word": "...", "normalized_word": ""},
        )

        with self.assertRaisesMessage(ValueError, "одно слово"):
            normalize_public_book_word("два слова")
        with self.assertRaisesMessage(ValueError, "букв и знаков препинания"):
            normalize_public_book_word("слово1")
        with self.assertRaisesMessage(ValueError, "30 символов"):
            normalize_public_book_word("а" * 31)

    def test_moderation_normalization_collapses_obfuscation(self):
        self.assertEqual(
            normalize_public_book_moderation_text("П\u200b.УууT😊ИИИН-Л000Х"),
            "путинлох",
        )
        self.assertEqual(normalize_public_book_translit_text("putin-loh"), "путинлох")
        self.assertEqual(normalize_public_book_blocked_word_key("putin loh"), "путинлох")

    def test_submit_word_rejects_obfuscated_blocked_phrase(self):
        user = self.make_user("obfuscated-book-user", telegram=True)

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(user, "пуууTин-л000х")

        self.assertFalse(PublicBookWord.objects.exists())

    def test_submit_word_rejects_admin_blocked_word_with_latin_and_without_vowels(self):
        user = self.make_user("admin-block-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="путин лох")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(user, "птнлх")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(user, "пyтинлoх")

        self.assertFalse(PublicBookWord.objects.exists())

    def test_submit_word_ignores_too_short_consonant_substring_matches(self):
        user = self.make_user("short-consonant-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="яровая")

        word = submit_word(user, "Первоеслово")

        self.assertEqual(word.word, "Первоеслово")

    def test_submit_word_rejects_translit_blocked_word(self):
        user = self.make_user("translit-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="путин лох")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(user, "putinloh")

        self.assertFalse(PublicBookWord.objects.exists())

    def test_submit_word_rejects_translit_in_previous_word_pair(self):
        first_user = self.make_user("translit-pair-first-book-user", telegram=True)
        second_user = self.make_user("translit-pair-second-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="лох путин")

        submit_word(first_user, "лох")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(second_user, "putin")

        self.assertEqual(PublicBookWord.objects.count(), 1)

    def test_submit_word_rejects_previous_word_pair_from_blocklist(self):
        first_user = self.make_user("pair-first-book-user", telegram=True)
        second_user = self.make_user("pair-second-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="красный флаг")

        first_word = submit_word(first_user, "красный")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(second_user, "флаг")

        self.assertEqual(PublicBookWord.objects.count(), 1)
        self.assertEqual(PublicBookWord.objects.get(), first_word)
        state = PublicBookModerationState.objects.get(user=second_user, project_slug=PROJECT_SLUG)
        self.assertEqual(state.consecutive_violations, 1)

    def test_submit_word_rejects_blocked_word_inside_longer_word(self):
        user = self.make_user("substring-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="убитьпутин")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(user, "убитьпутина")

        self.assertFalse(PublicBookWord.objects.exists())

    def test_submit_word_rejects_blocked_word_inside_previous_word_pair(self):
        first_user = self.make_user("substring-pair-first-book-user", telegram=True)
        second_user = self.make_user("substring-pair-second-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="убитьпутин")

        submit_word(first_user, "убить")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(second_user, "путина")

        self.assertEqual(PublicBookWord.objects.count(), 1)

    def test_submit_word_creates_position_and_updates_status(self):
        user = self.make_user("book-user", telegram=True)

        word = submit_word(user, "сВоБоДа")
        status = project_status_for_user(user)

        self.assertEqual(word.position, 1)
        self.assertEqual(word.word, "сВоБоДа")
        self.assertEqual(word.normalized_word, "свобода")
        self.assertEqual(PublicBookState.objects.get(project_slug=PROJECT_SLUG).total_words, 1)
        submission_state = PublicBookSubmissionState.objects.get(user=user, project_slug=PROJECT_SLUG)
        self.assertEqual(submission_state.words_count, 1)
        self.assertIsNotNone(submission_state.next_available_at)
        self.assertEqual(status["total_words"], 1)
        self.assertIn("30 символов", status["rules_text"])
        self.assertFalse(status["final_pdf"]["available"])
        self.assertFalse(status["final_notification"]["subscribed"])
        self.assertFalse(status["can_submit"])
        self.assertTrue(status["telegram_linked"])
        self.assertTrue(status["has_social_identity"])
        self.assertIsNotNone(status["discussion_post"]["id"])

    def test_submit_word_requires_telegram_or_vk_link(self):
        user = User.objects.create_user(username="email-book-user", password="pass")

        status = project_status_for_user(user)
        self.assertFalse(status["can_submit"])
        self.assertEqual(status["submit_block_reason"], "social_required")

        with self.assertRaisesMessage(ValueError, SOCIAL_IDENTITY_REQUIRED_MESSAGE):
            submit_word(user, "Свобода")

    def test_submit_word_allows_vk_link(self):
        user = self.make_user("vk-book-user", vk=True)

        word = submit_word(user, "Голос")

        self.assertEqual(word.position, 1)
        self.assertEqual(
            PublicBookSubmissionState.objects.get(user=user, project_slug=PROJECT_SLUG).words_count,
            1,
        )

    def test_submit_word_rejects_blocked_word(self):
        user = self.make_user("blocked-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="Запрет")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(user, "запрет")

        self.assertFalse(PublicBookWord.objects.exists())

    def test_blocked_words_lock_user_after_three_consecutive_violations(self):
        user = self.make_user("locked-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="Запрет")

        for _index in range(2):
            with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
                submit_word(user, "запрет")

        state = PublicBookModerationState.objects.get(user=user, project_slug=PROJECT_SLUG)
        self.assertEqual(state.consecutive_violations, 2)
        self.assertIsNone(state.locked_until)

        with self.assertRaisesMessage(ValueError, "заблокирована на 24 часа"):
            submit_word(user, "запрет")

        state.refresh_from_db()
        self.assertEqual(state.consecutive_violations, 3)
        self.assertIsNotNone(state.locked_until)

        status = project_status_for_user(user)
        self.assertFalse(status["can_submit"])
        self.assertEqual(status["submit_block_reason"], "moderation_lock")
        self.assertIsNotNone(status["moderation_locked_until"])

    def test_successful_word_resets_moderation_violations(self):
        user = self.make_user("reset-book-user", telegram=True)
        PublicBookBlockedWord.objects.create(word="Запрет")

        with self.assertRaisesMessage(ValueError, BLOCKED_WORD_WARNING):
            submit_word(user, "запрет")

        submit_word(user, "Свобода")

        state = PublicBookModerationState.objects.get(user=user, project_slug=PROJECT_SLUG)
        self.assertEqual(state.consecutive_violations, 0)
        self.assertIsNone(state.locked_until)

    def test_admin_can_replace_book_word_with_real_censor_blocks(self):
        author = self.make_user("censor-author", telegram=True)
        moderator = User.objects.create_user(username="censor-admin", password="pass", is_staff=True)
        word = submit_word(author, "Свобода")

        censored = censor_admin_word(word.id, moderator)

        self.assertEqual(censored.word, "███████")
        self.assertEqual(censored.normalized_word, "")
        self.assertTrue(censored.is_censored)
        self.assertEqual(censored.censored_by, moderator)

    def test_admin_can_censor_selected_book_fragment(self):
        author = self.make_user("fragment-author", telegram=True)
        moderator = User.objects.create_user(username="fragment-admin", password="pass", is_staff=True)
        word = submit_word(author, "Свобода")

        changed_words = censor_admin_selection(
            [{"word_id": word.id, "start": 1, "end": 4}],
            moderator,
        )

        self.assertEqual(len(changed_words), 1)
        word.refresh_from_db()
        self.assertEqual(word.word, "С███ода")
        self.assertEqual(word.normalized_word, "сода")
        self.assertTrue(word.is_censored)
        self.assertEqual(word.censored_by, moderator)

    def test_selection_censor_api_requires_staff(self):
        author = self.make_user("fragment-api-author", telegram=True)
        user = self.make_user("fragment-api-user", telegram=True)
        moderator = User.objects.create_user(username="fragment-api-admin", password="pass", is_staff=True)
        word = submit_word(author, "Проверка")
        url = reverse("special-book-admin-selection-censor")
        payload = json.dumps({"fragments": [{"word_id": word.id, "start": 0, "end": 3}]})

        response = self.client.post(url, data=payload, content_type="application/json")
        self.assertEqual(response.status_code, 401)

        response = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {_issue_token(user)}",
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            url,
            data=payload,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {_issue_token(moderator)}",
        )
        self.assertEqual(response.status_code, 200)
        word.refresh_from_db()
        self.assertEqual(word.word, "███верка")

    def test_submit_word_rejects_more_than_one_word_per_24_hours(self):
        user = self.make_user("slow-book-user", telegram=True)
        now = timezone.now()
        submit_word(user, "Первое")
        self.set_book_next_available_at(user, now + timedelta(hours=24))

        with patch("special_projects.public_book.timezone.now", return_value=now + timedelta(hours=23)):
            with self.assertRaisesMessage(ValueError, "24 часа"):
                submit_word(user, "Второе")

        with patch("special_projects.public_book.timezone.now", return_value=now + timedelta(hours=25)):
            second = submit_word(user, "Второе")

        self.assertEqual(second.position, 2)

        self.set_book_next_available_at(user, now + timedelta(hours=49))
        with patch("special_projects.public_book.timezone.now", return_value=now + timedelta(hours=48)):
            with self.assertRaisesMessage(ValueError, "24 часа"):
                submit_word(user, "Третье")

        with patch("special_projects.public_book.timezone.now", return_value=now + timedelta(hours=50)):
            third = submit_word(user, "Третье")

        self.assertEqual(third.position, 3)

    def test_staff_user_is_limited_by_24_hour_submission_interval(self):
        user = self.make_user("staff-book-user", telegram=True)
        user.is_staff = True
        user.save(update_fields=("is_staff",))
        now = timezone.now()
        submit_word(user, "Первое")
        self.set_book_next_available_at(user, now + timedelta(hours=24))

        with patch("special_projects.public_book.timezone.now", return_value=now + timedelta(minutes=5)):
            status = project_status_for_user(user)

            with self.assertRaisesMessage(ValueError, "24 часа"):
                submit_word(user, "Второе")

        self.assertFalse(status["can_submit"])
        self.assertEqual(status["submit_block_reason"], "cooldown")
        self.assertIsNotNone(status["next_available_at"])

    def test_superuser_can_submit_without_24_hour_submission_interval(self):
        user = self.make_user("superuser-book-user", telegram=True)
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=("is_staff", "is_superuser"))
        now = timezone.now()
        submit_word(user, "Первое")
        self.set_book_next_available_at(user, now + timedelta(hours=24))

        with patch("special_projects.public_book.timezone.now", return_value=now + timedelta(minutes=5)):
            status = project_status_for_user(user)
            second = submit_word(user, "Второе")

        self.assertTrue(status["can_submit"])
        self.assertEqual(status["submit_block_reason"], "")
        self.assertIsNone(status["next_available_at"])
        self.assertEqual(second.position, 2)

    def test_submit_word_rejects_full_book(self):
        user = self.make_user("late-book-user", telegram=True)
        PublicBookState.objects.create(project_slug=PROJECT_SLUG, total_words=MAX_WORDS)

        with self.assertRaisesMessage(ValueError, "185000"):
            submit_word(user, "Финиш")

    def test_schedule_reminder_requires_telegram(self):
        user = self.make_user("vk-reminder-user", vk=True)
        submit_word(user, "Слово")

        with self.assertRaisesMessage(ValueError, "Telegram"):
            schedule_reminder_for_user(user)

    def test_schedule_reminder_for_latest_word_and_send_due(self):
        user = self.make_user("reminder-book-user", telegram=True)
        now = timezone.now()
        submit_word(user, "Слово")
        expected_at = now + timedelta(hours=1)
        self.set_book_next_available_at(user, expected_at)

        reminder = schedule_reminder_for_user(user)

        self.assertEqual(reminder.scheduled_at, expected_at)
        self.assertEqual(PublicBookReminder.objects.count(), 1)

        with patch("notifications.service.send_site_notification_to_telegram") as send_mock:
            sent = send_due_reminders(now=expected_at + timedelta(minutes=1))

        self.assertEqual(sent, 1)
        self.assertTrue(send_mock.called)
        reminder.refresh_from_db()
        self.assertIsNotNone(reminder.sent_at)
        next_reminder = PublicBookReminder.objects.get(user=user, sent_at__isnull=True)
        self.assertEqual(
            next_reminder.scheduled_at,
            expected_at + timedelta(minutes=1, days=1),
        )

        with patch("notifications.service.send_site_notification_to_telegram") as send_mock:
            sent = send_due_reminders(now=next_reminder.scheduled_at + timedelta(minutes=1))

        self.assertEqual(sent, 1)
        self.assertTrue(send_mock.called)
        self.assertFalse(
            PublicBookReminder.objects.filter(user=user, sent_at__isnull=True).exists()
        )

    def test_reminder_cycle_restarts_after_next_word(self):
        user = self.make_user("restart-reminder-book-user", telegram=True)
        now = timezone.now()
        with patch("special_projects.public_book.timezone.now", return_value=now):
            submit_word(user, "Первое")

        first_reminder = schedule_reminder_for_user(user)
        with patch("notifications.service.send_site_notification_to_telegram"):
            send_due_reminders(now=first_reminder.scheduled_at)
        second_reminder = PublicBookReminder.objects.get(user=user, sent_at__isnull=True)
        with patch("notifications.service.send_site_notification_to_telegram"):
            send_due_reminders(now=second_reminder.scheduled_at)

        self.assertFalse(
            PublicBookReminder.objects.filter(user=user, sent_at__isnull=True).exists()
        )

        second_word_at = second_reminder.scheduled_at + timedelta(hours=1)
        with patch("special_projects.public_book.timezone.now", return_value=second_word_at):
            submit_word(user, "Второе")

        restarted_reminder = PublicBookReminder.objects.get(user=user, sent_at__isnull=True)
        self.assertEqual(
            restarted_reminder.scheduled_at,
            second_word_at + timedelta(hours=24),
        )

    def test_cancel_reminder_removes_pending_reminders(self):
        user = self.make_user("cancel-reminder-book-user", telegram=True)
        now = timezone.now()
        submit_word(user, "Слово")
        self.set_book_next_available_at(user, now + timedelta(hours=1))
        reminder = schedule_reminder_for_user(user)
        reminder.sent_at = now
        reminder.save(update_fields=("sent_at", "updated_at"))
        schedule_reminder_for_user(user)

        deleted = cancel_reminder_for_user(user)

        self.assertEqual(deleted, 2)
        self.assertFalse(PublicBookReminder.objects.filter(user=user).exists())

    def test_send_due_reminders_skips_stale_reminder_after_new_word(self):
        user = self.make_user("stale-reminder-book-user", telegram=True)
        now = timezone.now()
        submit_word(user, "Первое")
        stale_scheduled_at = now - timedelta(hours=1)
        self.set_book_next_available_at(user, stale_scheduled_at)
        stale_reminder = PublicBookReminder.objects.create(
            project_slug=PROJECT_SLUG,
            user=user,
            scheduled_at=stale_scheduled_at,
        )
        second_word = submit_word(user, "Второе")
        self.assertEqual(second_word.position, 2)
        self.set_book_next_available_at(user, now + timedelta(hours=24))

        with patch("notifications.service.send_site_notification_to_telegram") as send_mock:
            sent = send_due_reminders(now=now)

        self.assertEqual(sent, 0)
        self.assertFalse(send_mock.called)
        self.assertFalse(PublicBookReminder.objects.filter(id=stale_reminder.id).exists())
        self.assertTrue(
            PublicBookReminder.objects.filter(
                user=user,
                scheduled_at=now + timedelta(hours=24),
                sent_at__isnull=True,
            ).exists()
        )

    def test_discussion_post_is_public(self):
        post = ensure_public_book_discussion_post()

        self.assertEqual(post.author.title, DISCUSSION_AUTHOR_TITLE)
        self.assertFalse(post.is_pending)
        self.assertFalse(post.is_blocked)
        self.assertEqual(post.raw_data.get("special_project", {}).get("slug"), PROJECT_SLUG)
        self.assertIn("Книга интернет сообщества", post.title)
        self.assertIn(post, Post.objects.filter(is_blocked=False, is_pending=False))

    def test_discussion_comment_links_point_to_book_page(self):
        from feeds.views import _post_public_path, _site_comment_link

        user = self.make_user("book-comment-link-user", telegram=True)
        post = ensure_public_book_discussion_post()
        comment = PostComment.objects.create(post=post, user=user, body="Комментарий")

        self.assertEqual(_post_public_path(post), "/s/book")
        self.assertEqual(_site_comment_link(post), "/s/book#comments")
        self.assertEqual(_site_comment_link(post, comment), f"/s/book#site-comment-{comment.id}")

        detail_response = self.client.get(reverse("post-detail", args=[post.id]))
        self.assertEqual(detail_response.status_code, 410)
        self.assertEqual(detail_response.json()["redirect_url"], "/s/book#comments")

        recent_response = self.client.get(reverse("recent-comments"))
        self.assertEqual(recent_response.status_code, 200)
        recent_comment = recent_response.json()["comments"][0]
        self.assertEqual(recent_comment["id"], comment.id)
        self.assertEqual(recent_comment["link_url"], f"/s/book#site-comment-{comment.id}")

    def test_admin_stats_payload_counts_anonymous_contributors_and_registrations(self):
        users = [
            self.make_user("top-one", telegram=True),
            self.make_user("top-two", telegram=True),
            self.make_user("top-three", telegram=True),
            self.make_user("top-four", telegram=True),
        ]
        position = 1
        for user, count in ((users[0], 4), (users[1], 3), (users[2], 2), (users[3], 1)):
            for index in range(count):
                PublicBookWord.objects.create(
                    project_slug=PROJECT_SLUG,
                    position=position,
                    word=f"Слово{position}",
                    normalized_word=f"слово{position}",
                )
                position += 1
            PublicBookSubmissionState.objects.create(
                project_slug=PROJECT_SLUG,
                user=user,
                words_count=count,
                next_available_at=timezone.now() + timedelta(hours=24),
            )
        SiteUserProfile.objects.create(user=users[0], registration_source=PROJECT_SLUG, registration_path="/s/book")
        SiteUserProfile.objects.create(user=users[1], registration_source=PROJECT_SLUG, registration_path="/s/book")

        stats = admin_stats_payload()

        self.assertEqual(stats["contributors_count"], 4)
        self.assertEqual(stats["total_words"], 10)
        self.assertEqual(stats["average_words_per_user"], 2.5)
        self.assertEqual(stats["registrations_from_page_count"], 2)
        self.assertNotIn("top_three_words", stats)
        self.assertNotIn("top_users", stats)

    def test_final_pdf_subscription_is_notified_after_upload(self):
        user = self.make_user("pdf-book-user", telegram=True)
        subscription = subscribe_final_pdf_notification(user)
        self.assertIsNone(subscription.notified_at)

        settings_obj = PublicBookProjectSettings.objects.create(project_slug=PROJECT_SLUG)
        settings_obj.final_pdf.save("final.pdf", ContentFile(b"%PDF-1.4"), save=True)

        with (
            patch("notifications.service.send_site_notification_to_telegram") as telegram_mock,
            patch("notifications.service.send_site_notification_to_push") as push_mock,
        ):
            sent = notify_final_pdf_subscribers(settings_obj=settings_obj)

        self.assertEqual(sent, 1)
        self.assertTrue(telegram_mock.called)
        self.assertTrue(push_mock.called)
        subscription.refresh_from_db()
        self.assertIsNotNone(subscription.notified_at)

        status = project_status_for_user(user)
        self.assertTrue(status["final_pdf"]["available"])
        self.assertTrue(status["final_notification"]["subscribed"])
