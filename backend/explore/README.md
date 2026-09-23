# Explore

`explore` is an independent Django app with its own tables and migrations. Public UI:
`/explore` (including staff-only inline editing); `/moderator/explore` redirects there; API: `/api/explore/`.

## Domain and write boundary

- `Node` represents either an interest element or one existing `feeds.Comun`.
  A community has one graph node. Deleting its graph node does not delete the community.
- `Edge` points from a parent element to a child element/community. Multiple parents
  are allowed (Motorcycles → Pitbike ← Tourism). Any pair of node kinds can be linked,
  including communities. Community/element selections are normalized to element →
  community regardless of selection order. Cycles are allowed; traversal uses a visited
  set. Self-links and duplicate pairs (including reversed pairs) are rejected.
- `PropertyDefinition` / `PropertyOption` provide the fixed five-property catalog.
  `Node.properties` is a many-to-many relation: every property allows multiple values.
  `show_properties` controls display only, never matching. No inherited properties.
- `Subscription` follows an element; community subscriptions reuse `UserFeedSettings`,
  existing counters and subscription events.

All moderator writes go through `GraphEditor.apply()`: one transaction and a shared
`GraphState` row lock protect duplicate validation and notification snapshots. The
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

Framework-independent `GraphLayout` uses ELK force layout followed by compact spiral packing of measured
node/title/property rectangles. Straight edges and unconstrained positions keep the
graph organic, while the initial packing prevents node and label overlaps. The browser runs the layout in a worker before showing the
graph. Layout generations prevent stale filter results from replacing the current graph.
Manual dragging is unconstrained; fixed positions
survive filtering. The “Упорядочить” button restores automatic placement. The Svelte SVG
component handles dragging, panning, zooming, keyboard selection and neighborhood emphasis.
Dragging an interest moves the grabbed node immediately; directly connected visible
nodes follow damped springs in either edge direction. Springs pull stretched links but
go slack when compressed, so approaching a category cannot launch it outward to restore
an old link length. Link lengths and angles can change while moving; neighbors settle
after release. Moving followers repel each other and
the dragged node using their full label bounds. Unrelated nodes remain freely positioned. Springs yield at contact so a crowded
group spreads and comes to rest without pulling its labels back into a pile. Further neighbors stay still, communities
can be dragged individually, and moved positions remain manual. Animation stops on a
new gesture, layout rebuild or unmount.
Two-finger gestures on the graph zoom around the moving finger midpoint and pan the
graph without scaling the page. Starting a pinch cancels node dragging; lifting a finger
does not select or jump a node. The mobile workspace fills the dynamic viewport below
navigation. Cards are constrained to the visible viewport independently of graph zoom,
with internal scrolling for long descriptions and short/landscape screens.
Selecting a node opens a docked card with its optional description and subscription
actions. Community cards use the current community description and subscriber count;
subscription responses refresh the displayed count. Interest cards link to community creation with the name prefilled; guests
authenticate first and then continue to that form. New graph connections remain manual.
Pinned nodes form a temporary collection that can be highlighted together without
locking selection. Filters apply OR inside each property, AND between different properties,
and AND with title/description search. Missing properties do not match active filters.

The initial migration seeds only the five example interests from the feature request;
all further content and community connections are managed manually. No community
is created automatically or assigned inferred properties.

## Card images

Staff upload/replace or delete a node cover at `/api/explore/nodes/<id>/image/`
(multipart POST with `image`, or DELETE). `NodeImageService` accepts JPEG, PNG,
WebP and GIF up to 10 MiB / 25 megapixels. It applies EXIF orientation, center-crops
to 16:9 at up to 640×360 without upscaling, removes metadata, and stores only a
static WebP with quality 75. GIF uses its first frame. Images are optional for both
interests and community nodes. Replaced/deleted files are removed after transaction
commit; failed database writes remove the newly stored file instead.

The moderator form saves pending node edits before uploading and previews the
processed file. The graph response contains only image URLs; image elements are
created only inside the selected node's card, never for graph circles or pinned lists.

## Verification

```
.venv/bin/python backend/manage.py test explore --noinput
npm test -- --run src/lib/explore/explore.test.ts
.venv/bin/python backend/manage.py makemigrations --check --dry-run
npm run build
```

Deployment requires `python manage.py migrate` and the normal nginx restart.

### Inline moderation

Site staff enable “Редактировать граф” on `/explore`. The managed graph includes hidden
nodes (dashed circles). Clicking a node opens its form; clicking a line edits its endpoints.
The overlay creates interests and nodes for existing communities, edits properties/images,
and creates, updates or removes links. Endpoints can be searched or picked on the graph.
Drafts save before switching nodes or exiting; failed validation keeps the current draft.
The editor collapses while picking endpoints so the graph stays accessible on mobile.
All mutations and managed reads require `is_staff` on the server, including edge PATCH;
edge replacement uses the same atomic graph lock, validation and notification boundary.
