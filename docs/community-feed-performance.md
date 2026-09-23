# Community feed performance

The community posts endpoint keeps its existing default response. Web feed readers use
`include_counts=0&include_comun=0&include_editor=0` and the returned `has_more` flag.
They fetch counters separately with `counts_only=1`; this response is private/no-store.

`CommunityFeedReader` checks language/category membership with EXISTS, counts distinct
IDs, selects a deterministic page ordered by created_at/id, and hydrates only those posts.
Visibility is rechecked at hydration. The additional partial index includes manual_comun
and MAX sources. Migration 0177 creates it concurrently and keeps the previous index.

Ratings, community references and personal author profiles are loaded in batches.
Template settings memoization lives only inside one GET/HEAD operation, with ContextVar
cleanup on exceptions. Mutation handlers are not memoized.

API Server-Timing describes origin generation, including DB duration and SQL count.
An intermediary can serve these headers from cache: use nginx cache status and
request/upstream timings to distinguish cache hits from generation. Slow origin APIs
log the URL route pattern, not SQL parameters or user identifiers.

Validation:

```sh
npm run build
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py test communities.tests.test_feed_performance rabotaem_backend.tests.test_read_context ratings.tests.test_service communities.tests.test_runtime_bridges communities.tests.test_models_api --keepdb --noinput
```

2026-09-23: 22 focused tests passed. The older posting API suite has 12 pre-existing
failures; identical failure names reproduced on baseline a96c49a in an isolated checkout.

Before deployment, a read-only candidate process against production wherefilmed data
returned the same 3,780 IDs as the old language selection. Uncached compact responses
were 199–240 ms / 20 SQL calls, compared with the audit's 18–24 s / 150 calls on the full
old feed path. Full legacy responses retained counters and took 1.99–2.09 s / 30 calls.
These are individual observations, not a load-test percentile. The new index was not
yet present during those candidate measurements.

Redis, cache invalidation redesign, cursor pagination and normalized feed membership
are separate follow-up stages, not part of this change.
