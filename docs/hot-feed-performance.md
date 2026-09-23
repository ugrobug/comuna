# Hot feed: query optimization and compatibility checks

The September 2026 change optimizes `/api/home/` without replacing the ranking
algorithm, materialized feed, API pagination or personal filtering rules.
No schema migration or infrastructure change is required. The comparison below
records pre-release validation; deployed checks are recorded separately.

## Implementation

- `HomeFeedReader` applies language membership with EXISTS, selects distinct IDs
  and ordering columns first, then hydrates those rows. All existing eligibility
  predicates are rechecked during hydration, including matched invitations and
  read markers. DISTINCT no longer sorts complete bodies and JSON payloads.
- The hidden-community exclusion repeats `is_blocked=False/is_pending=False`.
  The outer query already requires both, so this does not change membership, but
  allows the existing partial `feeds_post_manual_comun_created_idx` to be used.
- `HomeFeedCardBatch` prepares personal author mappings, community references and
  moderator roles for the actual response page. It reuses existing preparation
  helpers; community precedence remains slug → category assignment → source.
- A request-scoped read context reuses template/rating settings. The context is
  released on completion or exception and is not shared across users/requests.
- Read-only history uses batched author/post scores. The live feed passes its
  already calculated score into serialization. Votes/favorites are loaded for
  returned cards; earlier pages are no longer serialized and discarded.
- Live ordering remains newest first, with ascending primary key explicitly
  resolving equal timestamps. Previously ties had no API guarantee. Snapshot
  ordering remains rank. Candidate multiplier, quotas, author alternation,
  current negative-score filtering and 14-day read window are unchanged.

The two application objects own query/hydration and card preparation respectively.
Existing HTTP adapters and selection rules are retained. No new shared cache is
introduced. Rolling back the change requires reverting the code; there is no data
conversion or migration to reverse.

## Functional verification

61 focused tests pass across hot feed, community feed, rating calculations,
request context, post cache, media previews, event and question templates.
The new tests cover language membership versus the former JOIN, personal hidden
posts/authors/community links, read-window/user isolation, visibility, quotas,
author alternation, offsets, equal timestamps, fractional scores, votes/favorites,
community precedence/roles, verified personal authors, templates, anonymous cache
isolation and visibility changes between ID selection and hydration.

The query-budget fixture uses 30 distinct communities/authors and checks both
10-card and 30-card pages, guest/authenticated and hide-read. SQL counts stay
constant and within 30 queries. This budget is for these representative cards;
special interactive templates can perform additional unchanged queries.

Old tests were corrected to use bearer-token API authentication, isolated response
cache, and explicit event/question template configuration. Their earlier failures
were also reproduced with original production code; these are fixture changes,
not changes to login, event or question behavior.

```sh
.venv/bin/python backend/manage.py test \
  feeds.tests.test_home_feed feeds.tests.test_home_feed_performance \
  communities.tests.test_feed_performance rabotaem_backend.tests.test_read_context \
  ratings.tests.test_service feeds.tests.test_post_detail_cache \
  feeds.tests.test_post_preview_images feeds.tests.test_event_template \
  feeds.tests.test_question_answers --keepdb --noinput
npm run build
.venv/bin/python backend/manage.py check
git diff --check
```

## Read-only production comparison

The running baseline was `0992ea1`. Candidate functions were loaded into an
independent Python process without modifying deployed files or serving traffic.
Both implementations read the same repeatable-read database snapshot and frozen
clock. Response caching was disabled only in that process's LocMemCache. For
authenticated cases the user resolver was injected; token and middleware overhead
are not measured. Only timings, counts and equality flags were exported.

All 10 final comparison scenarios returned equal **complete parsed JSON**, including
post order and all card fields: guest 10/30, offset 100, English, full legacy JSON,
authenticated, hide-read, hide-read offset 100, only-read and personal filters.

| Scenario | Before → after, ms | SQL before → after |
|---|---:|---:|
| Guest, 10 | 175 → 138 | 43 → 18 |
| Guest, 30 | 463 → 292 | 109 → 18 |
| Guest, offset 100 | 509 → 445 | 43 → 18 |
| English | 162 → 126 | 43 → 18 |
| Full JSON | 1526 → 162 | 84 → 19 |
| Authenticated | 188 → 222 | 56 → 22 |
| Hide read | 1443 → 170 | 97 → 23 |
| Hide read, offset 100 | 3944 → 549 | 920 → 23 |
| Only read, 7 cards | 665 → 95 | 89 → 18 |
| Personal filters | 202 → 155 | 56 → 22 |

These are individual observations, not p95 or a load test. The table deliberately
retains the slower authenticated observation; no claim is made that every request
is faster. Follow-up repeated authenticated comparisons are stored with the raw
results: three further pairs were 186 → 112, 196 → 124 and 189 → 150 ms, all with
equal responses. The primary improvement is the expensive read-filter/live-feed paths and
the removal of per-card SQL growth.

EXPLAIN ANALYZE of the optimized ID/hydration selection confirmed use of the
existing partial source index and no temporary block writes. Those plans were
captured before the last refinement that moved source-community loading from a
candidate JOIN into a batch for returned cards; the ID-selection SQL is unchanged.
The first candidate had a slower read-only-history path; it was rejected and fixed
before these final checks.

Evidence is in `output/hot-feed-fix-2026-09-23/`: `production-final.json`,
`production-plans.json`, repeated authentication measurements and test/build logs.

## Scope and release checks

This does not establish zero risk. Pre-release validation does not include a mobile
LCP/INP test, concurrent load test or p95 claim. The broad correctness evidence is
the automated coverage plus identical sampled production responses.

Before release, inspect the selected diff and keep unrelated analytics work out of
the commit. After deployment, verify the standard 200 responses and repeat uncached
guest/authenticated/read-filter timing checks on the running version. Compare error
rates and resource use; revert the code if a new regression appears. Broader load
tests belong on staging.

The 5× candidate window still grows with offset, and current rankings are still
recomputed to preserve behavior. A versioned cursor/read model, incremental
materialization, frontend SSR reuse and resource-size reductions are separate
changes that need their own compatibility checks.
