<script lang="ts">
  import { onMount } from 'svelte'
  import type * as Leaflet from 'leaflet'
  import 'leaflet/dist/leaflet.css'

  export let lat: number | null = null
  export let lng: number | null = null
  export let radius: number | null = null
  export let editable = false

  let element: HTMLDivElement
  let map: Leaflet.Map | undefined
  let leaflet: typeof Leaflet | undefined
  let marker: Leaflet.CircleMarker | undefined
  let circle: Leaflet.Circle | undefined
  let failed = false
  let previousPoint = ''

  function updatePoint(latitude: number | null, longitude: number | null, meters: number | null) {
    if (!map || !leaflet) return
    if (latitude == null || longitude == null || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      marker?.remove(); marker = undefined
      circle?.remove(); circle = undefined
      return
    }
    const point: Leaflet.LatLngTuple = [latitude, longitude]
    if (!marker) marker = leaflet.circleMarker(point, { radius: 9, color: '#fff', weight: 3, fillColor: '#7c3aed', fillOpacity: 1 }).addTo(map)
    else marker.setLatLng(point)
    if (meters && meters > 0) {
      if (!circle) circle = leaflet.circle(point, { radius: meters, color: '#7c3aed', weight: 2, fillOpacity: 0.12 }).addTo(map)
      else circle.setLatLng(point).setRadius(meters)
    } else { circle?.remove(); circle = undefined }
    const pointKey = `${latitude},${longitude}`
    if (pointKey !== previousPoint) {
      if (!previousPoint && circle) map.fitBounds(circle.getBounds(), { padding: [20, 20], maxZoom: 15 })
      else map.panTo(point)
      previousPoint = pointKey
    }
  }
  $: updatePoint(lat, lng, radius)

  onMount(() => {
    let disposed = false
    let observer: ResizeObserver | undefined
    import('leaflet').then((module) => {
      if (disposed) return
      leaflet = module
      map = leaflet.map(element, { scrollWheelZoom: false }).setView([lat ?? 55.7558, lng ?? 37.6176], lat == null ? 10 : 14)
      leaflet.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
      }).addTo(map)
      if (editable) map.on('click', (event: Leaflet.LeafletMouseEvent) => {
        lat = Math.max(-85, Math.min(85, event.latlng.lat))
        lng = event.latlng.wrap().lng
      })
      updatePoint(lat, lng, radius)
      observer = new ResizeObserver(() => map?.invalidateSize())
      observer.observe(element)
    }).catch(() => { failed = true })
    return () => { disposed = true; observer?.disconnect(); map?.remove() }
  })
</script>

<div class="relative isolate overflow-hidden rounded-xl border border-slate-200 dark:border-zinc-700">
  <div bind:this={element} class="h-64 w-full bg-slate-100" role="region" aria-label={editable ? 'Выберите место встречи на карте' : 'Место встречи'}></div>
  {#if failed}<p class="p-3 text-sm">Карта не загрузилась. Можно указать координаты вручную.</p>{/if}
</div>
