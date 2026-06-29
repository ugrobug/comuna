from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from notifications.models import SiteNotification
from notifications.service import (
    create_grouped_user_notification,
    list_site_notifications_for_user,
    send_due_grouped_notifications,
)
from telegram_integration.service import _grouped_post_notification_text

User = get_user_model()


class GroupedNotificationDeliveryTests(TestCase):
    def test_grouped_notification_is_delivered_once_when_due(self):
        user = User.objects.create_user(
            username="subscriber",
            email="subscriber@example.com",
            password="password",
        )
        now = timezone.now()
        delivery_at = now + timedelta(hours=1)

        with (
            patch("notifications.service.send_site_notification_to_telegram") as telegram_mock,
            patch("notifications.service.send_site_notification_to_push") as push_mock,
        ):
            notification = create_grouped_user_notification(
                user=user,
                event_key="post_published",
                title="Новые посты за день",
                message="",
                link_url="/b/post/1-first",
                payload={"grouping_period": "day", "group_label": "за день"},
                group_key="post_published:day:2026-06-29",
                group_item={"id": 1, "title": "Первый пост", "link_url": "/b/post/1-first"},
                delivery_at=delivery_at,
                defer_delivery=True,
                force_site=True,
                force_telegram=True,
                force_push=True,
            )
            create_grouped_user_notification(
                user=user,
                event_key="post_published",
                title="Новые посты за день",
                message="",
                link_url="/b/post/2-second",
                payload={"grouping_period": "day", "group_label": "за день"},
                group_key="post_published:day:2026-06-29",
                group_item={"id": 2, "title": "Второй пост", "link_url": "/b/post/2-second"},
                delivery_at=delivery_at,
                defer_delivery=True,
                force_site=True,
                force_telegram=True,
                force_push=True,
            )

            notification.refresh_from_db()
            self.assertIsNone(notification.delivered_at)
            self.assertEqual(notification.group_count, 2)
            self.assertEqual(SiteNotification.objects.filter(user=user).count(), 1)
            visible, unread_count, total_count = list_site_notifications_for_user(user)
            self.assertEqual(visible, [])
            self.assertEqual(unread_count, 0)
            self.assertEqual(total_count, 0)
            telegram_mock.assert_not_called()
            push_mock.assert_not_called()

            self.assertEqual(send_due_grouped_notifications(now=delivery_at - timedelta(seconds=1)), 0)
            self.assertEqual(send_due_grouped_notifications(now=delivery_at), 1)

            notification.refresh_from_db()
            self.assertIsNotNone(notification.delivered_at)
            self.assertIn("Первый пост", notification.message)
            self.assertIn("Второй пост", notification.message)
            visible, unread_count, total_count = list_site_notifications_for_user(user)
            self.assertEqual(len(visible), 1)
            self.assertEqual(unread_count, 1)
            self.assertEqual(total_count, 1)
            telegram_mock.assert_called_once_with(notification)
            push_mock.assert_called_once_with(notification)


class GroupedTelegramTextTests(TestCase):
    @override_settings(SITE_BASE_URL="https://tambur.pub")
    def test_grouped_post_telegram_text_uses_only_ten_title_links(self):
        notification = SiteNotification(
            event_key="post_published",
            group_key="post_published:day:2026-06-29",
            title="Новые посты за день",
            payload={
                "items": [
                    {
                        "id": index,
                        "title": f"Пост {index}",
                        "link_url": f"/b/post/{index}-post",
                    }
                    for index in range(1, 13)
                ]
            },
        )

        text = _grouped_post_notification_text(notification)

        self.assertIn("Пост 10", text)
        self.assertIn("https://tambur.pub/b/post/10-post", text)
        self.assertNotIn("Пост 11", text)
        self.assertNotIn("https://tambur.pub/b/post/11-post", text)
