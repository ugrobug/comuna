<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import { NodePopover } from '$lib/explore/NodePopover'
  import { GraphDrag } from '$lib/explore/GraphDrag'
  import ELK from 'elkjs/lib/elk-api'
  import elkWorkerUrl from 'elkjs/lib/elk-worker.min.js?url'
  import { GraphLayout, graphTitle, nodeSize, edgeCoordinates, edgePath, type Coordinate, type GraphPoint } from '$lib/explore/GraphLayout'
  import type { ExploreNode, ExploreEdge, ExploreProperty } from '$lib/explore/types'
  export let nodes: ExploreNode[] = []
  export let edges: ExploreEdge[] = []
  export let properties: ExploreProperty[] = []
  export let selected: number | null = null
  export let showProperties = false
  export let filtersOpen = false
  const dispatch = createEventDispatcher<{ select: number; dismiss: void }>()
  let svg: SVGSVGElement
  let canvas: HTMLDivElement
  let engine: InstanceType<typeof ELK>
  let observer: ResizeObserver
  let width = 1000, height = 650
  let arranging = true, layoutError = '', generation = 0
  let routes = new Map<number, Coordinate[]>()
  let layout: GraphLayout | null = null
  let points: GraphPoint[] = []
  let ready = false
  let scale = 1, tx = 0, ty = 0
  let drag: { id: number | null; group: GraphDrag | null; x: number; y: number; moved: boolean; startX: number; startY: number } | null = null
  let suppressClick = false
  let signature = ''
  let cardWidth = 320, cardHeight = 220
  $: cardTop = width > 700 ? 100 : 155
  $: cardLeft = width > 700 && filtersOpen ? Math.min(370, width - 340) : 10
  $: activePoint = points.find(point => point.id === selected)
  $: cardPosition = NodePopover.place({ x: (activePoint?.x ?? 0) * scale + tx, y: (activePoint?.y ?? 0) * scale + ty }, { width: cardWidth, height: cardHeight }, { width, height }, 24 * scale, cardTop, cardLeft)
  function measureCard(element: HTMLElement) {
    const resize = new ResizeObserver(() => { cardWidth = element.offsetWidth; cardHeight = element.offsetHeight })
    resize.observe(element)
    return { destroy: () => resize.disconnect() }
  }
  $: nextSignature = JSON.stringify([nodes.map(node => [node.id, node.kind, node.title, node.show_properties, node.property_ids]), edges, showProperties, properties, width <= 700])
  $: if (ready && signature !== nextSignature) { signature = nextSignature; void rebuild() }
  $: if (ready && !arranging) { filtersOpen; width; height; fit() }
  $: byId = new Map(points.map(point => [point.id, point]))
  $: nodeById = new Map(nodes.map(node => [node.id, node]))
  $: neighbors = new Set(edges.flatMap(edge => edge.source === selected ? [edge.target] : edge.target === selected ? [edge.source] : []))
  $: labels = new Map(properties.flatMap(property => property.options.map(option => [option.id, option.label] as const)))

  function propertyText(node: ExploreNode) {
    return showProperties && node.show_properties ? node.property_ids.slice(0, 2).map(id => labels.get(id)).filter(Boolean).join(' · ') : ''
  }
  async function rebuild(preserveManual = true) {
    const request = ++generation
    arranging = true; layoutError = ''
    try {
      const context = document.createElement('canvas').getContext('2d')
      if (context) context.font = '500 13px system-ui'
      const sizes = new Map(nodes.map(node => [node.id, nodeSize(node, text => context?.measureText(text).width ?? text.length * 10, propertyText(node))]))
      const drawing = await layout!.arrange(nodes, edges, sizes, preserveManual ? points : [], width <= 700 ? 'DOWN' : 'RIGHT')
      if (!ready || request !== generation) return
      points = drawing.points; routes = drawing.routes
      arranging = false
      fit()
    } catch {
      if (ready && request === generation) { layoutError = 'Не удалось разложить граф.'; arranging = false }
    }
  }
  function fit() {
    if (!points.length) { scale = 1; tx = 0; ty = 0; return }
    const currentPoints = new Map(points.map(point => [point.id, point]))
    const coordinates = edges.flatMap(edge => edgeCoordinates(edge, currentPoints, routes))
    const minX = Math.min(...points.map(p => p.x - p.width / 2), ...coordinates.map(p => p.x)) - 20
    const maxX = Math.max(...points.map(p => p.x + p.width / 2), ...coordinates.map(p => p.x)) + 20
    const minY = Math.min(...points.map(p => p.y - p.anchorY), ...coordinates.map(p => p.y)) - 20
    const maxY = Math.max(...points.map(p => p.y - p.anchorY + p.height), ...coordinates.map(p => p.y)) + 20
    const left = width > 700 && filtersOpen ? 370 : 20
    const top = width > 700 ? 100 : 155, bottom = 70
    const availableWidth = Math.max(100, width - left - 20), availableHeight = Math.max(100, height - top - bottom)
    scale = Math.min(1.5, availableWidth / (maxX - minX), availableHeight / (maxY - minY))
    tx = left + availableWidth / 2 - (minX + maxX) / 2 * scale
    ty = top + availableHeight / 2 - (minY + maxY) / 2 * scale
  }
  function zoom(factor: number) {
    const next = Math.max(.03, Math.min(3, scale * factor))
    tx = width / 2 - (width / 2 - tx) * next / scale; ty = height / 2 - (height / 2 - ty) * next / scale; scale = next
  }
  function point(event: PointerEvent) {
    return new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM()!.inverse())
  }
  function start(event: PointerEvent, id: number | null = null) {
    if (event.button !== 0 || arranging || layoutError) return
    event.stopPropagation()
    svg.setPointerCapture(event.pointerId)
    const p = point(event)
    drag = { id, group: id === null ? null : new GraphDrag(nodeById.get(id)!, edges), x: p.x, y: p.y, startX: p.x, startY: p.y, moved: false }
  }
  function move(event: PointerEvent) {
    if (!drag) return
    const p = point(event), dx = p.x - drag.x, dy = p.y - drag.y
    if (Math.hypot(p.x - drag.startX, p.y - drag.startY) > 3) drag.moved = true
    if (!drag.moved) return
    if (drag.id === null) { tx += dx; ty += dy }
    else if (drag.group) points = drag.group.move(points, dx / scale, dy / scale)
    drag.x = p.x; drag.y = p.y
  }
  function stop(event: PointerEvent) {
    if (!drag) return
    suppressClick = drag.moved
    if (drag.id !== null && !drag.moved) dispatch('select', drag.id)
    if (drag.id === null && !drag.moved) dispatch('dismiss')
    drag = null
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId)
  }
  function select(id: number) { if (!suppressClick) dispatch('select', id); suppressClick = false }
  onMount(() => {
    engine = new ELK({ workerUrl: elkWorkerUrl })
    layout = new GraphLayout(engine)
    observer = new ResizeObserver(([entry]) => { width = entry.contentRect.width; height = entry.contentRect.height })
    observer.observe(canvas)
    ready = true
  })
  onDestroy(() => { ready = false; generation++; observer?.disconnect(); engine?.terminateWorker() })
</script>

<svelte:window on:keydown={(event) => { if (event.key === 'Escape' && selected !== null) dispatch('dismiss') }} />

<div class="graph-canvas" bind:this={canvas}>
  {#if arranging}<p class="layout-status" role="status">Раскладываем граф…</p>{:else if layoutError}<div class="layout-status" role="alert">{layoutError} <button on:click={() => rebuild()}>Повторить</button></div>{/if}
  <div class="legend"><span><i class="element"></i>Увлечение</span><span><i class="community"></i>Сообщество</span></div>
  <svg bind:this={svg} viewBox={`0 0 ${width} ${height}`} class:pending={arranging || Boolean(layoutError)} aria-hidden={arranging || Boolean(layoutError)} aria-label="Граф увлечений: выберите узел, перетащите его или переместите поле" role="group"
    on:pointerdown={(event) => start(event)} on:pointermove={move} on:pointerup={stop} on:pointercancel={stop}
    on:wheel|nonpassive|preventDefault={(event) => zoom(event.deltaY < 0 ? 1.08 : 1 / 1.08)}>
    <g transform={`translate(${tx},${ty}) scale(${scale})`}>
      {#each edges as edge (edge.id)}
        <path d={edgePath(edgeCoordinates(edge, byId, routes))} class:connected={edge.source === selected || edge.target === selected} />
      {/each}
      {#each points as p (p.id)}
        {@const node = nodeById.get(p.id)!}
        <g transform={`translate(${p.x},${p.y})`} role="button" tabindex="0" aria-label={`${node.title}, ${node.kind === 'community' ? 'сообщество' : 'элемент'}`} aria-pressed={selected === p.id}
          class="node" class:selected={selected === p.id} class:neighbor={neighbors.has(p.id)} class:muted={selected !== null && selected !== p.id && !neighbors.has(p.id)}
          on:pointerdown={(event) => start(event, p.id)} on:click={() => select(p.id)} on:keydown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); dispatch('select', p.id) } }}>
          <circle class="halo" r={node.kind === 'community' ? 24 : 23.8} />
          <circle class:community={node.kind === 'community'} class="core" r={node.kind === 'community' ? 11 : 14.7} />
          {#if node.subscribed}<circle cx={node.kind === 'community' ? 15 : 11} cy={node.kind === 'community' ? -14 : -10} r="5" fill="#22a88a" stroke="white" stroke-width="2" />{/if}
          <text y={node.kind === 'community' ? 32 : 43} text-anchor="middle">{graphTitle(node.title)}</text>
          <title>{node.title}</title>
          {#if showProperties && node.show_properties && node.property_ids.length}
            <text class="property-label" y={node.kind === 'community' ? 48 : 59} text-anchor="middle">{propertyText(node)}</text>
          {/if}
        </g>
      {/each}
    </g>
  </svg>
  {#if activePoint && !arranging && !layoutError}
    <section class="node-popover" aria-label="Действия с выбранным узлом" use:measureCard style:left={`${cardPosition.x}px`} style:top={`${cardPosition.y}px`} style:max-height={`${Math.max(100, height - cardTop - 80)}px`}>
      <slot />
    </section>
  {/if}
  <div class="controls"><button aria-label="Уменьшить граф" on:click={() => zoom(1 / 1.2)}>−</button><span>{Math.round(scale * 100)}%</span><button aria-label="Увеличить граф" on:click={() => zoom(1.2)}>+</button><button on:click={fit}>Весь граф</button><button disabled={arranging} on:click={() => rebuild(false)}>Упорядочить</button></div>
  <p class="hint">Перетаскивайте узлы и поле · прокрутка меняет масштаб</p>
</div>

<style>
  .node-popover{position:absolute;z-index:2;width:320px;max-width:calc(100% - 20px);box-sizing:border-box;overflow:auto;padding:16px;border:1px solid #b2b8ca60;border-radius:16px;background:var(--explore-surface,#fff);box-shadow:0 10px 32px #30375124;color:var(--explore-ink,#35405a)}
  .pending{visibility:hidden}.layout-status{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:13px;color:#8174ce}.controls button:disabled{opacity:.5;cursor:wait}
  .graph-canvas{position:relative;min-width:0;height:100%;min-height:0;background-color:var(--explore-canvas,#f6f7fb);background-image:radial-gradient(#b9c2d340 .9px,transparent .9px);background-size:22px 22px;overflow:hidden}svg{display:block;width:100%;height:100%;min-height:0;touch-action:none;cursor:grab}svg:active{cursor:grabbing}path{fill:none;stroke-linejoin:round;stroke:#c6cedc;stroke-width:1.4;transition:stroke .2s}path.connected{stroke:#8174ce;stroke-width:2.2}.node{cursor:pointer;outline:none;transition:opacity .2s}.node.muted{opacity:.4}.halo{fill:transparent;stroke:transparent;stroke-width:1.5}.node.selected .halo,.node:focus .halo{fill:#8174ce18;stroke:#9284d1}.node.neighbor .halo{fill:#8174ce0c}.core{fill:#8174ce;stroke:#e6e1f9;stroke-width:2.8}.core.community{fill:#dc9b50;stroke:#f7e8d6;stroke-width:3}.node.selected .core{fill:#6555b4}.node.selected .core.community{fill:#c4883c}text{font:500 13px system-ui;fill:var(--explore-ink,#35405a);paint-order:stroke;stroke:var(--explore-canvas,#f6f7fb);stroke-width:4px;stroke-linejoin:round}.property-label{font-size:10px;fill:#788398}.legend{position:absolute;bottom:48px;left:20px;display:flex;gap:18px;font-size:11px;color:#7a8295;pointer-events:none}.legend span{display:flex;align-items:center;gap:7px}i{width:8px;height:8px;border-radius:50%}.element{background:#8174ce}.community{background:#dc9b50}.controls{position:absolute;bottom:20px;right:20px;display:flex;align-items:center;gap:8px;border:1px solid #dce1ea;border-radius:12px;background:var(--explore-surface,#fff);padding:5px;color:var(--explore-ink,#35405a)}button{border:0;background:transparent;font-size:13px;padding:7px;cursor:pointer}button:hover{background:#8174ce15;border-radius:8px}.controls span{font-size:10px;min-width:34px;text-align:center}.hint{position:absolute;bottom:22px;left:20px;font-size:10px;color:#8b94a5;pointer-events:none}@media(max-width:700px){text{font-size:13px}.property-label{font-size:10px}.hint{display:none}.graph-canvas,svg{min-height:0}.controls{right:10px;bottom:10px}.legend{left:12px;top:130px;bottom:auto;gap:12px}}
</style>
