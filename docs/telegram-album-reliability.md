# Telegram photo albums: delivery and persistence

Incident: post 23710 stored one photo (Telegram message 245), while the public
album at https://t.me/blogmanikgirl/242 contains four messages, 242–245. Production
uses polling, not a webhook. Historical polling errors from before the previous
container replacement are unavailable, so the precise network/exception event
that lost the first three messages cannot be established retrospectively.

Confirmed failure paths:

- A failed photo download returned `None`. A photo-only message then returned
  successfully without saving anything; a caption could be saved without its photo.
- The polling offset advanced before its handler completed, so exceptions skipped
  the failed update on the next request.
- Polling startup explicitly discarded pending updates.
- The album author lock was a lazy, unevaluated QuerySet. First-row creation was
  also outside the album transaction, allowing concurrent first photos to split.

## Implementation and boundaries

`TelegramUpdateProcessor` owns the offset and dispatches one bounded Telegram batch
sequentially. It advances only after successful processing and ignores already
processed IDs when replaying a batch. Startup keeps pending updates. Exception
logs contain the exception type, not payloads, URLs or tokens.

Missing downloaded photos raise `TelegramMediaDownloadError` before any post
write. Existing HTTP download attempts/timeouts remain bounded. A failure keeps
the polling cursor at that message and retries after the existing two-second
delay. This is not a durable inbox: a persistent failure delays later updates,
and Telegram's update retention still applies. A durable inbox with deferred
per-message retries is a separate architecture change, not claimed here.

`TelegramChannelPostWriter` owns post creation/merging and tags in one transaction.
An evaluated author row lock protects both the absent-album case and appends.
Network downloads, channel refresh and bot notifications stay outside this lock.
Different authors can proceed concurrently. Existing approval, delay and visibility
remain intact. Message IDs provide image ordering and replay deduplication, while
legacy file-ID deduplication is retained.

Recovery from a public album may supply local images without Bot API file IDs.
Such galleries mark `gallery_file_ids_complete=false` and keep the legacy file-ID
list empty, preventing the image rehydrator from replacing a complete gallery
with the one historically known file. Message IDs still deduplicate retries.

## Verification and cost

74 tests passed across Telegram integration, Telegram text and post preview images.
New regressions cover four-photo albums, missing downloads with/without captions,
offset replay, startup preservation, approval/delay, reordered photos, recovered
galleries and four simultaneous first photos using PostgreSQL connections.
The ten-photo append query count remains constant per image (under 30 queries).

Isolated local DB, Telegram/network operations mocked; complete handler observations:

| Album | Before | After |
|---|---|---|
| 4 photos | 36.5ms / 91 SQL | 29.4ms / 92 SQL |
| 10 photos | 77.5ms / 214 SQL | 69.3ms / 224 SQL |

These are individual observations, not network latency or production p95. The
added row lock costs one query per image; no additional external requests or
workers are introduced. Ten-photo work grows with image count, not total posts.
Existing author/FK indexes bound album lookup to the channel's posts. Very large
channel histories may warrant a measured `(author_id, media_group_id)` index later.

No migrations. Rollback: revert code; additive JSON fields are backward compatible.
Specific post recovery must back up the original row, check it did not change
while downloading, and preserve post ID, comments, votes and publication state.
