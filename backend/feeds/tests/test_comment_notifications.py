from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from feeds.models import Author, Post, PostComment
from feeds.views import _maybe_notify_comment_reply, _maybe_notify_post_comment
from notifications.models import SiteNotification, SiteNotificationPreference
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
