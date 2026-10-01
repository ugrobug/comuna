import base64
import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from communities.models import Comun
from feeds.models import Author, Post, PostComment, MentionDelivery
from feeds.mentions import MentionParser, MentionSearch, MentionService
from notifications.models import SiteNotification, SiteNotificationPreference
from notifications.service import list_site_notifications_for_user
from users.service import _issue_token


def user_link(user):
    return f'<a href="/id{user.pk}?mention=user.{user.pk}">@{user.username}</a>'


def editor_content(text, kind='paragraph'):
    return base64.b64encode(json.dumps({'blocks': [{'type': kind, 'data': {'text': text}}]}).encode()).decode()


@override_settings(SITE_BASE_URL='https://tambur.pub')
class MentionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.writer = get_user_model().objects.create_user(username='writer')
        cls.reader = get_user_model().objects.create_user(username='alina_art', first_name='Алина', last_name='Петрова')
        cls.owner = get_user_model().objects.create_user(username='owner')
        cls.author = Author.objects.create(username=cls.writer.username)
        cls.comun = Comun.objects.create(name='Любители кино', slug='cinema', creator=cls.owner)
        cls.post = Post.objects.create(author=cls.author, message_id=1, title='Title')

    def test_search_by_username_full_name_and_community_name(self):
        for query in ('alina', 'Алина Пет', 'Петрова Алина'):
            self.assertEqual(MentionSearch().search(query)[0]['id'], self.reader.pk)
        self.assertEqual(MentionSearch().search('Любители ки')[0]['id'], self.comun.pk)
        self.reader.is_active = False
        self.reader.save()
        self.comun.is_active = False
        self.comun.save()
        self.assertEqual(MentionSearch().search('alina'), [])
        self.assertEqual(MentionSearch().search('Любители'), [])

    def test_search_is_bounded_two_queries_and_compact(self):
        get_user_model().objects.bulk_create([get_user_model()(username=f'alina{i}') for i in range(35)])
        with CaptureQueriesContext(connection) as queries:
            rows = MentionSearch().search('alina')
        self.assertEqual(len(queries), 2)
        self.assertEqual(len(rows), 5)
        self.assertNotIn('email', rows[0])
        self.assertTrue(all('LIMIT 5' in q['sql'] for q in queries))

    def test_search_endpoint_requires_login(self):
        self.assertEqual(self.client.get(reverse('mention-suggestions'), {'q': 'alina'}).status_code, 401)
        response = self.client.get(reverse('mention-suggestions'), {'q': 'alina'},
                                   HTTP_AUTHORIZATION=f'Bearer {_issue_token(self.writer)}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['items'][0]['id'], self.reader.pk)
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_post_saved_as_editor_blocks_notifies_once_and_links_to_post(self):
        self.post.content = editor_content(user_link(self.reader) * 3)
        self.post.save()
        self.post.save()
        self.post.content = ''
        self.post.save()
        self.post.content = editor_content(user_link(self.reader))
        self.post.save()
        notification = SiteNotification.objects.get(user=self.reader)
        self.assertEqual(notification.event_key, 'post_mention')
        self.assertEqual(notification.link_url, f'/b/post/{self.post.pk}')
        self.assertEqual(list_site_notifications_for_user(self.reader)[1], 1)
        self.assertEqual(MentionDelivery.objects.count(), 1)

    def test_comments_owner_direct_dedupe_and_new_mentions_on_edit(self):
        body = (f'[@Кино](/comuns/cinema?mention=comun.{self.comun.pk}) '
                f'[@owner](/id{self.owner.pk}?mention=user.{self.owner.pk})')
        comment = PostComment.objects.create(post=self.post, user=self.writer, body=body)
        notification = SiteNotification.objects.get(user=self.owner)
        self.assertIn('Любители кино', notification.message)
        self.assertEqual(notification.link_url, f'/b/post/{self.post.pk}#site-comment-{comment.pk}')
        comment.body += f' [@alina](/id{self.reader.pk}?mention=user.{self.reader.pk})'
        comment.save(update_fields=['body'])
        self.assertEqual(SiteNotification.objects.count(), 2)
        self.assertEqual(MentionDelivery.objects.count(), 2)

    def test_draft_future_hidden_and_deleted_do_not_notify(self):
        for values in ({'is_pending': True}, {'is_blocked': True},
                       {'publish_at': timezone.now()+timedelta(days=1)}, {'companion_matched_at': timezone.now()}):
            for field, value in values.items():
                setattr(self.post, field, value)
            self.post.content = editor_content(user_link(self.reader))
            self.post.save()
            self.assertEqual(SiteNotification.objects.count(), 0)
            self.post.refresh_from_db()
            for field in values:
                setattr(self.post, field, False if field.startswith('is_') else None)
        self.post.save()
        self.assertEqual(SiteNotification.objects.count(), 1)
        SiteNotification.objects.all().delete()
        PostComment.objects.create(post=self.post, user=self.writer, body=user_link(self.reader), is_deleted=True)
        self.assertFalse(SiteNotification.objects.exists())

    def test_self_and_inactive_users_are_not_notified(self):
        self.reader.is_active = False
        self.reader.save()
        self.post.content = editor_content(user_link(self.writer) + user_link(self.reader))
        self.post.save()
        PostComment.objects.create(post=self.post, user=self.writer, body=user_link(self.writer))
        self.assertFalse(SiteNotification.objects.exists())

    def test_preferences_and_external_delivery_are_not_network_calls_during_save(self):
        SiteNotificationPreference.objects.create(user=self.reader, event_key='post_mention', site_enabled=False,
                                                   telegram_enabled=False, push_enabled=False)
        self.post.content = editor_content(user_link(self.reader))
        self.post.save()
        self.assertFalse(SiteNotification.objects.exists())
        SiteNotificationPreference.objects.create(user=self.owner, event_key='post_mention', site_enabled=True,
                                                   telegram_enabled=True, push_enabled=True)
        with patch('notifications.service.send_site_notification_to_telegram') as telegram, patch('notifications.service.send_site_notification_to_push') as push:
            self.post.content = editor_content(user_link(self.reader) + user_link(self.owner))
            self.post.save()
            telegram.assert_not_called()
            push.assert_not_called()
        self.assertIsNone(SiteNotification.objects.get(user=self.owner).delivered_at)

    def test_invalid_code_plain_text_and_foreign_links_ignored(self):
        link = user_link(self.reader)
        foreign = link.replace('href="/', 'href="https://evil.test/')
        for value, comment in [('@alina_art', True), (f'`{link}`', True), (f'```\n{link}\n```', True),
                               (f'<pre>{link}</pre>', True), (foreign, True), (editor_content(link, 'code'), False)]:
            self.assertEqual(MentionParser().extract(value, comment=comment), set())
        self.assertEqual(MentionParser().extract(link.replace('href="/', 'href="https://tambur.pub/')),
                         {('user', self.reader.pk)})

    def test_target_cap_and_no_recipient_query_growth(self):
        users = get_user_model().objects.bulk_create([get_user_model()(username=f'target{i}') for i in range(30)])
        self.post.content = editor_content(' '.join(user_link(u) for u in users))
        with CaptureQueriesContext(connection) as queries:
            MentionService().save_source(self.post, lambda: Post.objects.filter(pk=self.post.pk).update(content=self.post.content))
        self.assertEqual(SiteNotification.objects.count(), 20)
        self.assertLessEqual(len(queries), 13)

    def test_normal_content_adds_no_queries(self):
        with self.assertNumQueries(0):
            MentionService().save_source(self.post, lambda: None)

    def test_receipts_and_notifications_rollback_together(self):
        with patch.object(SiteNotification.objects, 'bulk_create', side_effect=RuntimeError('failed')):
            self.post.content = editor_content(user_link(self.reader))
            with self.assertRaises(RuntimeError):
                self.post.save()
        self.assertEqual(Post.objects.get(pk=self.post.pk).content, '')
        self.assertEqual(MentionDelivery.objects.count(), 0)

    def test_scheduled_worker_sends_mention_only_when_published(self):
        from editor.management.commands.publish_scheduled_posts import publish_due_posts
        self.post.content = editor_content(user_link(self.reader))
        self.post.is_pending = True
        self.post.publish_at = timezone.now() - timedelta(minutes=1)
        self.post.raw_data = {'scheduled_publication': True, 'scheduled_by_user_id': self.writer.pk, 'source': 'manual'}
        self.post.save()
        self.assertFalse(SiteNotification.objects.exists())
        with patch('communities.service._maybe_notify_post_published_to_subscribers'):
            self.assertEqual(publish_due_posts(), 1)
            self.assertEqual(publish_due_posts(), 0)
        self.assertEqual(SiteNotification.objects.filter(event_key='post_mention').count(), 1)

    def test_comment_api_create_and_edit_generate_mentions(self):
        auth = {'HTTP_AUTHORIZATION': f'Bearer {_issue_token(self.writer)}'}
        body = f'[@alina](/id{self.reader.pk}?mention=user.{self.reader.pk})'
        response = self.client.post(f'/api/posts/{self.post.pk}/comments/',
                                    json.dumps({'body': body}), content_type='application/json', **auth)
        self.assertEqual(response.status_code, 200, response.content)
        identifier = response.json()['comment']['id']
        response = self.client.patch(f'/api/comments/{identifier}/', json.dumps({'body': body+' edited'}),
                                     content_type='application/json', **auth)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(SiteNotification.objects.filter(event_key='comment_mention').count(), 1)

    def test_pending_external_alert_is_cancelled_when_content_is_hidden(self):
        from notifications.service import send_due_grouped_notifications
        SiteNotificationPreference.objects.create(user=self.reader, event_key='post_mention',
                                                   telegram_enabled=True, push_enabled=False)
        self.post.content = editor_content(user_link(self.reader))
        self.post.save()
        self.post.is_blocked = True
        self.post.save(update_fields=['is_blocked'])
        with patch('notifications.service.send_site_notification_to_telegram') as send:
            send_due_grouped_notifications()
            send.assert_not_called()
        self.assertFalse(SiteNotification.objects.filter(event_key='post_mention').exists())
        self.assertTrue(MentionDelivery.objects.filter(post=self.post).exists())
