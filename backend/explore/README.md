# Explore

`explore` is an independent Django app with its own tables and migrations. Public UI:
`/explore`; site moderator UI: `/moderator/explore`; API: `/api/explore/`.

## Domain and write boundary

- `Node` represents either an interest element or one existing `feeds.Comun`.
  A community has one graph node. Deleting its graph node does not delete the community.
- `Edge` points from a parent element to a child element/community. Multiple parents
  are allowed (Motorcycles → Pitbike ← Tourism); self-links, duplicate links,
  community parents and directed cycles are rejected.
- `PropertyDefinition` / `PropertyOption` provide the fixed five-property catalog.
  `Node.properties` is a many-to-many relation: every property allows multiple values.
  `show_properties` controls display only, never matching. No inherited properties.
- `Subscription` follows an element; community subscriptions reuse `UserFeedSettings`,
  existing counters and subscription events.

All moderator writes go through `GraphEditor.apply()`: one transaction and a shared
`GraphState` row lock protect cycle validation and notification snapshots. The
moderator UI is the write interface; no alternative editable Django admin bypasses
this service. `GraphQuery` supplies graph reads and descendant traversal;
`SubscriptionService` handles subscriptions; class-based views handle authentication
and HTTP. Site moderator (`is_staff`) is required, not merely community moderator.

`GraphNotifications` compares reachable communities before/after a graph change and
creates an existing site notification for subscribers of affected elements/ancestors.
Notifications are deduplicated per user/community across multiple paths and subscriptions.
Existing communities are not announced upon subscribing, nor on cosmetic edits.
Removing and later restoring a branch can announce it again. Disabled community/node
branches do not participate. Notifications are in-site only and honor the site preference.

## UI

Framework-independent `GraphLayout` owns the deterministic force layout. The Svelte SVG
component handles dragging, panning, zooming, keyboard selection and neighborhood emphasis.
A list view offers the same subscription/navigation actions without requiring spatial
navigation. Filters apply OR inside each property, AND between different properties,
and AND with title/description search. Missing properties do not match active filters.

The initial migration seeds only the five example interests from the feature request;
all further content and community connections are managed manually. No community
is created automatically or assigned inferred properties.

## Verification

```
.venv/bin/python backend/manage.py test explore --noinput
npm test -- --run src/lib/explore/explore.test.ts
.venv/bin/python backend/manage.py makemigrations --check --dry-run
npm run build
```

Deployment requires `python manage.py migrate` and the normal nginx restart.
