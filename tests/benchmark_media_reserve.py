"""Run via manage.py shell with bot_test_settings; local PostgreSQL only."""
import json
import statistics
import time
from tempfile import TemporaryDirectory
from django.core.files.base import ContentFile
from django.core.files.storage import FileSystemStorage
from django.db import connection
from django.test.runner import DiscoverRunner
from django.test.utils import CaptureQueriesContext
from media_storage.spool import LocalMediaSpool
from media_storage.models import MediaTransfer


class MediaReserveBenchmark:
    def run(self):
        result = {}
        payload = b'x' * 1024**2
        with TemporaryDirectory() as directory:
            for name, storage in [('local_reference', FileSystemStorage(location=directory)),
                                  ('reserve_with_queue', LocalMediaSpool(directory, reserve_bytes=0))]:
                elapsed, sql = [], []
                for index in range(30):
                    with CaptureQueriesContext(connection) as queries:
                        start = time.perf_counter()
                        storage.save(f'{name}-{index}.jpg', ContentFile(payload))
                        elapsed.append((time.perf_counter()-start)*1000)
                    sql.append(len(queries))
                result[name] = {'samples': 30, 'file_bytes': len(payload),
                    'median_ms': round(statistics.median(elapsed), 2), 'max_ms': round(max(elapsed), 2),
                    'sql_per_file': sorted(set(sql))}
            # Representative growth of historical receipts; due lookup has its own partial index.
            MediaTransfer.objects.bulk_create([MediaTransfer(key=f'_spool/fixture/{n}', size=1, sha256='a'*64,
                state='uploaded') for n in range(30000)], batch_size=500)
            with connection.cursor() as cursor:
                cursor.execute('ANALYZE media_storage_mediatransfer')
            due = MediaTransfer.objects.filter(state__in=['pending', 'deleting']).order_by('next_attempt_at', 'id')[:1]
            plan = json.loads(due.explain(format='json', analyze=True, buffers=True))[0]
            result['due_lookup_with_30000_historical_rows'] = {'execution_ms': plan['Execution Time'],
                'plan': plan['Plan']['Plans'][0]['Node Type'], 'index': plan['Plan']['Plans'][0].get('Index Name')}
        print(json.dumps(result))


assert connection.settings_dict['NAME'] == 'telegram_runtime_tests'
assert connection.settings_dict['HOST'] == '127.0.0.1'
runner = DiscoverRunner(verbosity=0, interactive=False)
runner.setup_test_environment()
config = runner.setup_databases(aliases={'default'})
try:
    MediaReserveBenchmark().run()
finally:
    runner.teardown_databases(config)
    runner.teardown_test_environment()
