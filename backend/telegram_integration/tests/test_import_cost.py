"""Bounded synthetic SQL budgets; set TAMBUR_TG_BENCHMARK=1 for timings (no live API)."""
import json
import os
from statistics import median
from time import perf_counter
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from feeds.models import Author, Post
from telegram_integration.models import TelegramApprovalDelivery
from telegram_integration.moderation import TelegramApprovalPrompt
from communities.models import Comun
from telegram_integration import bot

@override_settings(TELEGRAM_USE_POLLING=False, TELEGRAM_BOT_TOKEN='test', CACHES={'default':{'BACKEND':'django.core.cache.backends.dummy.DummyCache'}})
class ChannelImportCostTests(TestCase):
    def test_cost(self):
        a = Author.objects.create(username='cost-channel', channel_id=-100123, admin_chat_id=123)
        Comun.objects.create(name='Cost', slug='cost', telegram_source_author=a)
        def fetch(method, token, payload):
            if method=='getChat':
                return {'ok': True, 'result': {'id':-100123, 'type':'channel', 'username':a.username}}
            if method=='getChatMemberCount':
                return {'ok': True, 'result': 3}
            return {'ok':True,'result':{'message_id':444}}
        times=[]
        sql=[]
        db=[]
        calls=[]
        with patch.object(bot, '_fetch_telegram_json', side_effect=fetch) as network, patch.object(bot,'_is_bot_admin',return_value=True), patch('feeds.views._maybe_notify_new_author'):
            for n in range(20):
                network.reset_mock()
                start=perf_counter()
                with CaptureQueriesContext(connection) as q:
                    bot._handle_channel_post({'chat':{'id':-100123,'type':'channel','username':a.username},'message_id':n+1,'text':'Short example'})
                times.append((perf_counter()-start)*1000)
                sql.append(len(q))
                db.append(sum(float(x['time'])*1000 for x in q))
                calls.append(network.call_count)
        self.assertLessEqual(max(sql), 40)
        if os.environ.get('TAMBUR_TG_BENCHMARK') == '1':
            print(json.dumps({'samples':20,'median_ms':round(median(times),2),'sql_calls':sorted(set(sql)),'median_db_ms':median(db),'metadata_api_calls':sorted(set(calls))}))

@override_settings(TELEGRAM_USE_POLLING=False,TELEGRAM_BOT_TOKEN='')
class ApprovalDeliveryCostTests(TestCase):
    def test_cost(self):
        author=Author.objects.create(username='delivery-cost',admin_chat_id=123)
        service=TelegramApprovalPrompt(lambda *a: {'ok':True,'result':{'message_id':99}})
        times=[]
        counts=[]
        db=[]
        for n in range(20):
            post=Post.objects.create(author=author,message_id=n+1,title='Example',is_pending=True)
            start=perf_counter()
            with CaptureQueriesContext(connection) as q:
                service.deliver(post,author)
            times.append((perf_counter()-start)*1000)
            counts.append(len(q))
            db.append(sum(float(x['time'])*1000 for x in q))
        self.assertLessEqual(max(counts), 12)
        if os.environ.get('TAMBUR_TG_BENCHMARK') == '1':
            print(json.dumps({'new_delivery_samples':20,'median_ms':round(median(times),2),'queries':sorted(set(counts)),'median_db_ms':median(db)}))
        for target in (100,1000):
            existing=Post.objects.count()
            posts=Post.objects.bulk_create([Post(author=author,message_id=n+1,title='Example',is_pending=True) for n in range(existing,target)])
            TelegramApprovalDelivery.objects.bulk_create([TelegramApprovalDelivery(post=p,chat_id=123,sent_at=timezone.now()) for p in posts])
            times=[]
            counts=[]
            for _ in range(20):
                start=perf_counter()
                with CaptureQueriesContext(connection) as q:
                    self.assertEqual(service.drain(),0)
                times.append((perf_counter()-start)*1000)
                counts.append(len(q))
            self.assertEqual(set(counts), {1})
            if os.environ.get('TAMBUR_TG_BENCHMARK') == '1':
                print(json.dumps({'sent_history':target,'samples':20,'empty_due_scan_median_ms':round(median(times),2),'queries':sorted(set(counts))}))
        with connection.cursor() as c:
            c.execute("SELECT indisvalid,indisready FROM pg_index JOIN pg_class ON pg_class.oid=pg_index.indexrelid WHERE relname IN ('author_telegram_chat_idx','tg_approval_due_idx')")
            states = c.fetchall()
            self.assertEqual(states, [(True, True), (True, True)])
