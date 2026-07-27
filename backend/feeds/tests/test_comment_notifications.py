from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from feeds.models import Author, Post, PostComment
from feeds.views import (
    _maybe_notify_author_comment,
    _maybe_notify_comment_reply,
    _maybe_notify_post_comment,
)
from notifications.models import SiteNotification, SiteNotificationPreference
from telegram_integration.models import TelegramAccount
from users.models import AuthorAdmin

User = get_user_model()


class CommentNotificationTests(TestCase):
    def _user(self, username: str):
        return User.objects.create_user(username=username, password="password")

    def _author_with_owner(self, owner, username: str = "channel") -> Author:
        author = Author.objects.create(username=username, title=username)
        AuthorAdmin.objects.create(
            user=owner,
            author=author,
            verified_at=timezone.now(),
        )
        return author

    def _post(self, author: Author, message_id: int = 1) -> Post:
        return Post.objects.create(
            author=author,
            message_id=message_id,
            title="Тестовый пост",
        )

    def _site_only_preferences(self, user, *event_keys: str) -> None:
        for event_key in event_keys:
            SiteNotificationPreference.objects.create(
                user=user,
                event_key=event_key,
                site_enabled=True,
                telegram_enabled=False,
                push_enabled=False,
            )

    def test_reply_to_post_author_comment_creates_only_reply_notification(self):
        owner = self._user("owner")
        commenter = self._user("commenter")
        self._site_only_preferences(owner, "post_comment", "comment_reply")
        author = self._author_with_owner(owner)
        post = self._post(author)
        parent = PostComment.objects.create(post=post, user=owner, body="Parent")
        reply = PostComment.objects.create(
            post=post,
            user=commenter,
            parent=parent,
            body="Reply",
        )

        _maybe_notify_post_comment(post, reply, parent=parent)
        _maybe_notify_comment_reply(post, parent, reply)

        notifications = list(SiteNotification.objects.filter(user=owner))
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].event_key, "comment_reply")

    def test_reply_to_other_user_comment_still_notifies_post_author_and_parent_author(self):
        owner = self._user("owner")
        parent_author = self._user("parent_author")
        commenter = self._user("commenter")
        self._site_only_preferences(owner, "post_comment")
        self._site_only_preferences(parent_author, "comment_reply")
        author = self._author_with_owner(owner)
        post = self._post(author)
        parent = PostComment.objects.create(post=post, user=parent_author, body="Parent")
        reply = PostComment.objects.create(
            post=post,
            user=commenter,
            parent=parent,
            body="Reply",
        )

        _maybe_notify_post_comment(post, reply, parent=parent)
        _maybe_notify_comment_reply(post, parent, reply)

        owner_events = list(
            SiteNotification.objects.filter(user=owner).values_list("event_key", flat=True)
        )
        parent_events = list(
            SiteNotification.objects.filter(user=parent_author).values_list(
                "event_key",
                flat=True,
            )
        )
        self.assertEqual(owner_events, ["post_comment"])
        self.assertEqual(parent_events, ["comment_reply"])

    def test_comment_sends_only_site_telegram_notification_to_same_chat(self):
        owner = self._user("owner")
        commenter = self._user("commenter")
        author = self._author_with_owner(owner)
        author.notify_comments = True
        author.admin_chat_id = 12345
        author.save(update_fields=["notify_comments", "admin_chat_id"])
        TelegramAccount.objects.create(user=owner, telegram_id=12345)
        SiteNotificationPreference.objects.create(
            user=owner,
            event_key="post_comment",
            site_enabled=True,
            telegram_enabled=True,
            push_enabled=False,
        )
        post = self._post(author)
        comment = PostComment.objects.create(
            post=post,
            user=commenter,
            body="Comment",
        )

        def mark_telegram_delivered(notification):
            notification.telegram_sent_at = timezone.now()

        with (
            patch(
                "notifications.service.send_site_notification_to_telegram",
                side_effect=mark_telegram_delivered,
            ) as site_telegram,
            patch("feeds.views.telegram_bot._send_bot_message") as direct_telegram,
        ):
            notified_chat_ids = _maybe_notify_post_comment(post, comment)
            _maybe_notify_author_comment(
                post,
                comment,
                excluded_telegram_chat_ids=notified_chat_ids,
            )

        self.assertEqual(notified_chat_ids, {12345})
        site_telegram.assert_called_once()
        direct_telegram.assert_not_called()

    def test_comment_uses_direct_telegram_when_site_delivery_fails(self):
        owner = self._user("owner")
        commenter = self._user("commenter")
        author = self._author_with_owner(owner)
        author.notify_comments = True
        author.admin_chat_id = 12345
        author.save(update_fields=["notify_comments", "admin_chat_id"])
        TelegramAccount.objects.create(user=owner, telegram_id=12345)
        SiteNotificationPreference.objects.create(
            user=owner,
            event_key="post_comment",
            site_enabled=True,
            telegram_enabled=True,
            push_enabled=False,
        )
        post = self._post(author)
        comment = PostComment.objects.create(
            post=post,
            user=commenter,
            body="Comment",
        )

        with (
            patch("notifications.service.send_site_notification_to_telegram"),
            patch("feeds.views.telegram_bot._send_bot_message") as direct_telegram,
        ):
            notified_chat_ids = _maybe_notify_post_comment(post, comment)
            _maybe_notify_author_comment(
                post,
                comment,
                excluded_telegram_chat_ids=notified_chat_ids,
            )

        self.assertEqual(notified_chat_ids, set())
        direct_telegram.assert_called_once()
