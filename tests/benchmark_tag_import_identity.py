"""Local PostgreSQL only: bounded comparison of tag assignment before/after fix."""
import ast
import json
import statistics
import subprocess
import time
from unittest.mock import patch
from django.db import connection, transaction, IntegrityError
from django.test.runner import DiscoverRunner
from django.test.utils import CaptureQueriesContext
from feeds import views
from feeds.models import Author, Post, Tag


class TagIdentityBenchmark:
    def run(self):
        source = subprocess.check_output(['git', 'show', '105edd1:backend/feeds/views.py'], text=True)
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == '_apply_post_tags')
        scope = dict(vars(views))
        exec(compile(ast.get_source_segment(source, node), '<baseline>', 'exec'), scope)
        before = scope['_apply_post_tags']
        Tag.objects.bulk_create([Tag(name=f'fixture-{n}', lemma=f'fixture-{n}') for n in range(500)], batch_size=500)
        Tag.objects.create(name='changed', lemma='old-lemma')
        author = Author.objects.create(username='tag-benchmark')
        post = Post.objects.create(author=author, message_id=1, title='Example', content='Text')
        results = {}
        for case, explicit, lemma in [('normal', 'fixture-0', 'fixture-0'), ('changed_lemma', 'changed', 'changed')]:
            for label, assign in [('before', before), ('after', views._apply_post_tags)]:
                elapsed, sql, dbms, failed = [], [], [], 0
                with patch.dict(scope, _lemmatize_tag=lambda _: lemma), patch('feeds.views._lemmatize_tag', return_value=lemma):
                    for _ in range(30):
                        with CaptureQueriesContext(connection) as queries:
                            started = time.perf_counter()
                            try:
                                with transaction.atomic():
                                    assign(post, [explicit])
                            except IntegrityError:
                                failed += 1
                            elapsed.append((time.perf_counter()-started)*1000)
                        sql.append(len(queries))
                        dbms.append(sum(float(q['time']) for q in queries)*1000)
                results[f'{case}_{label}'] = {'samples':30, 'median_ms':round(statistics.median(elapsed),2),
                    'max_ms':round(max(elapsed),2), 'sql_median':statistics.median(sql),
                    'db_ms_median':round(statistics.median(dbms),2), 'failed':failed}
        print(json.dumps(results))


assert connection.settings_dict['NAME'] == 'telegram_runtime_tests'
assert connection.settings_dict['HOST'] == '127.0.0.1'
runner = DiscoverRunner(verbosity=0, interactive=False)
runner.setup_test_environment()
config = runner.setup_databases(aliases={'default'})
try:
    TagIdentityBenchmark().run()
finally:
    runner.teardown_databases(config)
    runner.teardown_test_environment()
