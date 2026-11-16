<script lang="ts">
  import { onMount, tick } from 'svelte'
  import type { ExploreData, ExploreNode } from '$lib/explore/types'
  import { HobbyDeck, HobbyHistory } from '$lib/explore/HobbyDeck'
  import { HobbySteps } from '$lib/explore/HobbySteps'
  import HobbyFirstStep from './HobbyFirstStep.svelte'
  import { connectedNodes } from '$lib/explore/GraphSelection'
  import { ExploreApi } from '$lib/explore/api'

  export let data: ExploreData
  export let account: number | null
  export let suspended: boolean
  export let busy: number | null
  export let error: string
  export let onClose: () => void
  export let subscribe: (node: ExploreNode) => void
  export let createCommunity: (title: string) => void

  const api = new ExploreApi()
  let dialog: HTMLDialogElement, pane: HTMLElement
  let mounted = false, scope: string, deck: HobbyDeck
  let card: ExploreNode | null = null, match: ExploreNode | null = null
  let intro = true, exporting = false, exportError = ''
  let steps: HobbySteps
  let remaining = 0
  let picks: ExploreNode[] = [], saved = false, confirming = false
  let pointer: { id: number; x: number; y: number } | null = null, offset = 0
  onMount(() => { mounted = true; return () => { dialog?.close() } })
  function initialize(user: number | null) {
    scope = 'tambur:hobby-picks:v1:' + (user ?? 'guest')
    let storage: Storage | undefined
    try { storage = window.localStorage } catch { /* private mode */ }
    steps = new HobbySteps(scope, storage)
    intro = true; match = null; exportError = ''
    deck = new HobbyDeck(data.nodes, new HobbyHistory(scope, storage))
    card = deck.next(); remaining = deck.remaining; picks = deck.picked
    saved = false; confirming = false
  }
  $: if (mounted && scope !== 'tambur:hobby-picks:v1:' + (account ?? 'guest')) initialize(account)
  $: if (mounted && dialog) {
    if (suspended && dialog.open) dialog.close()
    else if (!suspended && !dialog.open) dialog.showModal()
  }
  $: communities = match ? connectedNodes(match.id, data.nodes, data.edges).filter(n => n.kind === 'community' && n.is_active) : []
  $: selectedOptions = new Set(card?.property_ids)
  $: characteristics = data.properties.map(property => ({
    id: property.id, name: property.name,
    values: property.options.filter(option => selectedOptions.has(option.id)).map(option => option.label),
  })).filter(group => group.values.length)
  async function top() { await tick(); if (pane) pane.scrollTop = 0 }
  async function exportPicks() {
    if (exporting || !picks.length) return
    exporting = true; exportError = ''
    try {
      const { HobbyPdf } = await import('$lib/explore/HobbyPdf')
      await new HobbyPdf(data, steps).download(picks)
    } catch { exportError = 'Не удалось скачать PDF. Попробуйте ещё раз.' }
    finally { exporting = false }
  }
  function choose(like: boolean) {
    if (!card || match || saved || !deck.choose(card.id, like)) return
    match = like ? card : null; card = deck.next(); remaining = deck.remaining; picks = deck.picked
    pointer = null; offset = 0; void top()
  }
  function advance() { match = null; confirming = false; void top() }
  function reset() { deck.reset(); picks = []; card = deck.next(); remaining = deck.remaining; saved = false; advance() }
  function start(e: PointerEvent) {
    if ((e.target as Element).closest('label, input, button, a') || pointer || !e.isPrimary || e.button !== 0) return
    pointer = { id: e.pointerId, x: e.clientX, y: e.clientY }
    ;(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
  }
  function move(e: PointerEvent) {
    if (pointer?.id !== e.pointerId) return
    const dx = e.clientX - pointer.x, dy = e.clientY - pointer.y
    offset = Math.abs(dx) > Math.abs(dy) ? Math.max(-100, Math.min(100, dx)) : 0
  }
  function end(e: PointerEvent) {
    if (pointer?.id !== e.pointerId) return
    const dx = e.clientX - pointer.x, dy = e.clientY - pointer.y
    pointer = null; offset = 0
    if (Math.abs(dx) >= 50 && Math.abs(dx) > Math.abs(dy) * 1.3) choose(dx > 0)
  }
  function key(e: KeyboardEvent) {
    if (intro || !dialog?.open || e.repeat || e.altKey || e.ctrlKey || e.metaKey || suspended || match || saved || !card) return
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); choose(e.key === 'ArrowRight') }
  }
</script>

<svelte:window on:keydown={key} />

<dialog bind:this={dialog} aria-labelledby="hobby-picker-title" on:cancel={(e) => {e.preventDefault(); onClose()}}>
  <div class="heading"><div><span class="eyebrow">Исследовать</span><h2 id="hobby-picker-title">Подбор хобби</h2></div>
    <button class="close" aria-label="Закрыть подбор" on:click={onClose}>×</button></div>
  <div class="pane" bind:this={pane}>
    {#if intro}
      <article class="card"><div class="card-copy">
        <h3>Как подобрать хобби</h3>
        <p>Смахните карточку вправо, если хотите попробовать хобби, или влево, если оно вам не подходит. Можно также нажимать кнопки под карточкой.</p>
        <p>Ваш выбор влияет на следующие рекомендации. У понравившихся хобби можно посмотреть сообщества и сохранить подборку в PDF.</p>
        <button class="primary" on:click={() => {intro = false; void top()}}>Начать подбор</button>
      </div></article>
    {:else if match}
      <p class="kicker">Вам понравилось · {match.title}</p>
      {#if communities.length}
        <h3>Найти новое хобби проще в сообществе</h3>
        <p>Подпишитесь, чтобы узнать, с чего начать.</p>
        {#each communities as node (node.id)}
          <div class="row"><a href={node.community_url}>{node.title}</a>
            <button disabled={node.subscribed || busy !== null} on:click={() => subscribe(node)}>
              {node.subscribed ? 'Вы подписаны' : busy === node.id ? 'Сохраняем…' : 'Подписаться'}
            </button></div>
        {/each}
      {:else}
        <h3>Станьте первыми</h3><p>У этого увлечения пока нет сообщества. Создайте своё и соберите единомышленников.</p>
        <button class="primary" on:click={() => createCommunity(match!.title)}>Создать сообщество по «{match.title}»</button>
      {/if}
      <HobbyFirstStep node={match} {steps} />
      {#if error}<p role="alert">{error}</p>{/if}
      <button class="next" on:click={advance}>{saved ? 'К выбранным' : card ? 'Следующее хобби →' : 'К результатам'}</button>
    {:else if saved}
      <h3>Выбранные хобби</h3><p>Откройте хобби, чтобы посмотреть его сообщества.</p>
      {#each picks as item (item.id)}<button class="saved-row" on:click={() => {match = item; void top()}}>{item.title} <span>→</span></button>{/each}
      <button class="next" on:click={() => {saved = false; void top()}}>Назад к подбору</button>
    {:else if card}
      <p class="kicker">Ещё в подборке: {remaining}</p>
      <article class="card" style:transform={'translateX('+offset*.45+'px) rotate('+offset*.035+'deg)'} on:pointerdown={start} on:pointermove={move} on:pointerup={end} on:pointercancel={() => {pointer=null;offset=0}} on:lostpointercapture={() => {pointer=null;offset=0}}>
        {#if card.image_url}<img src={api.imageUrl(card.image_url)} alt="" width="640" height="360" draggable="false" />{/if}
        <div class="card-copy"><span class="eyebrow">Увлечение</span><h3>{card.title}</h3>
          {#if card.description}<p>{card.description}</p>{/if}
          <section class="characteristics" aria-labelledby="hobby-characteristics-title">
            <h4 id="hobby-characteristics-title">Характеристики</h4>
            {#if characteristics.length}
              <dl>
                {#each characteristics as group (group.id)}
                  <div><dt>{group.name}</dt><dd>{group.values.join(' · ')}</dd></div>
                {/each}
              </dl>
            {:else}<p>Характеристики пока не указаны.</p>{/if}
          </section>
          <HobbyFirstStep node={card} {steps} />
        </div>
      </article>
      <p class="hint">Смахните карточку или выберите кнопкой</p>
      <div class="actions"><button on:click={() => choose(false)}>← Не моё</button><button class="primary" on:click={() => choose(true)}>Нравится →</button></div>
    {:else}
      <h3>{data.nodes.some(n => n.kind === 'element' && n.is_active) ? 'Вы посмотрели все хобби' : 'Пока нет хобби для подбора'}</h3>
      {#if deck && data.nodes.some(n => n.kind === 'element' && n.is_active)}
        {#if confirming}<p>Очистить выбор и посмотреть карточки заново?</p><button on:click={reset}>Да, начать заново</button> <button on:click={() => confirming = false}>Отмена</button>
        {:else}<button class="next" on:click={() => confirming = true}>Начать заново</button>{/if}
      {/if}
    {/if}
    {#if !intro && picks.length}
      <button class="next" disabled={exporting} on:click={exportPicks}>{exporting ? 'Готовим PDF…' : 'Скачать подборку в PDF'}</button>
      {#if exportError}<p role="alert">{exportError}</p>{/if}
    {/if}
    {#if !intro && !saved && !match && picks.length}<button class="next" on:click={() => {saved = true; void top()}}>Выбранные хобби · {picks.length}</button>{/if}
  </div>
</dialog>
<style>
  dialog{box-sizing:border-box;position:fixed;inset:0;margin:auto;width:min(440px,calc(100% - 24px));max-height:min(90dvh,800px);padding:0;border:1px solid #8174ce45;border-radius:20px;background:var(--explore-surface,#fff);color:var(--explore-ink,#2d3650);box-shadow:0 20px 80px #1114}
  :global(.dark) dialog{--explore-surface:#242633;--explore-ink:#ecedf5}
  dialog[open]{display:flex;flex-direction:column}dialog::backdrop{background:#11172db3}
  .heading,.row,.actions,.saved-row{display:flex;align-items:center;justify-content:space-between;gap:12px}.heading{padding:16px 20px;border-bottom:1px solid #8174ce33;flex:none}
  .eyebrow,.kicker,.hint{font-size:12px}.eyebrow{letter-spacing:.06em}.kicker{margin:0 0 12px}.hint{text-align:center;margin:12px 0}.pane{padding:18px;overflow:auto;overscroll-behavior:contain;overflow-x:hidden}
  h2,h3{font-weight:700;line-height:1.2}h2{font-size:21px}h3{font-size:25px;overflow-wrap:anywhere}p{margin:10px 0;line-height:1.5}
  button,.row a{cursor:pointer}button{border-radius:12px;padding:10px 14px;min-height:44px;border:1px solid #8174ce55}button:disabled{opacity:.65;cursor:default}.close{font-size:24px;line-height:1}
  .card{touch-action:pan-y pinch-zoom;user-select:none;border-radius:17px;overflow:hidden;background:linear-gradient(145deg,#8174ce26,#8174ce0a);border:1px solid #8174ce44}.card img{display:block;width:100%;aspect-ratio:16/9;height:auto;object-fit:cover}
  .card-copy{padding:24px 20px;min-height:140px}.card-copy h3{margin-top:8px}.card-copy p{white-space:pre-line;overflow-wrap:anywhere}
  .actions button{flex:1}.primary{background:#6250a5;color:white;font-weight:600}
  .characteristics{margin-top:16px;border-top:1px solid #8174ce44;padding-top:12px;font-size:14px}
  .characteristics h4{font-weight:650}.characteristics dl{margin-top:8px;display:grid;gap:8px}
  .characteristics dl>div{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:12px;line-height:1.4;overflow-wrap:anywhere}
  .characteristics dd{margin:0;font-weight:600}
  .next,.saved-row{width:100%;margin-top:12px}.row{border-bottom:1px solid #8174ce33;padding:10px 0}.row a,.saved-row{overflow-wrap:anywhere}.row a{text-decoration:underline}.row button{flex:none}
  @media(max-width:600px){dialog{width:100%;height:100dvh;max-width:100%;max-height:100dvh;border:0;border-radius:0}.heading{padding-top:max(16px,env(safe-area-inset-top))}.pane{padding-bottom:max(24px,env(safe-area-inset-bottom))}}
</style>
