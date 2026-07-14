<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { buildComunMapUrl, type BackendComun, type BackendComunMapPoint } from '$lib/api/backend'

  export let data

  type MapTile = {
    key: string
    url: string
    x: number
    y: number
    left: number
    top: number
  }

  type MapMarker = BackendComunMapPoint & {
    x: number
    y: number
  }

  type MapCluster = {
    key: string
    x: number
    y: number
    lat: number
    lng: number
    markers: MapMarker[]
  }

  const TILE_SIZE = 256

  let comun: BackendComun | null = data?.comun ?? null
  const initialPoints: BackendComunMapPoint[] = Array.isArray(data?.points) ? data.points : []
  let points: BackendComunMapPoint[] = [...initialPoints]
  let totalPoints = Number(data?.totalPoints ?? initialPoints.length)
  let mapElement: HTMLDivElement | null = null
  let mapWidth = 1024
  let mapHeight = 560
  let resizeObserver: ResizeObserver | null = null
  let viewZoom: number | null = null
  let viewCenterLat: number | null = null
  let viewCenterLng: number | null = null
  let selectedMarkers: MapMarker[] = []
  let viewportLoadTimer: ReturnType<typeof setTimeout> | null = null
  let viewportAbortController: AbortController | null = null
  let isLoadingPoints = false
  let dragState: {
    pointerId: number
    startX: number
    startY: number
    centerX: number
    centerY: number
    moved: boolean
  } | null = null

  const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value))

  const lonToX = (lng: number, zoom: number) => ((lng + 180) / 360) * TILE_SIZE * 2 ** zoom

  const latToY = (lat: number, zoom: number) => {
    const safeLat = clamp(lat, -85.0511, 85.0511)
    const rad = (safeLat * Math.PI) / 180
    return (
      ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) *
      TILE_SIZE *
      2 ** zoom
    )
  }

  const xToLng = (x: number, zoom: number) => {
    const worldSize = TILE_SIZE * 2 ** zoom
    return ((x / worldSize) * 360 + 540) % 360 - 180
  }

  const yToLat = (y: number, zoom: number) => {
    const worldSize = TILE_SIZE * 2 ** zoom
    const mercator = Math.PI * (1 - (2 * y) / worldSize)
    return clamp((Math.atan(Math.sinh(mercator)) * 180) / Math.PI, -85.0511, 85.0511)
  }

  const normalizePoint = (point: BackendComunMapPoint) => {
    const lat = Number(point?.lat)
    const lng = Number(point?.lng)
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
    if (lat < -90 || lat > 90 || lng < -180 || lng > 180) return null
    return { ...point, lat, lng }
  }

  const formatCount = (value: number) => new Intl.NumberFormat('ru-RU').format(value)

  const mapZoomForPoints = (items: BackendComunMapPoint[]) => {
    if (items.length <= 1) return clamp(Number(items[0]?.zoom ?? 14) || 14, 4, 16)
    const latValues = items.map((point) => point.lat)
    const lngValues = items.map((point) => point.lng)
    const latSpan = Math.max(...latValues) - Math.min(...latValues)
    const lngSpan = Math.max(...lngValues) - Math.min(...lngValues)
    const span = Math.max(latSpan, lngSpan)
    if (span > 80) return 2
    if (span > 35) return 3
    if (span > 18) return 4
    if (span > 9) return 5
    if (span > 4) return 6
    if (span > 2) return 7
    if (span > 1) return 8
    if (span > 0.5) return 9
    if (span > 0.2) return 10
    if (span > 0.08) return 11
    return 12
  }

  const clusterMarkers = (items: MapMarker[], width: number, height: number): MapCluster[] => {
    const cellSize = 52
    const buckets = new Map<string, MapMarker[]>()
    for (const marker of items) {
      const cellX = Math.floor(((marker.x / 100) * width) / cellSize)
      const cellY = Math.floor(((marker.y / 100) * height) / cellSize)
      const key = `${cellX}:${cellY}`
      const bucket = buckets.get(key)
      if (bucket) bucket.push(marker)
      else buckets.set(key, [marker])
    }
    return Array.from(buckets.entries()).map(([key, clusterItems]) => ({
      key,
      x: clusterItems.reduce((sum, marker) => sum + marker.x, 0) / clusterItems.length,
      y: clusterItems.reduce((sum, marker) => sum + marker.y, 0) / clusterItems.length,
      lat: clusterItems.reduce((sum, marker) => sum + marker.lat, 0) / clusterItems.length,
      lng: clusterItems.reduce((sum, marker) => sum + marker.lng, 0) / clusterItems.length,
      markers: clusterItems,
    }))
  }

  const boundsForView = (lat: number, lng: number, zoom: number) => {
    const viewCenterX = lonToX(lng, zoom)
    const viewCenterY = latToY(lat, zoom)
    return {
      minLat: yToLat(viewCenterY + mapHeight / 2, zoom),
      maxLat: yToLat(viewCenterY - mapHeight / 2, zoom),
      minLng: xToLng(viewCenterX - mapWidth / 2, zoom),
      maxLng: xToLng(viewCenterX + mapWidth / 2, zoom),
    }
  }

  const mergePoints = (nextPoints: BackendComunMapPoint[]) => {
    const merged = new Map<number, BackendComunMapPoint>()
    for (const point of points) merged.set(Number(point.id), point)
    for (const point of nextPoints) merged.set(Number(point.id), point)
    points = Array.from(merged.values())
  }

  const loadViewportPoints = async (lat: number, lng: number, zoom: number) => {
    if (!comun?.slug || typeof window === 'undefined') return
    const bounds = boundsForView(lat, lng, zoom)
    if (bounds.minLng > bounds.maxLng) return

    viewportAbortController?.abort()
    const controller = new AbortController()
    viewportAbortController = controller
    const url = new URL(buildComunMapUrl(comun.slug), window.location.origin)
    url.searchParams.set('min_lat', String(bounds.minLat))
    url.searchParams.set('max_lat', String(bounds.maxLat))
    url.searchParams.set('min_lng', String(bounds.minLng))
    url.searchParams.set('max_lng', String(bounds.maxLng))
    url.searchParams.set('limit', '500')
    isLoadingPoints = true
    try {
      const response = await fetch(url.toString(), { signal: controller.signal })
      if (!response.ok) return
      const payload = await response.json().catch(() => ({}))
      if (Array.isArray(payload?.points)) mergePoints(payload.points)
      if (Number(payload?.total_count) > 0) totalPoints = Number(payload.total_count)
    } catch (error) {
      if ((error as Error)?.name !== 'AbortError') console.error('Failed to load map viewport', error)
    } finally {
      if (viewportAbortController === controller) isLoadingPoints = false
    }
  }

  const scheduleViewportLoad = (lat: number, lng: number, zoom: number) => {
    if (viewportLoadTimer) clearTimeout(viewportLoadTimer)
    viewportLoadTimer = setTimeout(() => loadViewportPoints(lat, lng, zoom), 180)
  }

  const setMapZoom = (nextZoom: number) => {
    const normalizedZoom = clamp(nextZoom, 2, 16)
    viewZoom = normalizedZoom
    selectedMarkers = []
    scheduleViewportLoad(centerLat, centerLng, normalizedZoom)
  }

  const focusCluster = (cluster: MapCluster) => {
    if (mapZoom < 16) {
      viewCenterLat = cluster.lat
      viewCenterLng = cluster.lng
      const nextZoom = Math.min(mapZoom + 2, 16)
      viewZoom = nextZoom
      selectedMarkers = []
      scheduleViewportLoad(cluster.lat, cluster.lng, nextZoom)
      return
    }
    const uniquePosts = new Map<number, MapMarker>()
    for (const marker of cluster.markers) uniquePosts.set(marker.post_id, marker)
    selectedMarkers = Array.from(uniquePosts.values())
  }

  const resetMapView = () => {
    points = [...initialPoints]
    viewZoom = null
    viewCenterLat = null
    viewCenterLng = null
    selectedMarkers = []
  }

  const handleMapPointerDown = (event: PointerEvent) => {
    if (event.button !== 0) return
    const target = event.target as HTMLElement | null
    if (target?.closest('a, button')) return
    const currentTarget = event.currentTarget as HTMLElement
    currentTarget.setPointerCapture(event.pointerId)
    dragState = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      centerX,
      centerY,
      moved: false,
    }
  }

  const handleMapPointerMove = (event: PointerEvent) => {
    if (!dragState || dragState.pointerId !== event.pointerId) return
    const deltaX = event.clientX - dragState.startX
    const deltaY = event.clientY - dragState.startY
    dragState.moved = dragState.moved || Math.abs(deltaX) + Math.abs(deltaY) > 4
    viewCenterLng = xToLng(dragState.centerX - deltaX, mapZoom)
    viewCenterLat = yToLat(dragState.centerY - deltaY, mapZoom)
    selectedMarkers = []
  }

  const handleMapPointerUp = (event: PointerEvent) => {
    if (!dragState || dragState.pointerId !== event.pointerId) return
    const moved = dragState.moved
    dragState = null
    const currentTarget = event.currentTarget as HTMLElement
    if (currentTarget.hasPointerCapture(event.pointerId)) currentTarget.releasePointerCapture(event.pointerId)
    if (moved) scheduleViewportLoad(centerLat, centerLng, mapZoom)
  }

  const handleMapWheel = (event: WheelEvent) => {
    event.preventDefault()
    setMapZoom(mapZoom + (event.deltaY < 0 ? 1 : -1))
  }

  $: normalizedPoints = points.map(normalizePoint).filter(Boolean) as BackendComunMapPoint[]
  $: fittedMapZoom = mapZoomForPoints(normalizedPoints)
  $: fittedCenterLat = normalizedPoints.length
    ? normalizedPoints.reduce((sum, point) => sum + point.lat, 0) / normalizedPoints.length
    : 55.751244
  $: fittedCenterLng = normalizedPoints.length
    ? normalizedPoints.reduce((sum, point) => sum + point.lng, 0) / normalizedPoints.length
    : 37.618423
  $: mapZoom = viewZoom ?? fittedMapZoom
  $: centerLat = viewCenterLat ?? fittedCenterLat
  $: centerLng = viewCenterLng ?? fittedCenterLng
  $: centerX = lonToX(centerLng, mapZoom)
  $: centerY = latToY(centerLat, mapZoom)
  $: topLeftX = centerX - mapWidth / 2
  $: topLeftY = centerY - mapHeight / 2
  $: tileMinX = Math.floor(topLeftX / TILE_SIZE)
  $: tileMaxX = Math.floor((topLeftX + mapWidth) / TILE_SIZE)
  $: tileMinY = Math.floor(topLeftY / TILE_SIZE)
  $: tileMaxY = Math.floor((topLeftY + mapHeight) / TILE_SIZE)
  $: tiles = Array.from(
    { length: Math.max(tileMaxX - tileMinX + 1, 0) * Math.max(tileMaxY - tileMinY + 1, 0) },
    (_, index): MapTile => {
      const columns = Math.max(tileMaxX - tileMinX + 1, 1)
      const x = tileMinX + (index % columns)
      const y = tileMinY + Math.floor(index / columns)
      const wrappedX = ((x % 2 ** mapZoom) + 2 ** mapZoom) % 2 ** mapZoom
      return {
        key: `${mapZoom}-${wrappedX}-${y}`,
        url: `https://tile.openstreetmap.org/${mapZoom}/${wrappedX}/${y}.png`,
        x: wrappedX,
        y,
        left: x * TILE_SIZE - topLeftX,
        top: y * TILE_SIZE - topLeftY,
      }
    }
  ).filter((tile) => tile.y >= 0 && tile.y < 2 ** mapZoom)
  $: markers = normalizedPoints.map(
    (point): MapMarker => ({
      ...point,
      x: ((lonToX(point.lng, mapZoom) - topLeftX) / mapWidth) * 100,
      y: ((latToY(point.lat, mapZoom) - topLeftY) / mapHeight) * 100,
    })
  )
  $: visibleMarkers = markers.filter(
    (marker) => marker.x >= -2 && marker.x <= 102 && marker.y >= -4 && marker.y <= 104
  )
  $: markerClusters = clusterMarkers(visibleMarkers, mapWidth, mapHeight)

  onMount(() => {
    const updateSize = () => {
      if (!mapElement) return
      const rect = mapElement.getBoundingClientRect()
      mapWidth = Math.max(Math.round(rect.width), 320)
      mapHeight = Math.max(Math.round(rect.height), 320)
    }
    updateSize()
    if (typeof ResizeObserver !== 'undefined' && mapElement) {
      resizeObserver = new ResizeObserver(updateSize)
      resizeObserver.observe(mapElement)
    }
  })

  onDestroy(() => {
    resizeObserver?.disconnect()
    if (viewportLoadTimer) clearTimeout(viewportLoadTimer)
    viewportAbortController?.abort()
  })
</script>

<svelte:head>
  <title>{comun?.name ? `${comun.name}: карта` : 'Карта сообщества'}</title>
</svelte:head>

<main class="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-4 sm:px-6 lg:px-8">
  <section class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950 sm:p-5">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
      <div class="min-w-0">
        <Header noMargin>Карта</Header>
        <div class="mt-1 text-sm text-slate-500 dark:text-zinc-400">
          {comun?.name ?? 'Сообщество'} · {formatCount(normalizedPoints.length)} из {formatCount(totalPoints || normalizedPoints.length)} меток{isLoadingPoints ? ' · загрузка' : ''}
        </div>
      </div>
      {#if comun?.slug}
        <a
          href={`/comuns/${encodeURIComponent(comun.slug)}`}
          class="inline-flex shrink-0 items-center justify-center rounded-full border border-slate-200 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-900"
        >
          К сообществу
        </a>
      {/if}
    </div>
  </section>

  {#if normalizedPoints.length}
    <section class="community-map-shell overflow-hidden rounded-2xl border border-slate-200 bg-slate-100 dark:border-zinc-800 dark:bg-zinc-900">
      <div
        class:community-map-dragging={Boolean(dragState)}
        class="community-map-canvas"
        role="application"
        aria-label="Карта сообщества"
        bind:this={mapElement}
        on:pointerdown={handleMapPointerDown}
        on:pointermove={handleMapPointerMove}
        on:pointerup={handleMapPointerUp}
        on:pointercancel={handleMapPointerUp}
        on:wheel|nonpassive={handleMapWheel}
      >
        {#each tiles as tile (tile.key)}
          <img
            src={tile.url}
            alt=""
            loading="lazy"
            draggable="false"
            class="community-map-tile"
            style={`left:${tile.left}px; top:${tile.top}px;`}
            width={TILE_SIZE}
            height={TILE_SIZE}
          />
        {/each}
        {#each markerClusters as cluster (cluster.key)}
          {#if cluster.markers.length === 1}
            <a
              href={cluster.markers[0].post_path}
              class="community-map-marker"
              style={`left:${cluster.x}%; top:${cluster.y}%;`}
              title={cluster.markers[0].post_title || cluster.markers[0].raw || 'Пост с меткой'}
              aria-label={cluster.markers[0].post_title || cluster.markers[0].raw || 'Пост с меткой'}
            >
              <span class="community-map-marker-dot"></span>
            </a>
          {:else}
            <button
              type="button"
              class="community-map-cluster"
              style={`left:${cluster.x}%; top:${cluster.y}%;`}
              title={mapZoom < 16 ? 'Приблизить область' : 'Показать посты'}
              aria-label={`${formatCount(cluster.markers.length)} меток`}
              on:click={() => focusCluster(cluster)}
            >
              {formatCount(cluster.markers.length)}
            </button>
          {/if}
        {/each}
        <div class="community-map-controls" aria-label="Управление масштабом">
          <button type="button" title="Приблизить" aria-label="Приблизить" on:click={() => setMapZoom(mapZoom + 1)}>+</button>
          <button type="button" title="Отдалить" aria-label="Отдалить" on:click={() => setMapZoom(mapZoom - 1)}>−</button>
          <button type="button" class="community-map-reset" on:click={resetMapView}>К началу</button>
        </div>
        <a
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="nofollow noopener noreferrer"
          class="community-map-attribution"
        >
          © OpenStreetMap
        </a>
      </div>
    </section>

    {#if selectedMarkers.length}
      <section class="rounded-xl border border-slate-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-950">
        <div class="mb-2 text-sm font-semibold text-slate-900 dark:text-zinc-100">
          Посты в этой точке
        </div>
        <div class="community-map-posts grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {#each selectedMarkers as point (point.post_id)}
            <a
              href={point.post_path}
              class="block rounded-lg border border-slate-200 p-3 transition hover:border-blue-300 hover:bg-blue-50/40 dark:border-zinc-800 dark:hover:border-blue-800 dark:hover:bg-blue-950/20"
            >
              <div class="truncate text-sm font-semibold text-slate-900 dark:text-zinc-100">
                {point.post_title || point.raw || 'Пост с меткой'}
              </div>
            </a>
          {/each}
        </div>
      </section>
    {/if}
  {:else}
    <section class="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
      На карте пока нет меток.
    </section>
  {/if}
</main>

<style>
  .community-map-shell {
    min-height: 360px;
  }

  .community-map-canvas {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    min-height: 360px;
    max-height: 620px;
    overflow: hidden;
    cursor: grab;
    touch-action: none;
  }

  .community-map-canvas.community-map-dragging {
    cursor: grabbing;
  }

  .community-map-tile {
    position: absolute;
    width: 256px;
    height: 256px;
    max-width: none;
    user-select: none;
  }

  .community-map-marker {
    position: absolute;
    z-index: 5;
    width: 30px;
    height: 30px;
    transform: translate(-50%, -100%);
  }

  .community-map-marker-dot {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 18px;
    height: 18px;
    transform: translate(-50%, -50%) rotate(45deg);
    border: 3px solid #fff;
    border-radius: 999px 999px 999px 0;
    background: #2563eb;
    box-shadow: 0 6px 16px rgb(15 23 42 / 0.35);
  }

  .community-map-marker:hover .community-map-marker-dot,
  .community-map-marker:focus-visible .community-map-marker-dot {
    background: #dc2626;
  }

  .community-map-cluster {
    position: absolute;
    z-index: 5;
    min-width: 38px;
    height: 38px;
    transform: translate(-50%, -50%);
    border: 3px solid rgb(255 255 255 / 0.92);
    border-radius: 999px;
    background: #2563eb;
    padding: 0 8px;
    color: #fff;
    font-size: 12px;
    font-weight: 700;
    line-height: 1;
    box-shadow: 0 5px 14px rgb(15 23 42 / 0.3);
  }

  .community-map-cluster:hover,
  .community-map-cluster:focus-visible {
    background: #1d4ed8;
  }

  .community-map-controls {
    position: absolute;
    left: 10px;
    top: 10px;
    z-index: 7;
    display: grid;
    grid-template-columns: 38px 38px auto;
    overflow: hidden;
    border: 1px solid rgb(148 163 184 / 0.55);
    border-radius: 7px;
    background: rgb(255 255 255 / 0.94);
    box-shadow: 0 4px 12px rgb(15 23 42 / 0.16);
  }

  .community-map-controls button {
    height: 38px;
    border-right: 1px solid rgb(148 163 184 / 0.45);
    color: #1e293b;
    font-size: 22px;
    font-weight: 600;
    line-height: 1;
  }

  .community-map-controls button:hover,
  .community-map-controls button:focus-visible {
    background: #f1f5f9;
  }

  .community-map-controls .community-map-reset {
    border-right: 0;
    padding: 0 10px;
    font-size: 12px;
  }

  .community-map-posts {
    max-height: 320px;
    overflow: auto;
  }

  .community-map-attribution {
    position: absolute;
    right: 8px;
    bottom: 8px;
    z-index: 6;
    border-radius: 6px;
    background: rgb(255 255 255 / 0.9);
    padding: 3px 6px;
    color: #334155;
    font-size: 11px;
    line-height: 1;
  }

  :global(.dark) .community-map-attribution {
    background: rgb(24 24 27 / 0.9);
    color: #d4d4d8;
  }

  @media (max-width: 640px) {
    .community-map-canvas {
      aspect-ratio: 1 / 1;
      min-height: 320px;
    }
  }
</style>
