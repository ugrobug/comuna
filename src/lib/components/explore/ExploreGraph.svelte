<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import { NodePopover, type PopoverBounds } from '$lib/explore/NodePopover'
  import { focusNodes } from '$lib/explore/GraphSelection'
  import MobileNodeCard from './MobileNodeCard.svelte'
  import { GraphPinch } from '$lib/explore/GraphPinch'
  import { GraphDrag } from '$lib/explore/GraphDrag'
  import ELK from 'elkjs/lib/elk-api'
  import elkWorkerUrl from 'elkjs/lib/elk-worker.min.js?url'
  import { GraphLayout, graphTitle, nodeSize, edgeCoordinates, edgePath, type Coordinate, type GraphPoint } from '$lib/explore/GraphLayout'
  import type { ExploreNode, ExploreEdge, ExploreProperty } from '$lib/explore/types'
  export let nodes: ExploreNode[] = []
  export let edges: ExploreEdge[] = []
  export let properties: ExploreProperty[] = []
  export let selected: number | null = null
  export let highlightedPins: number[] = []
  export let showProperties = false
  export let filtersOpen = false
  export let focusOnly = false
  export let editable = false
  const dispatch = createEventDispatcher<{ select: number; dismiss: void; editEdge: ExploreEdge }>()
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
  const pointers = new Map<number, Coordinate>()
  let pinch: GraphPinch | null = null
  let visibleViewport: PopoverBounds | undefined
  let drag: { id: number | null; group: GraphDrag | null; x: number; y: number; moved: boolean; startX: number; startY: number } | null = null
  let spring: GraphDrag | null = null
  let springFrame = 0, springTime = 0
  let suppressClick = false
  let signature = ''
  $: cardTop = width > 700 ? 100 : 125
  $: activePoint = points.find(point => point.id === selected)
  $: cardBounds = NodePopover.bounds({ width, height }, cardTop, 10, visibleViewport)
  $: cardWidth = Math.min(340, cardBounds.width)
  $: cardHeight = width > 700 ? cardBounds.height : Math.min(340, height * .44, cardBounds.height)
  $: cardPosition = { x: width > 700 ? cardBounds.x + cardBounds.width - cardWidth : cardBounds.x,
    y: width > 700 ? cardBounds.y : cardBounds.y + cardBounds.height - cardHeight }
  $: selectionArea = {
    x: width > 1050 && filtersOpen ? 370 : cardBounds.x,
    y: cardBounds.y,
    width: Math.max(80, (width > 700 ? cardPosition.x - 20 : cardBounds.x + cardBounds.width) - (width > 1050 && filtersOpen ? 370 : cardBounds.x)),
    height: Math.max(60, (width > 700 ? cardBounds.height : cardPosition.y - cardBounds.y - 16)) }
  function measureViewport() {
    const rect = canvas.getBoundingClientRect(), viewport = window.visualViewport
    const x = Math.max(0, (viewport?.offsetLeft ?? 0) - rect.left)
    const y = Math.max(0, (viewport?.offsetTop ?? 0) - rect.top)
    visibleViewport = { x, y,
      width: Math.max(0, Math.min(rect.width, (viewport?.offsetLeft ?? 0) + (viewport?.width ?? window.innerWidth) - rect.left) - x),
      height: Math.max(0, Math.min(rect.height, (viewport?.offsetTop ?? 0) + (viewport?.height ?? window.innerHeight) - rect.top) - y) }
  }
  $: nextSignature = JSON.stringify([nodes.map(node => [node.id, node.kind, node.title, node.show_properties, node.property_ids]), edges, showProperties, properties, width <= 700])
  $: if (ready && signature !== nextSignature) { signature = nextSignature; void rebuild() }
  $: if (ready && !arranging) { filtersOpen; width; height; selectionArea; if (highlightedPins.length) focusPinned(); else if (selected !== null) focusSelected(); else fit() }
  $: byId = new Map(points.map(point => [point.id, point]))
  $: nodeById = new Map(nodes.map(node => [node.id, node]))
  $: selectedIds = new Set(selected === null ? highlightedPins : [selected])
  $: hasSelection = selectedIds.size > 0
  $: neighbors = new Set(edges.flatMap(edge => [
    ...(selectedIds.has(edge.source) ? [edge.target] : []),
    ...(selectedIds.has(edge.target) ? [edge.source] : []),
  ]))
  $: labels = new Map(properties.flatMap(property => property.options.map(option => [option.id, option.label] as const)))

  function propertyText(node: ExploreNode) {
    return showProperties && node.show_properties ? node.property_ids.slice(0, 2).map(id => labels.get(id)).filter(Boolean).join(' · ') : ''
  }
  async function rebuild(preserveManual = true) {
    stopSprings()
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
  function focusSelected(includeNeighbors = false) {
    const target = points.find(point => point.id === selected)
    if (!target) return
    stopSprings()
    if (includeNeighbors) {
      const view = focusNodes(points.filter(point => point.id === selected || neighbors.has(point.id)), selectionArea)
      if (view) ({ scale, tx, ty } = view)
    } else {
      const view = focusNodes([target], selectionArea)
      if (!view) return
      scale = Math.min(view.scale, Math.max(.65, Math.min(1.25, scale)))
      tx = selectionArea.x + selectionArea.width / 2 - target.x * scale
      ty = selectionArea.y + selectionArea.height / 2 - (target.y - target.anchorY + target.height / 2) * scale
    }
  }
  function focusPinned() {
    stopSprings()
    const view = focusNodes(points.filter(point => highlightedPins.includes(point.id)), selectionArea)
    if (view) ({ scale, tx, ty } = view)
  }
  function zoom(factor: number) {
    const next = Math.max(.03, Math.min(3, scale * factor))
    tx = width / 2 - (width / 2 - tx) * next / scale; ty = height / 2 - (height / 2 - ty) * next / scale; scale = next
  }
  function point(event: PointerEvent) {
    return new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM()!.inverse())
  }
  function stopSprings() {
    if (springFrame) cancelAnimationFrame(springFrame)
    springFrame = 0; spring = null
  }
  function stepSprings(time: number) {
    springFrame = 0
    if (!spring || !ready || arranging) return
    // A callback queued within a frame can precede performance.now() from that frame.
    const result = spring.step(points, Math.max(1 / 240, (time - springTime) / 1000))
    springTime = time; points = result.points
    if (result.moving) springFrame = requestAnimationFrame(stepSprings)
    else spring = null
  }
  function follow(group: GraphDrag) {
    spring = group
    if (!springFrame) { springTime = performance.now(); springFrame = requestAnimationFrame(stepSprings) }
  }
  function start(event: PointerEvent, id: number | null = null) {
    if (event.button !== 0 || arranging || layoutError) return
    event.stopPropagation()
    stopSprings()
    svg.setPointerCapture(event.pointerId)
    const p = point(event)
    pointers.set(event.pointerId, p)
    if (pointers.size >= 2) {
      const [a, b] = [...pointers.values()]
      pinch = new GraphPinch(a, b, { scale, tx, ty })
      drag = null; suppressClick = true
      return
    }
    suppressClick = false
    drag = { id, group: id === null ? null : new GraphDrag(nodeById.get(id)!, edges, points), x: p.x, y: p.y, startX: p.x, startY: p.y, moved: false }
  }
  function move(event: PointerEvent) {
    if (!pointers.has(event.pointerId)) return
    pointers.set(event.pointerId, point(event))
    if (pinch) {
      const [a, b] = [...pointers.values()]
      if (a && b) ({ scale, tx, ty } = pinch.move(a, b))
      return
    }
    if (!drag) return
    const p = point(event), dx = p.x - drag.x, dy = p.y - drag.y
    if (Math.hypot(p.x - drag.startX, p.y - drag.startY) > 3) drag.moved = true
    if (!drag.moved) return
    if (drag.id === null) { tx += dx; ty += dy }
    else if (drag.group) {
      points = drag.group.move(points, dx / scale, dy / scale)
      follow(drag.group)
    }
    drag.x = p.x; drag.y = p.y
  }
  function stop(event: PointerEvent) {
    if (!pointers.delete(event.pointerId)) return
    if (drag) {
      suppressClick = drag.moved || event.type !== 'pointerup'
      if (!suppressClick && drag.id !== null) dispatch('select', drag.id)
      if (!suppressClick && drag.id === null) dispatch('dismiss')
    }
    drag = null
    const [a, b] = [...pointers.values()]
    pinch = a && b ? new GraphPinch(a, b, { scale, tx, ty }) : null
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId)
  }
  function select(id: number) { if (!suppressClick) dispatch('select', id) }
  onMount(() => {
    engine = new ELK({ workerUrl: elkWorkerUrl })
    layout = new GraphLayout(engine)
    observer = new ResizeObserver(([entry]) => { width = entry.contentRect.width; height = entry.contentRect.height; measureViewport() })
    observer.observe(canvas)
    window.visualViewport?.addEventListener('resize', measureViewport)
    window.visualViewport?.addEventListener('scroll', measureViewport)
    window.addEventListener('scroll', measureViewport, true)
    ready = true
    return () => {
      window.visualViewport?.removeEventListener('resize', measureViewport)
      window.visualViewport?.removeEventListener('scroll', measureViewport)
      window.removeEventListener('scroll', measureViewport, true)
    }
  })
  onDestroy(() => { stopSprings(); ready = false; generation++; observer?.disconnect(); engine?.terminateWorker() })
</script>

<svelte:window on:keydown={(event) => { if (event.key === 'Escape' && hasSelection) dispatch('dismiss') }} />

<div class="graph-canvas" bind:this={canvas}>
  {#if arranging}<p class="layout-status" role="status">Раскладываем граф…</p>{:else if layoutError}<div class="layout-status" role="alert">{layoutError} <button on:click={() => rebuild()}>Повторить</button></div>{/if}
  <div class="legend"><span><i class="element"></i>Увлечение</span><span><i class="community"></i>Сообщество</span></div>
  <svg bind:this={svg} viewBox={`0 0 ${width} ${height}`} class:pending={arranging || Boolean(layoutError)} aria-hidden={arranging || Boolean(layoutError)} aria-label="Граф увлечений: выберите узел, перетащите его или переместите поле" role="group"
    on:pointerdown={(event) => start(event)} on:pointermove={move} on:pointerup={stop} on:pointercancel={stop} on:lostpointercapture={stop}
    on:touchstart|nonpassive={(event) => { if (event.touches.length > 1) event.preventDefault() }}
    on:touchmove|nonpassive={(event) => { if (event.touches.length > 1) event.preventDefault() }}
    on:wheel|nonpassive|preventDefault={(event) => zoom(event.deltaY < 0 ? 1.08 : 1 / 1.08)}>
    <g transform={`translate(${tx},${ty}) scale(${scale})`}>
      {#each edges as edge (edge.id)}
        <path d={edgePath(edgeCoordinates(edge, byId, routes))} class:connected={selectedIds.has(edge.source) || selectedIds.has(edge.target)} class:muted={hasSelection && !selectedIds.has(edge.source) && !selectedIds.has(edge.target)} class:concealed={focusOnly && hasSelection && !selectedIds.has(edge.source) && !selectedIds.has(edge.target)} />
        {#if editable}
          <path class="edge-hit" d={edgePath(edgeCoordinates(edge, byId, routes))} role="button" tabindex="0" aria-label={`Изменить связь: ${nodeById.get(edge.source)?.title} — ${nodeById.get(edge.target)?.title}`}
            on:pointerdown|stopPropagation on:click|stopPropagation={() => dispatch('editEdge', edge)} on:keydown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); dispatch('editEdge', edge) } }} />
        {/if}
      {/each}
      {#each points as p (p.id)}
        {@const node = nodeById.get(p.id)!}
        <g transform={`translate(${p.x},${p.y})`} role="button" tabindex={focusOnly && hasSelection && !selectedIds.has(p.id) && !neighbors.has(p.id) ? -1 : 0} aria-hidden={focusOnly && hasSelection && !selectedIds.has(p.id) && !neighbors.has(p.id)} aria-label={`${node.title}, ${node.kind === 'community' ? 'сообщество' : 'элемент'}`} aria-pressed={selectedIds.has(p.id)}
          class="node" class:hidden-node={!node.is_active} class:concealed={focusOnly && hasSelection && !selectedIds.has(p.id) && !neighbors.has(p.id)} class:selected={selectedIds.has(p.id)} class:neighbor={neighbors.has(p.id)} class:muted={hasSelection && !selectedIds.has(p.id) && !neighbors.has(p.id)}
          on:pointerdown={(event) => start(event, p.id)} on:click={() => select(p.id)} on:keydown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); dispatch('select', p.id) } }}>
          <circle class="halo" r={node.kind === 'community' ? 24 : 23.8} />
          <circle class:community={node.kind === 'community'} class="core" r={node.kind === 'community' ? 11 : 14.7} />
          {#if node.subscribed}<circle cx={node.kind === 'community' ? 15 : 11} cy={node.kind === 'community' ? -14 : -10} r="5" fill="#22a88a" stroke="white" stroke-width="2" />{/if}
          <text y={node.kind === 'community' ? 32 : 43} text-anchor="middle">{graphTitle(node.title)}</text>
          <title>{node.title}{!node.is_active ? ' · скрыт от посетителей' : ''}</title>
          {#if showProperties && node.show_properties && node.property_ids.length}
            <text class="property-label" y={node.kind === 'community' ? 48 : 59} text-anchor="middle">{propertyText(node)}</text>
          {/if}
        </g>
      {/each}
    </g>
  </svg>
  {#if !editable && (activePoint || highlightedPins.length) && !arranging && !layoutError}
    {#key selected}
    {#if width <= 700 && activePoint}
      <MobileNodeCard label={nodeById.get(activePoint.id)?.kind === 'community' ? 'Карточка сообщества' : 'Карточка увлечения'} on:dismiss={() => dispatch('dismiss')}><slot /></MobileNodeCard>
    {:else}
    <section class="node-inspector" aria-label={highlightedPins.length ? 'Зафиксированные узлы' : 'Выбранное увлечение или сообщество'} style:left={`${cardPosition.x}px`} style:top={`${cardPosition.y}px`} style:width={`${width > 700 ? cardWidth : cardBounds.width}px`} style:max-height={`${cardHeight}px`} style:height={width > 700 ? undefined : `${cardHeight}px`}>
      <slot />
    </section>
    {/if}
    {/key}
  {/if}
  <div class="controls"><button aria-label="Уменьшить граф" on:click={() => zoom(1 / 1.2)}>−</button><span>{Math.round(scale * 100)}%</span><button aria-label="Увеличить граф" on:click={() => zoom(1.2)}>+</button>{#if selected !== null}<button on:click={() => focusSelected(true)}>Показать связи</button>{/if}<button on:click={() => { dispatch('dismiss'); fit() }}>Весь граф</button><button disabled={arranging} on:click={() => rebuild(false)}>Упорядочить</button></div>
  <p class="hint">Выбирайте точки, чтобы изучать связи · перетаскивайте поле</p>
</div>

<style>
  path.edge-hit{stroke:transparent;stroke-width:16;vector-effect:non-scaling-stroke;pointer-events:stroke;cursor:pointer}path.edge-hit:hover,path.edge-hit:focus-visible{stroke:#8174ce44;stroke-width:8;outline:none}.node.hidden-node .core{stroke-dasharray:3 3;fill-opacity:.45}
  .node-inspector{overscroll-behavior:contain;position:absolute;z-index:2;width:320px;max-width:calc(100% - 20px);box-sizing:border-box;overflow:auto;padding:16px;border:1px solid #b2b8ca60;border-radius:16px;background:var(--explore-surface,#fff);box-shadow:0 10px 32px #30375124;color:var(--explore-ink,#35405a)}
  .pending{visibility:hidden}.layout-status{position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);font-size:13px;color:#8174ce}.controls button:disabled{opacity:.5;cursor:wait}
  .graph-canvas{position:relative;min-width:0;height:100%;min-height:0;background-color:var(--explore-canvas,#f6f7fb);background-image:radial-gradient(#b9c2d340 .9px,transparent .9px);background-size:22px 22px;overflow:hidden}svg{display:block;width:100%;height:100%;min-height:0;touch-action:none;cursor:grab}svg:active{cursor:grabbing}path{fill:none;stroke-linejoin:round;stroke:#c6cedc;stroke-width:1.4;transition:stroke .2s}path.connected{stroke:#8174ce;stroke-width:1.25;vector-effect:non-scaling-stroke}path.muted{opacity:.16}.concealed{visibility:hidden;pointer-events:none}.node{cursor:pointer;outline:none;transition:opacity .2s}.node.muted{opacity:.22}.halo{fill:transparent;stroke:transparent;stroke-width:1.5}.node.selected .halo,.node:focus-visible .halo{fill:#8174ce28;stroke:#8174ce;stroke-width:3;vector-effect:non-scaling-stroke}.node.selected text{font-weight:750}.node:focus-visible .halo{stroke-dasharray:4 3}.node.neighbor .halo{fill:#8174ce0c}.core{fill:#8174ce;stroke:#e6e1f9;stroke-width:2.8}.core.community{fill:#dc9b50;stroke:#f7e8d6;stroke-width:3}.node.selected .core{fill:#6555b4}.node.selected .core.community{fill:#c4883c}text{font:500 13px system-ui;fill:var(--explore-ink,#35405a);paint-order:stroke;stroke:var(--explore-canvas,#f6f7fb);stroke-width:4px;stroke-linejoin:round}.property-label{font-size:10px;fill:#788398}.legend{position:absolute;bottom:48px;left:20px;display:flex;gap:18px;font-size:11px;color:#7a8295;pointer-events:none}.legend span{display:flex;align-items:center;gap:7px}i{width:8px;height:8px;border-radius:50%}.element{background:#8174ce}.community{background:#dc9b50}.controls{position:absolute;bottom:20px;right:20px;display:flex;align-items:center;gap:8px;border:1px solid #dce1ea;border-radius:12px;background:var(--explore-surface,#fff);padding:5px;color:var(--explore-ink,#35405a)}button{border:0;background:transparent;font-size:13px;padding:7px;cursor:pointer}button:hover{background:#8174ce15;border-radius:8px}.controls span{font-size:10px;min-width:34px;text-align:center}.hint{position:absolute;bottom:22px;left:20px;font-size:10px;color:#8b94a5;pointer-events:none}@media(max-width:700px){text{font-size:13px}.property-label{font-size:10px}.hint{display:none}.graph-canvas,svg{min-height:0}.controls{right:10px;left:10px;bottom:16px;justify-content:center;gap:2px}.controls button{font-size:11px;padding:6px}.legend{max-width:calc(100% - 24px)}.legend{left:12px;top:130px;bottom:auto;gap:12px}}
</style>
