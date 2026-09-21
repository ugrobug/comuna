import hashlib
import json
from datetime import timedelta
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from communities.models import Comun, ComunGlossaryTerm, ComunKnowledgeBaseItem
from communities.service import _comun_posts_base_queryset
from feeds.models import Post
from max_integration.bot import MaxBot
from max_integration.models import MaxAccount, MaxChat, MaxUpdate, MaxVerificationCode, MaxNotificationDelivery
from max_integration.publishing import MaxPostPublisher
from max_integration.service import MaxAccountService, MaxChannelService
from max_integration.submissions import MaxSubmissionService
from max_integration.management.commands.process_max_events import Command
from notifications.service import create_user_notification
from users.service import _issue_token


@override_settings(TELEGRAM_BOT_TOKEN='', TELEGRAM_USE_POLLING=False, MAX_WEBHOOK_SECRET='test-webhook-secret')
class MaxIntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='max-owner')
        self.other = get_user_model().objects.create_user(username='max-other')
        self.comun = Comun.objects.create(name='MAX community', slug='max-community', creator=self.user,
            knowledge_base_enabled=True, glossary_enabled=True)
        self.account = MaxAccount.objects.create(user=self.user, max_user_id=123, dialog_id=456)
        self.chat = MaxChat.objects.create(chat_id=-100, chat_type='channel', title='MAX channel', link='https://max.ru/test')
        self.api = Mock()
        self.api.admins.return_value = [{'user_id':123}]
        self.api.request.return_value = {'is_admin':True}
        self.api.chat.return_value = {'chat_id':-100, 'type':'channel', 'status':'active', 'title':'MAX channel', 'link':'https://max.ru/test'}
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {_issue_token(self.user)}'

    def linked_chat(self):
        self.chat.comun = self.comun
        self.chat.save()
        return self.chat

    def test_webhook_rejects_invalid_secret_and_queues_once(self):
        payload = {'update_type':'bot_added', 'chat_id':-100, 'user':{'user_id':123}}
        self.assertEqual(self.client.post('/api/max/webhook/', data=json.dumps(payload), content_type='application/json').status_code, 403)
        for _ in range(2):
            response = self.client.post('/api/max/webhook/', data=json.dumps(payload), content_type='application/json', HTTP_X_MAX_BOT_API_SECRET='test-webhook-secret')
            self.assertEqual(response.status_code, 200)
        self.assertEqual(MaxUpdate.objects.count(), 1)
        self.assertIsNone(MaxUpdate.objects.get().processed_at)
        self.assertEqual(self.client.post('/api/max/webhook/', data='[]', content_type='application/json', HTTP_X_MAX_BOT_API_SECRET='test-webhook-secret').status_code, 400)

    def test_verification_code_single_use_and_expiry(self):
        code = MaxAccountService.issue_code(self.other)
        self.assertNotEqual(MaxVerificationCode.objects.get(user=self.other).digest, code)
        linked = MaxAccountService.redeem_code(code, {'user_id':777,'name':'Test'}, 888)
        self.assertEqual(linked.user, self.other)
        with self.assertRaises(ValueError): MaxAccountService.redeem_code(code, {'user_id':777}, 888)
        code = MaxAccountService.issue_code(self.other)
        MaxVerificationCode.objects.filter(user=self.other).update(expires_at=timezone.now()-timedelta(seconds=1))
        with self.assertRaises(ValueError): MaxAccountService.redeem_code(code, {'user_id':777}, 888)

    def test_code_cannot_claim_existing_max_identity(self):
        code = MaxAccountService.issue_code(self.other)
        with self.assertRaises(ValueError): MaxAccountService.redeem_code(code, {'user_id':123}, 888)
        self.assertEqual(MaxAccount.objects.get(max_user_id=123).user, self.user)

    def test_bot_added_never_creates_community(self):
        MaxBot(self.api).handle({'update_type':'bot_added', 'chat_id':-100, 'user':{'user_id':123}})
        self.chat.refresh_from_db()
        self.assertIsNone(self.chat.comun_id)
        self.assertEqual(Comun.objects.count(),1)
        self.assertFalse(Post.objects.exists())

    def test_link_requires_site_and_max_rights_for_both_chat_types(self):
        service = MaxChannelService(self.api)
        for kind in ['channel','chat']:
            self.chat.chat_type=kind
            self.chat.save()
            linked=service.link(self.account,self.chat,self.comun)
            self.assertEqual(linked.comun_id,self.comun.pk)
        self.comun.creator=self.other
        self.comun.save()
        with self.assertRaises(ValueError): service.link(self.account,self.chat,self.comun)
        self.comun.creator=self.user
        self.comun.save()
        self.api.admins.return_value=[]
        with self.assertRaises(ValueError): service.link(self.account,self.chat,self.comun)
        self.api.admins.return_value=[{'user_id':123}]
        self.api.request.return_value={'is_admin':False}
        with self.assertRaises(ValueError): service.link(self.account,self.chat,self.comun)

    def test_channel_post_import_is_idempotent_and_visible(self):
        chat=self.linked_chat()
        publisher=MaxPostPublisher()
        message={'body':{'mid':'message-1','text':'Hello <script>bad</script>','attachments':[{'type':'image','payload':{'url':'https://example.com/image.jpg'}}]}}
        post,created=publisher.import_message(chat,message)
        self.assertTrue(created)
        self.assertNotIn('<script>',post.content)
        self.assertIn('<img ',post.content)
        self.assertTrue(_comun_posts_base_queryset(self.comun).filter(pk=post.pk).exists())
        message['body']['text']='Edited'
        same,created=publisher.import_message(chat,message)
        self.assertFalse(created)
        self.assertEqual(post.pk,same.pk)
        self.assertEqual(same.title,'Edited')

    def test_unlinked_channel_and_pending_delayed_post_are_not_published(self):
        publisher=MaxPostPublisher()
        message={'body':{'mid':'message-1','text':'Test'}}
        self.assertEqual(publisher.import_message(self.chat,message),(None,False))
        chat=self.linked_chat()
        chat.auto_publish=False
        chat.publish_delay_days=3
        chat.save()
        post,_=publisher.import_message(chat,message)
        self.assertTrue(post.is_pending)
        self.assertGreater(post.publish_at,timezone.now()+timedelta(days=2))
        self.assertFalse(_comun_posts_base_queryset(self.comun).filter(pk=post.pk).exists())
        other=MaxAccount.objects.create(user=self.other,max_user_id=999,dialog_id=999)
        with self.assertRaises(ValueError): MaxBot(self.api).action(other,f'approve:{post.pk}',999)
        post.refresh_from_db()
        self.assertTrue(post.is_pending)
        MaxBot(self.api).action(self.account,f'approve:{post.pk}',456)
        post.refresh_from_db()
        self.assertFalse(post.is_pending)
        self.assertFalse(_comun_posts_base_queryset(self.comun).filter(pk=post.pk).exists())

    def test_max_only_notification_is_enqueued_and_sent_once(self):
        self.account.notification_events=['system']
        self.account.save()
        notification=create_user_notification(user=self.user,event_key='system',title='MAX test',force_site=False,force_telegram=False,force_push=False)
        self.assertIsNotNone(notification)
        self.assertEqual(MaxNotificationDelivery.objects.count(),1)
        bot=MaxBot(self.api)
        self.assertTrue(Command().process_notification(bot))
        self.assertFalse(Command().process_notification(bot))
        self.api.send.assert_called_once()
        self.assertIsNotNone(MaxNotificationDelivery.objects.get().sent_at)

    def test_failed_event_retries_without_exposing_exception(self):
        event=MaxUpdate.objects.create(digest='a'*64,payload={'update_type':'test'},available_at=timezone.now())
        bot=Mock();bot.handle.side_effect=RuntimeError('private-token')
        self.assertTrue(Command().process_update(bot))
        event.refresh_from_db()
        self.assertEqual(event.last_error,'RuntimeError')
        self.assertIsNone(event.processed_at)
        self.assertEqual(event.attempts,1)

    def test_group_submissions_require_moderator_and_do_not_duplicate(self):
        chat=self.linked_chat();chat.chat_type='chat';chat.save()
        for kind in ['kb','glossary']:
            message={'link':{'type':'reply','message':{'mid':f'msg-{kind}','text':'Термин — определение'}}}
            item,created=MaxSubmissionService.create(chat,message,kind)
            self.assertTrue(created)
            self.assertFalse(MaxSubmissionService.create(chat,message,kind)[1])
            with self.assertRaises(ValueError): MaxSubmissionService.review(self.other,item.pk,True)
            MaxSubmissionService.review(self.user,item.pk,True)
            with self.assertRaises(ValueError): MaxSubmissionService.review(self.user,item.pk,True)
        self.assertEqual(ComunKnowledgeBaseItem.objects.filter(comun=self.comun).count(),1)
        self.assertEqual(ComunGlossaryTerm.objects.filter(comun=self.comun).count(),1)

    def test_unlink_invalidates_unused_codes(self):
        code=MaxAccountService.issue_code(self.user)
        self.assertEqual(self.client.delete('/api/max/account/').status_code,200)
        with self.assertRaises(ValueError): MaxAccountService.redeem_code(code,{'user_id':123},456)
