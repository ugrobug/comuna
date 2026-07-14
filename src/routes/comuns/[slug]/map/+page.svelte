<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { buildComunMapUrl, type BackendComun, type BackendComunMapPoint } from '$lib/api/backend'
  import { Icon, MagnifyingGlass, XMark } from 'svelte-hero-icons'

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
  let selectedPoint: BackendComunMapPoint | null = null
  let mapSearchQuery = ''
  let searchResults: BackendComunMapPoint[] = []
  let isSearching = false
  let completedSearchQuery = ''
  let searchTimer: ReturnType<typeof setTimeout> | null = null
  let searchAbortController: AbortController | null = null
  let viewportLoadTimer: ReturnType<typeof setTimeout> | null = null
  let viewportAbortController: AbortController | null = null
  let suppressMarkerClickUntil = 0
  let isLoadingPoints = false
  let dragState: {
    pointerId: number
    startX: number
    startY: number
    centerX: number
    centerY: number
    zoom: number
    lastLat: number
    lastLng: number
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
    const wrappedX = ((x % worldSize) + worldSize) % worldSize
    return (wrappedX / worldSize) * 360 - 180
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

  const formatPostDate = (value?: string | null) => {
    if (!value) return ''
    const date = new Date(value)
    if (!Number.isFinite(date.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date)
  }

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

  const searchMapPoints = async () => {
    const query = mapSearchQuery.trim()
    if (!comun?.slug || query.length < 2 || typeof window === 'undefined') {
      searchResults = []
      return
    }

    searchAbortController?.abort()
    const controller = new AbortController()
    searchAbortController = controller
    const url = new URL(buildComunMapUrl(comun.slug), window.location.origin)
    url.searchParams.set('q', query)
    url.searchParams.set('limit', '30')
    isSearching = true
    try {
      const response = await fetch(url.toString(), { signal: controller.signal })
      if (!response.ok) return
      const payload = await response.json().catch(() => ({}))
      searchResults = Array.isArray(payload?.points) ? payload.points : []
      completedSearchQuery = query
    } catch (error) {
      if ((error as Error)?.name !== 'AbortError') console.error('Failed to search map points', error)
    } finally {
      if (searchAbortController === controller) isSearching = false
    }
  }

  const handleSearchInput = () => {
    if (searchTimer) clearTimeout(searchTimer)
    completedSearchQuery = ''
    if (mapSearchQuery.trim().length < 2) {
      searchAbortController?.abort()
      searchResults = []
      isSearching = false
      return
    }
    searchTimer = setTimeout(searchMapPoints, 280)
  }

  const selectMapPoint = (point: BackendComunMapPoint) => {
    const lat = Number(point.lat)
    const lng = Number(point.lng)
    if (!Number.isFinite(lat) || !Number.isFinite(lng)) return
    mergePoints([point])
    selectedPoint = point
    selectedMarkers = []
    mapSearchQuery = point.post_title || point.raw || mapSearchQuery
    searchResults = []
    viewCenterLat = lat
    viewCenterLng = lng
    const nextZoom = clamp(Number(point.zoom ?? 14) || 14, 12, 16)
    viewZoom = nextZoom
    scheduleViewportLoad(lat, lng, nextZoom)
  }

  const submitMapSearch = () => {
    if (searchResults.length) selectMapPoint(searchResults[0])
    else searchMapPoints()
  }

  const clearMapSearch = () => {
    mapSearchQuery = ''
    searchResults = []
    completedSearchQuery = ''
    searchAbortController?.abort()
    isSearching = false
  }

  const setMapZoom = (nextZoom: number) => {
    const normalizedZoom = clamp(nextZoom, 2, 16)
    const currentLat = centerLat
    const currentLng = centerLng
    viewCenterLat = currentLat
    viewCenterLng = currentLng
    viewZoom = normalizedZoom
    selectedMarkers = []
    selectedPoint = null
    scheduleViewportLoad(currentLat, currentLng, normalizedZoom)
  }

  const focusCluster = (cluster: MapCluster) => {
    if (mapZoom < 16) {
      viewCenterLat = cluster.lat
      viewCenterLng = cluster.lng
      const nextZoom = Math.min(mapZoom + 2, 16)
      viewZoom = nextZoom
      selectedMarkers = []
      selectedPoint = null
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
    selectedPoint = null
  }

  const handleMapPointerDown = (event: PointerEvent) => {
    if (event.button !== 0) return
    const target = event.target as HTMLElement | null
    if (target?.closest('.community-map-controls, .community-map-popup, .community-map-attribution')) return
    dragState = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      centerX,
      centerY,
      zoom: mapZoom,
      lastLat: centerLat,
      lastLng: centerLng,
      moved: false,
    }
  }

  const handleMapPointerMove = (event: PointerEvent) => {
    if (!dragState || dragState.pointerId !== event.pointerId) return
    const deltaX = event.clientX - dragState.startX
    const deltaY = event.clientY - dragState.startY
    dragState.moved = dragState.moved || Math.abs(deltaX) + Math.abs(deltaY) > 4
    dragState.lastLng = xToLng(dragState.centerX - deltaX, dragState.zoom)
    dragState.lastLat = yToLat(dragState.centerY - deltaY, dragState.zoom)
    viewCenterLng = dragState.lastLng
    viewCenterLat = dragState.lastLat
    if (dragState.moved) {
      const currentTarget = event.currentTarget as HTMLElement
      if (!currentTarget.hasPointerCapture(event.pointerId)) currentTarget.setPointerCapture(event.pointerId)
      suppressMarkerClickUntil = Date.now() + 250
    }
    selectedMarkers = []
    selectedPoint = null
  }

  const handleMapPointerUp = (event: PointerEvent) => {
    if (!dragState || dragState.pointerId !== event.pointerId) return
    const completedDrag = dragState
    dragState = null
    const currentTarget = event.currentTarget as HTMLElement
    if (currentTarget.hasPointerCapture(event.pointerId)) currentTarget.releasePointerCapture(event.pointerId)
    if (completedDrag.moved) {
      scheduleViewportLoad(completedDrag.lastLat, completedDrag.lastLng, completedDrag.zoom)
    }
  }

  const openMarker = (point: BackendComunMapPoint) => {
    if (Date.now() >= suppressMarkerClickUntil) selectedPoint = point
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
  $: selectedMapMarker = selectedPoint
    ? markers.find((marker) => marker.id === selectedPoint?.id) ?? null
    : null

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
    if (searchTimer) clearTimeout(searchTimer)
    searchAbortController?.abort()
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

  <section class="community-map-search relative z-20">
    <form class="relative" on:submit|preventDefault={submitMapSearch}>
      <span class="community-map-search-icon" aria-hidden="true">
        <Icon src={MagnifyingGlass} size="20" mini />
      </span>
      <input
        type="search"
        bind:value={mapSearchQuery}
        on:input={handleSearchInput}
        placeholder="Поиск по объектам карты"
        aria-label="Поиск по объектам карты"
        autocomplete="off"
        class="community-map-search-input"
      />
      {#if mapSearchQuery}
        <button
          type="button"
          class="community-map-search-clear"
          title="Очистить поиск"
          aria-label="Очистить поиск"
          on:click={clearMapSearch}
        >
          <Icon src={XMark} size="18" mini />
        </button>
      {/if}
    </form>

    {#if mapSearchQuery.trim().length >= 2 && (isSearching || searchResults.length || completedSearchQuery === mapSearchQuery.trim())}
      <div class="community-map-search-results">
        {#if isSearching && !searchResults.length}
          <div class="community-map-search-status">Ищем...</div>
        {:else if !searchResults.length}
          <div class="community-map-search-status">Ничего не найдено</div>
        {:else}
          {#each searchResults.slice(0, 10) as result (result.id)}
            <button type="button" class="community-map-search-result" on:click={() => selectMapPoint(result)}>
              {#if result.preview_image_url}
                <img src={result.preview_image_url} alt="" loading="lazy" />
              {:else}
                <span class="community-map-search-placeholder">
                  <Icon src={MagnifyingGlass} size="18" mini />
                </span>
              {/if}
              <span class="min-w-0 text-left">
                <span class="block truncate text-sm font-semibold text-slate-900 dark:text-zinc-100">
                  {result.post_title || result.raw || 'Точка на карте'}
                </span>
                <span class="mt-0.5 block truncate text-xs text-slate-500 dark:text-zinc-400">
                  {result.raw || `${Number(result.lat).toFixed(5)}, ${Number(result.lng).toFixed(5)}`}
                </span>
              </span>
            </button>
          {/each}
        {/if}
      </div>
    {/if}
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
            <button
              type="button"
              class="community-map-marker"
              style={`left:${cluster.x}%; top:${cluster.y}%;`}
              title={cluster.markers[0].post_title || cluster.markers[0].raw || 'Пост с меткой'}
              aria-label={cluster.markers[0].post_title || cluster.markers[0].raw || 'Пост с меткой'}
              on:click={() => openMarker(cluster.markers[0])}
            >
              <span class="community-map-marker-dot"></span>
            </button>
          {:else}
            <button
              type="button"
              class="community-map-cluster"
              style={`left:${cluster.x}%; top:${cluster.y}%;`}
              title={mapZoom < 16 ? 'Приблизить область' : 'Показать посты'}
              aria-label={`${formatCount(cluster.markers.length)} меток`}
              on:click={() => Date.now() >= suppressMarkerClickUntil && focusCluster(cluster)}
            >
              {formatCount(cluster.markers.length)}
            </button>
          {/if}
        {/each}
        {#if selectedMapMarker}
          <article
            class:community-map-popup-below={selectedMapMarker.y < 46}
            class="community-map-popup"
            style={`left:${clamp(selectedMapMarker.x, 18, 82)}%; top:${clamp(selectedMapMarker.y, 8, 92)}%;`}
          >
            <button
              type="button"
              class="community-map-popup-close"
              title="Закрыть"
              aria-label="Закрыть"
              on:click={() => (selectedPoint = null)}
            >
              <Icon src={XMark} size="18" mini />
            </button>
            {#if selectedMapMarker.raw}
              <div class="community-map-popup-location">{selectedMapMarker.raw}</div>
            {/if}
            {#if selectedMapMarker.preview_image_url}
              <img
                src={selectedMapMarker.preview_image_url}
                alt={selectedMapMarker.post_title || 'Фотография места'}
                loading="lazy"
                class="community-map-popup-image"
              />
            {/if}
            <h2 class="community-map-popup-title">
              {selectedMapMarker.post_title || 'Точка на карте'}
            </h2>
            <div class="community-map-popup-meta">
              {#if formatPostDate(selectedMapMarker.created_at)}
                <span>{formatPostDate(selectedMapMarker.created_at)}</span>
              {/if}
              <span>{selectedMapMarker.lat.toFixed(5)}, {selectedMapMarker.lng.toFixed(5)}</span>
            </div>
            <a href={selectedMapMarker.post_path} class="community-map-popup-link">Открыть пост</a>
          </article>
        {/if}
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
  .community-map-search-input {
    width: 100%;
    height: 46px;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    background: #fff;
    padding: 0 46px;
    color: #0f172a;
    font-size: 15px;
    outline: none;
    box-shadow: 0 2px 8px rgb(15 23 42 / 0.06);
  }

  .community-map-search-input:focus {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgb(37 99 235 / 0.14);
  }

  .community-map-search-icon,
  .community-map-search-clear {
    position: absolute;
    top: 50%;
    z-index: 2;
    display: grid;
    width: 38px;
    height: 38px;
    transform: translateY(-50%);
    place-items: center;
    color: #64748b;
  }

  .community-map-search-icon {
    left: 5px;
    pointer-events: none;
  }

  .community-map-search-clear {
    right: 5px;
    border: 0;
    background: transparent;
  }

  .community-map-search-clear:hover,
  .community-map-search-clear:focus-visible {
    color: #0f172a;
  }

  .community-map-search-results {
    position: absolute;
    left: 0;
    right: 0;
    top: calc(100% + 6px);
    overflow: hidden;
    max-height: 430px;
    overflow-y: auto;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    background: #fff;
    box-shadow: 0 14px 32px rgb(15 23 42 / 0.18);
  }

  .community-map-search-result {
    display: grid;
    width: 100%;
    grid-template-columns: 48px minmax(0, 1fr);
    align-items: center;
    gap: 10px;
    border: 0;
    border-bottom: 1px solid #e2e8f0;
    background: transparent;
    padding: 8px 10px;
  }

  .community-map-search-result:last-child {
    border-bottom: 0;
  }

  .community-map-search-result:hover,
  .community-map-search-result:focus-visible {
    background: #f8fafc;
  }

  .community-map-search-result img,
  .community-map-search-placeholder {
    width: 48px;
    height: 48px;
    border-radius: 6px;
  }

  .community-map-search-result img {
    object-fit: cover;
  }

  .community-map-search-placeholder {
    display: grid;
    place-items: center;
    background: #e2e8f0;
    color: #64748b;
  }

  .community-map-search-status {
    padding: 14px;
    color: #64748b;
    font-size: 14px;
  }

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
    pointer-events: none;
    user-select: none;
  }

  .community-map-marker {
    position: absolute;
    z-index: 5;
    width: 30px;
    height: 30px;
    transform: translate(-50%, -100%);
    border: 0;
    background: transparent;
    padding: 0;
  }

  .community-map-marker-dot {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 18px;
    height: 18px;
    transform: translate(-50%, -50%) rotate(-45deg);
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

  .community-map-popup {
    position: absolute;
    z-index: 9;
    width: min(360px, calc(100% - 24px));
    transform: translate(-50%, calc(-100% - 22px));
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background: #fff;
    padding: 14px;
    color: #0f172a;
    box-shadow: 0 18px 45px rgb(15 23 42 / 0.28);
  }

  .community-map-popup::after {
    position: absolute;
    left: 50%;
    bottom: -9px;
    width: 18px;
    height: 18px;
    transform: translateX(-50%) rotate(45deg);
    border-right: 1px solid #e2e8f0;
    border-bottom: 1px solid #e2e8f0;
    background: #fff;
    content: '';
  }

  .community-map-popup.community-map-popup-below {
    transform: translate(-50%, 24px);
  }

  .community-map-popup.community-map-popup-below::after {
    top: -9px;
    bottom: auto;
    transform: translateX(-50%) rotate(225deg);
  }

  .community-map-popup-close {
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 2;
    display: grid;
    width: 32px;
    height: 32px;
    place-items: center;
    border: 0;
    border-radius: 6px;
    background: rgb(255 255 255 / 0.9);
    color: #475569;
  }

  .community-map-popup-close:hover,
  .community-map-popup-close:focus-visible {
    background: #f1f5f9;
    color: #0f172a;
  }

  .community-map-popup-location {
    padding-right: 34px;
    color: #2563eb;
    font-size: 13px;
    font-weight: 700;
    line-height: 1.35;
  }

  .community-map-popup-image {
    width: 100%;
    margin-top: 10px;
    aspect-ratio: 16 / 9;
    border-radius: 6px;
    object-fit: cover;
  }

  .community-map-popup-title {
    margin-top: 10px;
    padding-right: 24px;
    color: #0f172a;
    font-size: 17px;
    font-weight: 700;
    line-height: 1.3;
  }

  .community-map-popup-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 10px;
    margin-top: 7px;
    color: #64748b;
    font-size: 12px;
  }

  .community-map-popup-link {
    position: relative;
    z-index: 1;
    display: inline-flex;
    margin-top: 12px;
    color: #0369a1;
    font-size: 14px;
    font-weight: 700;
  }

  .community-map-popup-link:hover,
  .community-map-popup-link:focus-visible {
    color: #075985;
    text-decoration: underline;
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

  :global(.dark) .community-map-search-input,
  :global(.dark) .community-map-search-results,
  :global(.dark) .community-map-popup,
  :global(.dark) .community-map-popup::after {
    border-color: #3f3f46;
    background: #18181b;
    color: #f4f4f5;
  }

  :global(.dark) .community-map-search-result {
    border-color: #27272a;
  }

  :global(.dark) .community-map-search-result:hover,
  :global(.dark) .community-map-search-result:focus-visible,
  :global(.dark) .community-map-popup-close:hover,
  :global(.dark) .community-map-popup-close:focus-visible {
    background: #27272a;
  }

  :global(.dark) .community-map-search-placeholder,
  :global(.dark) .community-map-popup-close {
    background: #27272a;
    color: #a1a1aa;
  }

  :global(.dark) .community-map-popup-title {
    color: #f4f4f5;
  }

  @media (max-width: 640px) {
    .community-map-canvas {
      aspect-ratio: 1 / 1;
      min-height: 320px;
    }

    .community-map-popup {
      width: min(310px, calc(100% - 20px));
      padding: 12px;
    }

    .community-map-popup-title {
      font-size: 15px;
    }
  }
</style>
