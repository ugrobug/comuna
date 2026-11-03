"""Local PostgreSQL fixture benchmark; never point this runner at production."""
import json
import statistics
import subprocess
import time
from unittest.mock import patch
from django.test.runner import DiscoverRunner
from django.db import connection
from django.test.utils import CaptureQueriesContext
from feeds.models import Author, Post
from communities.models import Comun
from feeds import views
from telegram_integration.channel_import import TelegramChannelImport
from telegram_integration.media_queue import TelegramMediaWorker
from telegram_integration.models import TelegramMediaJob
from unittest.mock import Mock


class TelegramMediaBenchmark:
    def run(self):
        old = {}
        exec(compile(subprocess.check_output(['git', 'show', '7fe71e6:backend/telegram_integration/channel_import.py'], text=True), 'baseline', 'exec'), old)
        result = {}
        for variant, cls in [('before', old['TelegramChannelImport']), ('after', TelegramChannelImport)]:
            author = Author.objects.create(username=f'benchmark-{variant}', auto_publish=True)
            comun = Comun.objects.create(name=f'Benchmark {variant}', slug=f'benchmark-{variant}', telegram_source_author=author)
            service = cls(token='fake', content=views, check_access=lambda *a: True,
                refresh_metadata=lambda *a: None, resolve_community=lambda a: comun, send_prompt=Mock())
            elapsed, sql, dbms = [], [], []
            with patch('feeds.views._extract_photo_url', return_value='https://media.test/fixture.webp'), patch('feeds.views._maybe_notify_new_author'):
                for n in range(30):
                    message = {'chat': {'username': author.username, 'id': -123 if variant == 'before' else -124, 'type': 'channel'},
                        'message_id': n + 1, 'caption': 'Benchmark fixture text',
                        'photo': [{'file_id': f'fixture-{n}', 'width': 100, 'height': 100}]}
                    with CaptureQueriesContext(connection) as queries:
                        start = time.perf_counter()
                        service.receive(message)
                        elapsed.append((time.perf_counter() - start) * 1000)
                    sql.append(len(queries))
                    dbms.append(sum(float(q['time']) for q in queries) * 1000)
            assert Post.objects.filter(author=author).count() == 30
            result[variant] = {'samples': 30, 'median_ms': round(statistics.median(elapsed), 2),
                'max_ms': round(max(elapsed), 2), 'sql_median': statistics.median(sql),
                'sql_ms_median': round(statistics.median(dbms), 2), 'posts': Post.objects.filter(author=author).count()}
        # Repeated claims on 300 pending messages; only bounded batches are loaded.
        template = TelegramMediaJob.objects.filter(state='pending').first()
        TelegramMediaJob.objects.bulk_create([TelegramMediaJob(author=template.author, message_id=1000+n,
            payload=template.payload, revision=str(n)) for n in range(270)])
        worker = TelegramMediaWorker(download=Mock(side_effect=ConnectionError), content=views, prompt=Mock())
        with CaptureQueriesContext(connection) as queries:
            start = time.perf_counter()
            outcome = worker.drain(20)
        result['outage_300_jobs'] = {'ms': round((time.perf_counter()-start)*1000, 2),
            'sql': len(queries), 'attempts': worker.download.call_count, **outcome}
        print(json.dumps(result))


assert connection.settings_dict['NAME'] == 'telegram_runtime_tests'
assert connection.settings_dict['HOST'] == '127.0.0.1'
runner = DiscoverRunner(verbosity=0, interactive=False)
runner.setup_test_environment()
config = runner.setup_databases(aliases={'default'})
try:
    TelegramMediaBenchmark().run()
finally:
    runner.teardown_databases(config)
    runner.teardown_test_environment()
