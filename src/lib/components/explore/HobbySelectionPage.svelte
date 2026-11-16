<script lang="ts">
  import { HobbySelection } from '$lib/explore/HobbySelection'
  import type { ExploreData, ExploreNode } from '$lib/explore/types'
  import type { HobbySteps } from '$lib/explore/HobbySteps'
  import { ExploreApi } from '$lib/explore/api'
  import HobbyFirstStep from './HobbyFirstStep.svelte'

  export let data: ExploreData
  export let picks: ExploreNode[]
  export let steps: HobbySteps
  export let busy: number | null
  export let error: string
  export let subscribe: (node: ExploreNode) => void
  export let createCommunity: (title: string) => void
  const api = new ExploreApi()
  let exporting = false, exportError = ''
  $: selection = new HobbySelection(data, picks)

  async function download() {
    if (exporting || !selection.items.length) return
    exporting = true; exportError = ''
    try {
      const { HobbyPdf } = await import('$lib/explore/HobbyPdf')
      await new HobbyPdf(steps).download(selection.items)
    } catch { exportError = 'Не удалось скачать PDF. Попробуйте ещё раз.' }
    finally { exporting = false }
  }
</script>

<div class="selection">
  <a class="back" href="/hobbies">← К подбору хобби</a>
  <header><h1>Выбранные хобби и сообщества</h1>
    {#if selection.items.length}
      <button class="download" disabled={exporting} on:click={download}>{exporting ? 'Готовим PDF…' : 'Скачать подборку в PDF'}</button>
    {/if}
  </header>
  {#if exportError || error}<p role="alert">{exportError || error}</p>{/if}
  {#each selection.items as {hobby, communities} (hobby.id)}
    <article>
      <div class="summary">
        {#if hobby.image_url}<img src={api.imageUrl(hobby.image_url)} alt="" loading="lazy" width="88" height="62" />{/if}
        <div><h2>{hobby.title}</h2>
          {#if hobby.description}<p>{HobbySelection.description(hobby)}</p>{/if}
        </div>
      </div>
      <HobbyFirstStep node={hobby} {steps} />
      <h3>Сообщества</h3>
      {#each communities as club (club.id)}
        <div class="club">
          <div><a href={club.community_url}>{club.title}</a>
            {#if HobbySelection.description(club)}<p>{HobbySelection.description(club)}</p>{/if}
          </div>
          <button disabled={club.subscribed || busy !== null} on:click={() => subscribe(club)}>
            {club.subscribed ? 'Вы подписаны' : busy === club.id ? 'Сохраняем…' : 'Подписаться'}
          </button>
        </div>
      {:else}
        <p>У этого хобби пока нет сообщества.</p>
        <button on:click={() => createCommunity(hobby.title)}>Создать сообщество</button>
      {/each}
    </article>
  {:else}
    <p>Здесь появятся хобби, которым вы поставите «Нравится».</p>
  {/each}
</div>

<style>
  .selection{width:100%;max-width:760px;margin:0 auto;padding:12px 0 32px;overflow-wrap:anywhere}
  header,.summary,.club{display:flex;gap:16px;align-items:center}header,.club{justify-content:space-between}
  header{margin:12px 0 20px;flex-wrap:wrap}h1,h2,h3{font-weight:700;line-height:1.2}h1{font-size:clamp(24px,4vw,32px)}h2{font-size:22px}h3{margin:18px 0 6px;font-size:16px}
  article{padding:20px;border:1px solid #8174ce45;border-radius:16px;margin:14px 0}
  .summary{align-items:flex-start}.summary img{width:88px;height:62px;object-fit:cover;border-radius:8px}
  .club{border-top:1px solid #8174ce33;padding:10px 0}.club a,.back{text-decoration:underline;text-underline-offset:3px}.club a{font-weight:600}
  button{padding:8px 14px;border-radius:10px;border:1px solid #8174ce66;min-height:44px;flex:none}button:disabled{opacity:.65}
  .download{background:#5841a0;color:white;font-weight:600}p{margin:6px 0;line-height:1.45}
  @media(max-width:500px){.club{flex-wrap:wrap;gap:4px}article{padding:15px}}
</style>
