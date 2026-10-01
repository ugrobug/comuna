"""Reproducible local scale/latency observations; timings are not unit-test assertions."""
import base64
import json
import os
from concurrent.futures import ThreadPoolExecutor
from statistics import median
from threading import Barrier
from time import perf_counter

from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext

from communities.models import Comun
from feeds.models import Author, Post, MentionDelivery
from feeds.mentions import MentionService, MentionSearch
from notifications.models import SiteNotification


class MentionPerformanceTests(TestCase):
    def test_search_scale_and_write_cost(self):
        size = min(100000, max(1000, int(os.environ.get('MENTION_PERF_USERS', 10000))))
        user_model = get_user_model()
        user_model.objects.bulk_create([user_model(username=f'perfuser{i:05}', first_name='Тест', last_name=f'Фамилия{i}') for i in range(size)], batch_size=1000)
        Comun.objects.bulk_create([Comun(name=f'Тестовое сообщество {i:05}', slug=f'perfclub{i:05}') for i in range(size // 10)], batch_size=500)
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE auth_user')
            cursor.execute('ANALYZE feeds_comun')
        for label, query in [('specific', 'perfuser099'), ('broad', 'Тест'), ('community', 'perfclub009')]:
            durations, sql_ms, sizes = [], [], []
            plans = []
            for i in range(20):
                start = perf_counter()
                with CaptureQueriesContext(connection) as sql:
                    results = MentionSearch().search(query)
                durations.append((perf_counter() - start) * 1000)
                self.assertEqual(len(sql), 2)
                sql_ms.append(sum(float(q['time']) * 1000 for q in sql))
                sizes.append(len(json.dumps(results, ensure_ascii=False).encode()))
                if i == 0:
                    with connection.cursor() as cursor:
                        for row in sql:
                            cursor.execute('EXPLAIN ' + row['sql'])
                            plans += [r[0] for r in cursor.fetchall()]
            print(f'MENTION_SEARCH {label}: n=20 users={size} communities={size // 10} median_ms={median(durations):.2f} max_ms={max(durations):.2f} queries=2 median_sql_ms={median(sql_ms):.2f} bytes={max(sizes)}')
            print('MENTION_INDEXES', ', '.join(p.strip() for p in plans if 'Index' in p))
        writer = user_model.objects.create(username='perfwriter')
        author = Author.objects.create(username=writer.username)
        post = Post.objects.create(author=author, message_id=1)
        targets = list(user_model.objects.filter(username__startswith='perfuser').order_by('id')[:20])
        baseline = []
        for _ in range(10):
            start = perf_counter()
            Post.objects.filter(pk=post.pk).update(content='Обычный текст')
            baseline.append((perf_counter()-start)*1000)
        print(f'MENTION_SAVE baseline_without_service n=10 median_ms={median(baseline):.2f} queries=1')
        for count in (0, 1, 20):
            values = []
            for i in range(10):
                MentionDelivery.objects.filter(post=post).delete()
                SiteNotification.objects.filter(event_key='post_mention').delete()
                text = ' '.join(f'<a href="/id{u.pk}?mention=user.{u.pk}">@{u.username}</a>' for u in targets[:count]) or 'Обычный текст'
                post.content = base64.b64encode(json.dumps({'blocks':[{'type':'paragraph','data':{'text':text}}]}).encode()).decode()
                start = perf_counter()
                with CaptureQueriesContext(connection) as sql:
                    MentionService().save_source(post, lambda: Post.objects.filter(pk=post.pk).update(content=post.content))
                values.append((perf_counter()-start)*1000)
                self.assertEqual(SiteNotification.objects.filter(event_key='post_mention').count(),count)
            print(f'MENTION_SAVE recipients={count} n=10 median_ms={median(values):.2f} max_ms={max(values):.2f} queries_including_update={len(sql)}')


class MentionConcurrencyTests(TransactionTestCase):
    def test_two_concurrent_edits_deliver_only_once(self):
        writer = get_user_model().objects.create(username='concurrentwriter')
        target = get_user_model().objects.create(username='concurrentreader')
        author = Author.objects.create(username=writer.username)
        post = Post.objects.create(author=author, message_id=1)
        barrier = Barrier(2)
        def edit():
            close_old_connections()
            try:
                item = Post.objects.get(pk=post.pk)
                item.content = f'<a href="/id{target.pk}?mention=user.{target.pk}">@reader</a>'
                barrier.wait(timeout=5)
                MentionService().save_source(item, lambda: Post.objects.filter(pk=item.pk).update(content=item.content))
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(edit) for _ in range(2)]
            for future in futures:
                future.result(timeout=10)
        self.assertEqual(MentionDelivery.objects.filter(post=post).count(),1)
        self.assertEqual(SiteNotification.objects.filter(user=target,event_key='post_mention').count(),1)
