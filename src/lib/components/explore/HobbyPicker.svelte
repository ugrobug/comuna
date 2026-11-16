<script lang="ts">
  import { onMount, tick } from 'svelte'
  import type { ExploreData, ExploreNode } from '$lib/explore/types'
  import { HobbyDeck, HobbyHistory } from '$lib/explore/HobbyDeck'
  import { HobbySteps } from '$lib/explore/HobbySteps'
  import HobbyFirstStep from './HobbyFirstStep.svelte'
  import HobbySelectionPage from './HobbySelectionPage.svelte'
  import { ExploreApi } from '$lib/explore/api'

  export let data: ExploreData
  export let account: number | null
  export let selectedView: boolean
  export let suspended: boolean
  export let busy: number | null
  export let error: string
  export let onClose: () => void
  export let subscribe: (node: ExploreNode) => void
  export let createCommunity: (title: string) => void

  const api = new ExploreApi()
  let dialog: HTMLDialogElement, pane: HTMLElement
  let mounted = false, scope: string, deck: HobbyDeck
  let card: ExploreNode | null = null
  let intro = true
  let steps: HobbySteps
  let remaining = 0
  let picks: ExploreNode[] = [], confirming = false
  let pointer: { id: number; x: number; y: number } | null = null, offset = 0
  let suppressClick = false
  onMount(() => { mounted = true; return () => { dialog?.close() } })
  function initialize(user: number | null) {
    scope = 'tambur:hobby-picks:v1:' + (user ?? 'guest')
    let storage: Storage | undefined
    try { storage = window.localStorage } catch { /* private mode */ }
    steps = new HobbySteps(scope, storage)
    intro = true
    deck = new HobbyDeck(data.nodes, new HobbyHistory(scope, storage))
    card = deck.next(); remaining = deck.remaining; picks = deck.picked
    confirming = false
  }
  $: if (mounted && scope !== 'tambur:hobby-picks:v1:' + (account ?? 'guest')) initialize(account)
  $: if (mounted && dialog) {
    if (suspended && dialog.open) dialog.close()
    else if (!suspended && !dialog.open) dialog.showModal()
  }
  $: selectedOptions = new Set(card?.property_ids)
  $: characteristics = data.properties.map(property => ({
    id: property.id, name: property.name,
    values: property.options.filter(option => selectedOptions.has(option.id)).map(option => option.label),
  })).filter(group => group.values.length)
  async function top() { await tick(); if (pane) pane.scrollTop = 0 }
  function choose(like: boolean) {
    if (!card || selectedView || !deck.choose(card.id, like)) return
    card = deck.next(); remaining = deck.remaining; picks = deck.picked
    pointer = null; offset = 0; void top()
  }
  function reset() { deck.reset(); picks = []; card = deck.next(); remaining = deck.remaining; confirming = false; void top() }
  function start(e: PointerEvent) {
    if (!e.isPrimary || e.button !== 0) return
    suppressClick = false
    if (intro || suspended || selectedView || !card) return
    pointer = { id: e.pointerId, x: e.clientX, y: e.clientY }
  }
  function clearGesture() { pointer = null; offset = 0 }
  function cancel(e: PointerEvent) {
    if (pointer?.id === e.pointerId) clearGesture()
  }
  function afterSwipe(e: MouseEvent) {
    if (suppressClick && e.detail > 0) {
      e.preventDefault(); e.stopPropagation(); suppressClick = false
    }
  }
  function move(e: PointerEvent) {
    if (pointer?.id !== e.pointerId) return
    const dx = e.clientX - pointer.x, dy = e.clientY - pointer.y
    offset = Math.abs(dx) > Math.abs(dy) ? Math.max(-100, Math.min(100, dx)) : 0
  }
  function end(e: PointerEvent) {
    if (pointer?.id !== e.pointerId) return
    const dx = e.clientX - pointer.x, dy = e.clientY - pointer.y
    clearGesture()
    if (Math.abs(dx) < 36 || Math.abs(dx) <= Math.abs(dy) * 1.15) return
    suppressClick = true
    choose(dx > 0)
  }
  function key(e: KeyboardEvent) {
    if (intro || !dialog?.open || e.repeat || e.altKey || e.ctrlKey || e.metaKey || suspended || selectedView || !card) return
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') { e.preventDefault(); choose(e.key === 'ArrowRight') }
  }
</script>

<svelte:window on:keydown={key} on:pointermove={move} on:pointerup={end} on:pointercancel={cancel} on:blur={clearGesture} />

{#if selectedView}
  {#if steps}<HobbySelectionPage {data} {picks} {steps} {busy} {error} {subscribe} {createCommunity} />{/if}
{:else}
<dialog bind:this={dialog} aria-labelledby="hobby-picker-title" on:cancel={(e) => {e.preventDefault(); onClose()}}>
  <div class="heading"><div><span class="eyebrow">Исследовать</span><h2 id="hobby-picker-title">Подбор хобби</h2></div>
    <button class="close" aria-label="Закрыть подбор" on:click={onClose}>×</button></div>
  {#if picks.length}
    <a class="selection-link" href="/hobbies?view=selected">Выбранные хобби и сообщества <strong>{picks.length}</strong> →</a>
  {/if}
  <div class="pane" bind:this={pane} on:pointerdown={start} on:click|capture={afterSwipe} role="presentation">
    {#if intro}
      <article class="card"><div class="card-copy">
        <h3>Как подобрать хобби</h3>
        <p>Смахните карточку вправо, если хотите попробовать хобби, или влево, если оно вам не подходит. Можно также нажимать кнопки под карточкой.</p>
        <p>Ваш выбор влияет на следующие рекомендации. У понравившихся хобби можно посмотреть сообщества и сохранить подборку в PDF.</p>
        <button class="primary" on:click={() => {intro = false; void top()}}>Начать подбор</button>
      </div></article>
    {:else if card}
      <p class="kicker">Ещё в подборке: {remaining}</p>
      <article class="card" style:transform={'translateX('+offset*.45+'px) rotate('+offset*.035+'deg)'}>
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
  </div>
</dialog>
{/if}
<style>
  dialog{box-sizing:border-box;position:fixed;inset:0;margin:auto;width:min(440px,calc(100% - 24px));max-height:min(90dvh,800px);padding:0;border:1px solid #8174ce45;border-radius:20px;background:var(--explore-surface,#fff);color:var(--explore-ink,#2d3650);box-shadow:0 20px 80px #1114}
  :global(.dark) dialog{--explore-surface:#242633;--explore-ink:#ecedf5}
  dialog[open]{display:flex;flex-direction:column}dialog::backdrop{background:#11172db3}
  .heading,.actions{display:flex;align-items:center;justify-content:space-between;gap:12px}.heading{padding:16px 20px;border-bottom:1px solid #8174ce33;flex:none}
  .eyebrow,.kicker,.hint{font-size:12px}.eyebrow{letter-spacing:.06em}.kicker{margin:0 0 12px}.hint{text-align:center;margin:12px 0}.pane{touch-action:pan-y pinch-zoom;padding:18px;overflow:auto;overscroll-behavior:contain;overflow-x:hidden}
  h2,h3{font-weight:700;line-height:1.2}h2{font-size:21px}h3{font-size:25px;overflow-wrap:anywhere}p{margin:10px 0;line-height:1.5}
  button{cursor:pointer}button{border-radius:12px;padding:10px 14px;min-height:44px;border:1px solid #8174ce55}button:disabled{opacity:.65;cursor:default}.close{font-size:24px;line-height:1}
  .card{touch-action:pan-y pinch-zoom;user-select:none;border-radius:17px;overflow:hidden;background:linear-gradient(145deg,#8174ce26,#8174ce0a);border:1px solid #8174ce44}.card img{display:block;width:100%;aspect-ratio:16/9;height:auto;object-fit:cover}
  .card-copy{padding:24px 20px;min-height:140px}.card-copy h3{margin-top:8px}.card-copy p{white-space:pre-line;overflow-wrap:anywhere}
  .actions button{flex:1}.primary{background:#6250a5;color:white;font-weight:600}
  .characteristics{margin-top:16px;border-top:1px solid #8174ce44;padding-top:12px;font-size:14px}
  .characteristics h4{font-weight:650}.characteristics dl{margin-top:8px;display:grid;gap:8px}
  .characteristics dl>div{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.2fr);gap:12px;line-height:1.4;overflow-wrap:anywhere}
  .characteristics dd{margin:0;font-weight:600}
  .next{width:100%;margin-top:12px}
  .selection-link{flex:none;padding:9px 20px;background:#8174ce18;border-bottom:1px solid #8174ce33;font-size:14px;text-decoration:underline;text-underline-offset:3px}
  @media(max-width:600px){
    .card img{float:right;width:88px;height:60px;margin:16px 16px 8px 12px;border-radius:8px}
    .card-copy{padding:16px}.card-copy>p,.characteristics{clear:both}.pane{flex:1}
    dialog{width:100%;height:100dvh;max-width:100%;max-height:100dvh;border:0;border-radius:0}.heading{padding-top:max(16px,env(safe-area-inset-top))}.pane{padding-bottom:max(24px,env(safe-area-inset-bottom))}}
</style>
