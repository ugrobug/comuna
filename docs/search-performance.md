# Search and autocomplete: bounded selection and compact responses

Implementation based on the 2026-09-23 audit, baseline `e43b3bb`.
This document records pre-release checks; the changes have not been deployed.

## Responsibilities and cost

- `SearchOptions` validates the query and bounds page work: 512 characters,
  50 results per type/page, first 5,000 results. Out-of-window requests return
  an explicit 400 error; the web pager stops at the window boundary. Ordinary
  one-character searches remain supported; suggestions require two characters.
- `SearchReader` owns PostgreSQL selection. Text and matching-author branches
  select only IDs and ordering columns, then UNION removes duplicates before
  pagination. Each branch needs at most offset + limit + 1 rows. Full Post rows
  are loaded once, only for the final page; eligibility is rechecked then.
- Newest ordering is `created_at DESC, id DESC`. Relevance ordering is
  `search_rank DESC, created_at DESC, id DESC`. Text matches keep their rank
  when their author also matches. Matching authors are a subquery, removing
  the former arbitrary 50-author cutoff. No exact full-result COUNT is added.
- `SearchPresenter` prepares final-page author profiles, communities and roles
  through the existing batch helpers. Ratings are calculated once in a batch
  only for authors actually returned by the legacy API. Request-scoped read
  context reuses settings and is reset on completion/errors.
- `SearchService` composes reader and presenter; HTTP functions are adapters.
  `/api/search/` retains its full card fields, type filters and `total_*` next-page
  hints. Editor, mentions and voting-post search callers keep that contract.
- `/api/search/suggest/` is a separate DTO: 5 posts, 3 communities, 3 authors;
  names, links/identifiers, short descriptions and image URLs. No votes,
  favorites, live polls, author ratings or complete card bodies are computed.
  Existing generated 320px variants are used where available. Legacy JPEGs and
  external images retain their URLs: no remote file probing or resizing occurs
  inside a search request. Dedicated 72/108px backfill is not part of this release.
- `SuggestionController` owns the debounce, abort, revision guard and bounded
  20-entry/10-second public-response cache. Input is invalidated immediately,
  including while the next debounce is pending. Clear, Escape, outside click,
  selection, submit and destruction cancel work. Errors are distinct from empty
  results. URL synchronization alone never requests or opens suggestions; the
  CSS-hidden header instance therefore does not request them.
- `SearchBackendProxy` rewrites only same-origin GET search calls to the configured
  internal backend during SSR, preserving authentication headers. The page uses
  a stable public fetch path so hydration reuses its serialized response. Other
  endpoints, methods and external URLs are unaffected. The full search form no
  longer invalidates every loader.

Author-first then site-user ordering and case-insensitive username deduplication
are retained. Narrow people candidates are read in chunks; only selected profiles
are hydrated. Blocked authors/inactive users are rechecked during hydration.

Guest caching keeps the existing 30-second policy. Compact results containing a
companion invitation, and authenticated compact responses, are explicitly private,
no-store; removing template data from the DTO must not bypass invitation privacy.
Public response caching does not cross authentication contexts.

## Intentional correctness changes

Previously the text branch took arbitrary IDs with LIMIT and sorted that truncated
set in Python. Newest search can now return different, newer posts. It also finds
posts from matching authors beyond the former 50-author cutoff and supports pages
beyond the former 200-candidate limit. Web pagination is now visible and its next
button stops when no next result exists. These changes are tested against expected
results rather than treating the previous truncated ordering as the specification.

Within the returned cards, template payloads, community precedence, roles, votes,
favorites, tags and author identity retain existing serializers. Existing
published/pending/blocked/matched filters are preserved. Search has not gained a
new language, stemming, typo-correction or personal-feed filtering policy.

## Functional checks

76 backend tests pass: search (12), hot/community card loading, thumbnails,
events, questions, companion matching/concurrency, ratings and request context.
The new search cases cover global newest order/ties, deep pages past the old cap,
text/author overlap, >50 author matches, ranked ordering, visibility for guests
and users, hiding a post between ID selection and hydration, personal fields,
author/user deduplication, compact DTO limits, no rating work in autocomplete,
invitation cache invalidation, input bounds and final-page-only hydration.

The SQL budget fixture uses 30 different authors/communities and moderator roles;
10- and 30-card pages remain within 30 queries with no proportional SQL growth.
Seven frontend tests cover input debounce, cancellation/races, cleanup, cache
expiry/private responses, errors and SSR proxy scope/authentication preservation.

`npm run build`, `manage.py check` and `git diff --check` pass.
The repository-wide `npm run check` still reports 20 errors/3 warnings in 11
untouched files (post-detail typing, Explore, roadmap, etc.). No diagnostics are
reported in the changed search/proxy files. This is not a clean global typecheck.

## Read-only production-data verification

The candidate was loaded into an independent Python process. No production code,
schema, data or running response cache was changed. SQL transactions were read-only
with a 12-second statement timeout. Tests froze time; authenticated checks injected
an ordinary user and therefore exclude token validation/middleware overhead.
These are individual observations, not p95 or full HTTP/page timings.

| Scenario | Before → after, ms | SQL before → after |
|---|---:|---:|
| Full search «кино», guest, 20 posts | 797 → 467 | 79 → 17 |
| Full search «спорт», guest, 20 posts | 309 → 144 | 53 → 12 |
| Header query «ки», old full DTO → compact suggestions | 442 → 67 | 91 → 7 |
| Full search «кино», authenticated, 20 posts | 541 → 403 | 101 → 20 |

Compact «кино» separately took 106ms/11 SQL for a guest and 133ms/12 SQL with an
injected user. Its JSON was 6.9KB (escaped JSON bytes), versus roughly 29KB in the
original 5-post autocomplete audit. Full-page JSON can grow because newer,
correctly selected posts have different contents; no misleading payload-parity
claim is made for different selections.

For all four before/after cases, author/community results were equal. Full card
JSON was equal for every shared post (8, 16, 2, 8 shared posts respectively),
including clock-dependent views under the frozen clock. Expected new ordering is
covered independently by regression tests; complete response equality is neither
expected nor asserted after fixing selection.

EXPLAIN ANALYZE verified the actual UNION selection and hydration. The common
«кино» first-page ID query uses the existing publication-date index, the author FTS
index and author/post FK indexes; one plan took 316ms. The compact selection took
71ms. On page 6 the complete request took 1,069ms/13 SQL, and its ID query 811ms.
This is a remaining cost: PostgreSQL still computes the text vector while checking
rows for some plans. A stored vector/search read model should be the next measured
candidate if deep paging or real p95 exceeds the agreed budget. No new index or
schema migration is justified as already successful by these measurements.

## Growth and concurrent reads, isolated local database

A separate Django test generated 2,400 then 24,000 synthetic posts with 30 authors
and communities, using existing indexes, and checked the exact newest IDs. Full
and compact responses were measured sequentially and with 4 workers/8 requests.
This 10× synthetic growth check is not a production load test or a prediction for
240,000 real posts with long content and complex interactive templates.

| Synthetic rows | Sequential suggestions | Sequential full page | Four-worker observations |
|---|---:|---:|---:|
| 2,400 | 15ms / 7 SQL | 17–18ms / 8 SQL | 21–29ms per request |
| 24,000 | 21–23ms / 7 SQL | 25–29ms / 8 SQL | 27–39ms per request |

The 8-request groups completed in 58/70ms, Python CPU was about 59ms for either
batch. Process peak RSS (including fixture creation) was 126.3/126.8MB. PostgreSQL
CPU, cold disks, external storage throughput and production concurrency were not
measured. Candidate memory stays narrow and bounded by the page window; page
hydration/serialization and relation queries depend on page size, not total rows.
Database matching/sorting and deep OFFSET still depend on selectivity/data size.

## Browser checks

An isolated local QA database supplied 48 synthetic posts. Desktop and 390px mobile
checks verified: no unsolicited suggestions after navigation; 5/3/3 results after
input; Escape and keyboard clearing; three result pages; disabled next button on
the last page. Server logs confirmed one full-search fetch after SSR/hydration
following the proxy fix, and an input-driven compact request. API requests returned
200. Development hydration and unrelated authentication bootstrap warnings are
not presented as production performance measurements. No mobile LCP/INP claim.

## Release and rollback

No migrations, external search service or production configuration change is
required. Reverting the selected code restores the previous behavior. Keep the
unrelated local analytics modifications out of the release. Deploy only through
the repository playbook, then verify standard 200s and actual MISS/HIT search,
compact results, guest/auth flows, errors and server resources. Repeat the measured
scenarios; do not claim the isolated-process timings as deployed results.

Evidence: `output/search-fix-2026-09-23/` contains final comparisons/SQL plans,
reproducible diagnostic scripts, growth checks, frontend/backend tests and build
logs. SQL parameters, tokens and post contents are omitted from exported results.
