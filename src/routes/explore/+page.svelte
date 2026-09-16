<script lang="ts">
  import { onMount } from 'svelte'
  import { contentPadding } from '$lib/components/ui/layout/Shell.svelte'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { loadBackendFeedSettings } from '$lib/settings'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import ExploreGraph from '$lib/components/explore/ExploreGraph.svelte'
  import PropertyPicker from '$lib/components/explore/PropertyPicker.svelte'
  import { ExploreApi } from '$lib/explore/api'
  import { emptyGraph, filterNodes, type ExploreNode } from '$lib/explore/types'

  const api = new ExploreApi()
  let data = emptyGraph()
  let loading = true, error = '', loginOpen = false
  let query = '', filters: number[] = [], selected: number | null = null
  let showProperties = false, listView = false, busy: number | null = null
  let filtersOpen = true
  $: visible = filterNodes(data.nodes, data.properties, filters, query)
  $: visibleIds = new Set(visible.map(node => node.id))
  $: edges = data.edges.filter(edge => visibleIds.has(edge.source) && visibleIds.has(edge.target))
  $: active = visible.find(node => node.id === selected) ?? null

  async function load() {
    loading = true; error = ''
    try { data = await api.graph() }
    catch (problem) { error = (problem as Error).message }
    finally { loading = false }
  }
  async function subscribe(node: ExploreNode) {
    if (!$siteToken) { loginOpen = true; return }
    if (busy !== null) return
    busy = node.id; error = ''
    try {
      const result = await api.subscribe(node.id, !node.subscribed)
      data = { ...data, nodes: data.nodes.map(item => item.id === node.id ? { ...item, subscribed: result.subscribed } : item) }
      if (node.kind === 'community') await loadBackendFeedSettings($siteToken)
    } catch (problem) { error = (problem as Error).message }
    finally { busy = null }
  }
  onMount(load)
</script>

<svelte:head><title>Explore — карта увлечений | Тамбур</title><meta name="description" content="Найдите новое увлечение и сообщество по интересам. Исследуйте связи, выбирайте компанию, бюджет и сложность." /></svelte:head>

<main class="explore-page" style:height={`calc(100dvh - ${$contentPadding.top + $contentPadding.bottom}px)`}>
  <div class="explore-workspace">
    <header class="toolbar">
      <h1>Explore<span>Карта увлечений</span></h1>
      <input class="search" aria-label="Поиск увлечения или сообщества" placeholder="Увлечение или сообщество" bind:value={query} />
      <button class="filter-button" class:chosen={filtersOpen} aria-expanded={filtersOpen} aria-controls="explore-filters" on:click={() => filtersOpen = !filtersOpen}>Фильтры{filters.length ? ` · ${filters.length}` : ''} ▾</button>
      <div class="view-switch" aria-label="Вид карты"><button aria-pressed={!listView} class:chosen={!listView} on:click={() => listView = false}>Граф</button><button aria-pressed={listView} class:chosen={listView} on:click={() => listView = true}>Список</button></div>
      {#if $siteUser?.is_staff}<a class="manage" href="/moderator/explore" aria-label="Управление графом">Управление ↗</a>{/if}
    </header>
    {#if filtersOpen}
      <section id="explore-filters" class="filters" aria-label="Фильтры графа">
        <div class="section-title"><h2>Найти своё</h2><button aria-label="Закрыть фильтры" on:click={() => filtersOpen = false}>×</button></div>
        <PropertyPicker properties={data.properties} bind:selected={filters} />
        <label class="toggle"><input type="checkbox" bind:checked={showProperties} />Показывать свойства на графе</label>
        <div class="filter-footer"><span>{visible.length} из {data.nodes.length} узлов</span>{#if filters.length || query}<button on:click={() => { filters = []; query = '' }}>Сбросить</button>{/if}</div>
      </section>
    {/if}
    {#if error}<div class="error" role="alert">{error}<button on:click={load}>Повторить</button></div>{/if}
    <section class="graph-area" aria-label="Карта интересов">
      {#if loading}<div class="empty" role="status"><span class="empty-symbol">◌</span><h2>Собираем карту интересов…</h2></div>
      {:else if !visible.length}<div class="empty"><span class="empty-symbol">◎</span><h2>{data.nodes.length ? 'Ничего не найдено' : 'Карта скоро появится'}</h2><p>{data.nodes.length ? 'Попробуйте другие свойства или сбросьте фильтры.' : 'Мы собираем увлечения и сообщества в одну карту.'}</p>{#if data.nodes.length}<button on:click={() => { filters = []; query = '' }}>Сбросить фильтры</button>{/if}</div>
      {:else if listView}<div class="node-list">{#each visible as node (node.id)}<article><button class="node-title" on:click={() => selected = node.id}><span class:community={node.kind === 'community'} class="dot"></span>{node.title}</button><small>{node.kind === 'community' ? 'Сообщество' : 'Увлечение'}</small><div><button disabled={busy !== null} on:click={() => subscribe(node)}>{node.subscribed ? 'Вы подписаны ✓' : node.kind === 'community' ? 'Подписаться' : 'Следить за обновлениями'}</button>{#if node.community_url}<a href={node.community_url}>Перейти ↗</a>{/if}</div></article>{/each}</div>
      {:else}<ExploreGraph nodes={visible} {edges} properties={data.properties} selected={active?.id ?? null} {showProperties} on:select={(event) => selected = event.detail} />{/if}
    </section>
    {#if active && !listView}
      <section class="node-actions" aria-label="Действия с выбранным узлом">
        <div class="selected-title"><span class="dot" class:community={active.kind === 'community'}></span><h2>{active.title}</h2></div>
        <button class="subscribe" class:subscribed={active.subscribed} disabled={busy !== null} on:click={() => subscribe(active!)}>{busy === active.id ? 'Сохраняем…' : active.subscribed ? 'Отписаться' : active.kind === 'community' ? 'Подписаться' : 'Следить за обновлениями'}</button>
        {#if active.community_url}<a class="open-community" href={active.community_url}>Перейти в сообщество ↗</a>{/if}
        <button class="close-selection" aria-label="Снять выделение" on:click={() => selected = null}>×</button>
      </section>
    {/if}
  </div>
</main>
<LoginModal bind:open={loginOpen} registrationSource="explore" registrationPath="/explore" on:success={load} />

<style>
  .explore-page{--explore-ink:#2d3650;--explore-surface:#fff;--explore-canvas:#f6f7fb;color:var(--explore-ink);width:100%;min-width:0;min-height:360px;box-sizing:border-box}
  .explore-workspace{position:relative;width:100%;height:100%;isolation:isolate;overflow:hidden}
  .graph-area{position:absolute;inset:0;min-width:0}
  .toolbar{position:absolute;z-index:3;top:16px;left:20px;right:20px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;padding:12px 16px;border:1px solid #b2b8ca40;border-radius:16px;background:var(--explore-surface);box-shadow:0 4px 24px #3037510a}
  h1{display:flex;align-items:center;gap:12px;font-size:23px;letter-spacing:-.6px;font-weight:650;white-space:nowrap;margin-right:auto}
  h1 span{font-size:12px;letter-spacing:0;font-weight:400;color:#8b91a2}
  .search{box-sizing:border-box;width:240px;max-width:100%;border:1px solid #b2b8ca50;border-radius:10px;padding:10px 12px;font-size:12px;background:transparent}
  .filter-button{padding:10px 12px;border:1px solid #b2b8ca50;border-radius:10px;font-size:12px;white-space:nowrap}
  .view-switch{display:flex;gap:2px;border-radius:10px;padding:3px;background:var(--explore-canvas)}
  .view-switch button{padding:7px 10px;font-size:12px;border-radius:7px}.chosen{background:#8174ce18;color:#8174ce}
  .manage{font-size:12px;color:#8174ce;white-space:nowrap}
  .filters{position:absolute;z-index:4;top:92px;left:20px;width:330px;max-width:calc(100% - 40px);max-height:calc(100% - 112px);overflow:auto;border:1px solid #b2b8ca40;background:var(--explore-surface);border-radius:16px;padding:18px;box-shadow:0 12px 35px #3037511a;box-sizing:border-box}
  .section-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}.section-title h2{font-size:15px;font-weight:600}.section-title button,.close-selection{font-size:22px;line-height:1;padding:4px 8px;color:#8b91a2}
  .toggle{display:flex;align-items:center;gap:8px;font-size:12px;margin:18px 0;line-height:1.5}.toggle input{accent-color:#8174ce}
  .filter-footer{display:flex;align-items:center;justify-content:space-between;font-size:11px;color:#8b91a2}.filter-footer button{color:#8174ce}
  .node-actions{position:absolute;z-index:2;bottom:76px;left:50%;transform:translateX(-50%);display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:12px;width:max-content;max-width:calc(100% - 40px);padding:12px 16px;border:1px solid #b2b8ca40;border-radius:16px;background:var(--explore-surface);box-shadow:0 8px 30px #30375118}
  .selected-title{display:flex;align-items:center;gap:8px;min-width:0}.selected-title h2{font-size:14px;font-weight:600;overflow-wrap:anywhere}
  .subscribe{padding:10px 14px;border-radius:10px;background:#7766be;color:white;font-size:12px}.subscribe.subscribed{background:#edf5f2;color:#338a72}.open-community{font-size:12px;color:#8174ce}
  .empty{height:100%;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:100px 30px 40px;background:var(--explore-canvas)}.empty-symbol{font-size:50px;color:#a59bc3}.empty h2{font-size:19px;margin:18px 0 10px}.empty p{color:#8790a3;font-size:13px}.empty button{margin-top:20px;font-size:13px;color:#8174ce}
  .error{position:absolute;z-index:5;top:92px;left:50%;transform:translateX(-50%);max-width:90%;padding:14px;background:#fff1ef;color:#a63a32;border-radius:12px;font-size:13px}.error button{margin-left:12px;text-decoration:underline}
  .node-list{height:100%;overflow:auto;display:grid;align-content:start;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:12px;padding:100px 20px 24px}.node-list article{padding:18px;border:1px solid #b2b8ca40;border-radius:16px;background:var(--explore-surface)}.node-title{display:flex;align-items:center;gap:10px;font-weight:550;text-align:left}.dot{width:10px;height:10px;flex-shrink:0;border-radius:50%;background:#8174ce}.dot.community{background:#dc9b50}.node-list small{font-size:10px;color:#929bad;display:block;margin:6px 0 16px 22px}.node-list article>div{display:flex;gap:20px;font-size:11px;color:#8174ce}
  button{cursor:pointer}button:disabled{cursor:wait;opacity:.55}button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid #8174ce;outline-offset:3px}
  :global(.dark) .explore-page{--explore-ink:#d9dfec;--explore-surface:#242631;--explore-canvas:#1d202a}.explore-page :global(.property-pickers details){border-color:#b2b8ca40}
  @media(max-width:1000px){h1 span{display:none}.search{width:200px}}
  @media(max-width:700px){.toolbar{top:10px;left:10px;right:10px;padding:10px;gap:8px}h1{font-size:21px;order:0}.view-switch{order:1}.manage{order:2;font-size:10px}.search{order:3;flex:1 1 calc(100% - 120px);min-width:0;width:auto}.filter-button{order:4}.filters{top:120px;left:10px;max-width:calc(100% - 20px);max-height:calc(100% - 140px);width:340px}.node-list{padding:126px 10px 20px;grid-template-columns:1fr}.error{top:120px}.node-actions{bottom:66px;gap:8px;padding:10px 36px 10px 12px;max-width:calc(100% - 20px)}.close-selection{position:absolute;right:5px;top:8px}.selected-title{width:100%;justify-content:center}}
</style>
