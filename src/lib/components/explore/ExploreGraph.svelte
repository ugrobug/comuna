<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte'
  import { GraphLayout, type GraphPoint } from '$lib/explore/GraphLayout'
  import type { ExploreNode, ExploreEdge, ExploreProperty } from '$lib/explore/types'
  export let nodes: ExploreNode[] = []
  export let edges: ExploreEdge[] = []
  export let properties: ExploreProperty[] = []
  export let selected: number | null = null
  export let showProperties = false
  const dispatch = createEventDispatcher<{ select: number }>()
  let svg: SVGSVGElement
  let layout: GraphLayout | null = null
  let points: GraphPoint[] = []
  let frame = 0
  let ready = false
  let scale = 1, tx = 0, ty = 0
  let drag: { id: number | null; x: number; y: number; moved: boolean } | null = null
  let suppressClick = false
  let signature = ''
  $: nextSignature = nodes.map(node => node.id).join(',') + ':' + edges.map(edge => `${edge.source}-${edge.target}`).join(',')
  $: if (ready && signature !== nextSignature) { signature = nextSignature; rebuild() }
  $: byId = new Map(points.map(point => [point.id, point]))
  $: nodeById = new Map(nodes.map(node => [node.id, node]))
  $: neighbors = new Set(edges.flatMap(edge => edge.source === selected ? [edge.target] : edge.target === selected ? [edge.source] : []))
  $: labels = new Map(properties.flatMap(property => property.options.map(option => [option.id, option.label] as const)))

  function rebuild() {
    cancelAnimationFrame(frame)
    layout = new GraphLayout(nodes, edges, points)
    // Settle offscreen first to avoid a distracting initial burst.
    for (let i = 0; i < 100; i++) layout.step()
    points = [...layout.points]
    fit()
    animate()
  }
  function animate() {
    if (!layout) return
    const running = layout.step()
    points = [...layout.points]
    if (running) frame = requestAnimationFrame(animate)
  }
  function fit() {
    if (!points.length) { scale = 1; tx = 0; ty = 0; return }
    const xs = points.map(p => p.x), ys = points.map(p => p.y)
    const minX = Math.min(...xs) - 110, maxX = Math.max(...xs) + 110
    const minY = Math.min(...ys) - 70, maxY = Math.max(...ys) + 90
    scale = Math.min(1.5, 940 / (maxX - minX), 580 / (maxY - minY))
    tx = 500 - (minX + maxX) / 2 * scale; ty = 325 - (minY + maxY) / 2 * scale
  }
  function zoom(factor: number) {
    const next = Math.max(.15, Math.min(3, scale * factor))
    tx = 500 - (500 - tx) * next / scale; ty = 325 - (325 - ty) * next / scale; scale = next
  }
  function point(event: PointerEvent) {
    return new DOMPoint(event.clientX, event.clientY).matrixTransform(svg.getScreenCTM()!.inverse())
  }
  function start(event: PointerEvent, id: number | null = null) {
    if (event.button !== 0) return
    event.stopPropagation()
    svg.setPointerCapture(event.pointerId)
    const p = point(event)
    drag = { id, x: p.x, y: p.y, moved: false }
    if (id !== null) { const node = byId.get(id); if (node) node.fixed = true }
  }
  function move(event: PointerEvent) {
    if (!drag) return
    const p = point(event), dx = p.x - drag.x, dy = p.y - drag.y
    if (Math.abs(dx) + Math.abs(dy) > 2) drag.moved = true
    if (drag.id === null) { tx += dx; ty += dy }
    else {
      const node = byId.get(drag.id)
      if (node) { node.x += dx / scale; node.y += dy / scale; points = [...points] }
    }
    drag.x = p.x; drag.y = p.y
  }
  function stop(event: PointerEvent) {
    if (!drag) return
    suppressClick = drag.moved
    if (drag.id !== null && !drag.moved) dispatch('select', drag.id)
    drag = null
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId)
  }
  function select(id: number) { if (!suppressClick) dispatch('select', id); suppressClick = false }
  onMount(() => { ready = true })
  onDestroy(() => cancelAnimationFrame(frame))
</script>

<div class="graph-canvas">
  <div class="legend"><span><i class="element"></i>Увлечение</span><span><i class="community"></i>Сообщество</span></div>
  <svg bind:this={svg} viewBox="0 0 1000 650" aria-label="Граф увлечений: выберите узел, перетащите его или переместите поле" role="group"
    on:pointerdown={(event) => start(event)} on:pointermove={move} on:pointerup={stop} on:pointercancel={stop}
    on:wheel|nonpassive|preventDefault={(event) => zoom(event.deltaY < 0 ? 1.08 : 1 / 1.08)}>
    <g transform={`translate(${tx},${ty}) scale(${scale})`}>
      {#each edges as edge (edge.id)}
        {@const a = byId.get(edge.source)}{@const b = byId.get(edge.target)}
        {#if a && b}<line x1={a.x} y1={a.y} x2={b.x} y2={b.y} class:connected={edge.source === selected || edge.target === selected} />{/if}
      {/each}
      {#each points as p (p.id)}
        {@const node = nodeById.get(p.id)!}
        <g transform={`translate(${p.x},${p.y})`} role="button" tabindex="0" aria-label={`${node.title}, ${node.kind === 'community' ? 'сообщество' : 'элемент'}`} aria-pressed={selected === p.id}
          class="node" class:selected={selected === p.id} class:neighbor={neighbors.has(p.id)} class:muted={selected !== null && selected !== p.id && !neighbors.has(p.id)}
          on:pointerdown={(event) => start(event, p.id)} on:click={() => select(p.id)} on:keydown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); dispatch('select', p.id) } }}>
          <circle class="halo" r={node.kind === 'community' ? 24 : 34} />
          <circle class:community={node.kind === 'community'} class="core" r={node.kind === 'community' ? 11 : 21} />
          {#if node.subscribed}<circle cx="15" cy="-14" r="5" fill="#22a88a" stroke="white" stroke-width="2" />{/if}
          <text y={node.kind === 'community' ? 32 : 43} text-anchor="middle">{node.title.length > 30 ? node.title.slice(0, 29) + '…' : node.title}</text>
          <title>{node.title}</title>
          {#if showProperties && node.show_properties && node.property_ids.length}
            <text class="property-label" y={node.kind === 'community' ? 48 : 59} text-anchor="middle">{node.property_ids.slice(0, 2).map(id => labels.get(id)).join(' · ')}</text>
          {/if}
        </g>
      {/each}
    </g>
  </svg>
  <div class="controls"><button aria-label="Уменьшить граф" on:click={() => zoom(1 / 1.2)}>−</button><span>{Math.round(scale * 100)}%</span><button aria-label="Увеличить граф" on:click={() => zoom(1.2)}>+</button><button on:click={fit}>Весь граф</button></div>
  <p class="hint">Перетаскивайте узлы и поле · прокрутка меняет масштаб</p>
</div>

<style>
  .graph-canvas{position:relative;min-width:0;height:100%;min-height:480px;background-color:var(--explore-canvas,#f6f7fb);background-image:radial-gradient(#b9c2d340 .9px,transparent .9px);background-size:22px 22px;border-radius:20px;overflow:hidden}svg{width:100%;height:100%;min-height:480px;touch-action:none;cursor:grab}svg:active{cursor:grabbing}line{stroke:#c6cedc;stroke-width:1.4;transition:stroke .2s}line.connected{stroke:#8174ce;stroke-width:2.2}.node{cursor:pointer;outline:none;transition:opacity .2s}.node.muted{opacity:.4}.halo{fill:transparent;stroke:transparent;stroke-width:1.5}.node.selected .halo,.node:focus .halo{fill:#8174ce18;stroke:#9284d1}.node.neighbor .halo{fill:#8174ce0c}.core{fill:#8174ce;stroke:#e6e1f9;stroke-width:4}.core.community{fill:#dc9b50;stroke:#f7e8d6;stroke-width:3}.node.selected .core{fill:#6555b4}.node.selected .core.community{fill:#c4883c}text{font:500 13px system-ui;fill:var(--explore-ink,#35405a);paint-order:stroke;stroke:var(--explore-canvas,#f6f7fb);stroke-width:4px;stroke-linejoin:round}.property-label{font-size:10px;fill:#788398}.legend{position:absolute;top:18px;left:20px;display:flex;gap:18px;font-size:11px;color:#7a8295;pointer-events:none}.legend span{display:flex;align-items:center;gap:7px}i{width:8px;height:8px;border-radius:50%}.element{background:#8174ce}.community{background:#dc9b50}.controls{position:absolute;bottom:20px;right:20px;display:flex;align-items:center;gap:8px;border:1px solid #dce1ea;border-radius:12px;background:var(--explore-surface,#fff);padding:5px;color:var(--explore-ink,#35405a)}button{border:0;background:transparent;font-size:13px;padding:7px;cursor:pointer}button:hover{background:#8174ce15;border-radius:8px}.controls span{font-size:10px;min-width:34px;text-align:center}.hint{position:absolute;bottom:22px;left:20px;font-size:10px;color:#8b94a5;pointer-events:none}@media(max-width:700px){text{font-size:22px}.property-label{font-size:17px}.hint{display:none}.graph-canvas,svg{min-height:430px}.controls{right:10px;bottom:10px}.legend{left:12px;gap:12px}}
</style>
