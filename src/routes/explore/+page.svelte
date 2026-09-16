<script lang="ts">
  import { onMount } from 'svelte'
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
  let filtersOpen = false
  $: visible = filterNodes(data.nodes, data.properties, filters, query)
  $: visibleIds = new Set(visible.map(node => node.id))
  $: edges = data.edges.filter(edge => visibleIds.has(edge.source) && visibleIds.has(edge.target))
  $: active = visible.find(node => node.id === selected) ?? null
  $: neighbors = active ? data.edges.flatMap(edge => edge.source === active.id ? [edge.target] : edge.target === active.id ? [edge.source] : []) : []
  $: optionLabels = new Map(data.properties.flatMap(property => property.options.map(option => [option.id, option.label] as const)))

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

<main class="explore-page">
  <header><div><p class="eyebrow">Территория интересов</p><h1>Explore<span>Карта увлечений</span></h1><p class="intro">От знакомого интереса — к новому увлечению и своей компании.</p></div>{#if $siteUser?.is_staff}<a class="manage" href="/moderator/explore">Управление графом ↗</a>{/if}</header>
  {#if error}<div class="error" role="alert">{error}<button on:click={load}>Повторить</button></div>{/if}
  <div class="explore-workspace" class:has-selection={Boolean(active)}>
    <aside class="filters">
      <div class="section-title"><h2>Найти своё</h2><button class="mobile-filters" aria-expanded={filtersOpen} on:click={() => filtersOpen = !filtersOpen}>Фильтры{filters.length ? ` · ${filters.length}` : ''} ▾</button>{#if filters.length || query}<button on:click={() => { filters = []; query = '' }}>Сбросить</button>{/if}</div>
      <input class="search" aria-label="Поиск увлечения или сообщества" placeholder="Увлечение или сообщество" bind:value={query} />
      <div class="filter-details" class:expanded={filtersOpen}>
      <PropertyPicker properties={data.properties} bind:selected={filters} />
      <p class="filter-hint">Внутри свойства достаточно одного совпадения. Между свойствами учитываются все условия.</p>
      <label class="toggle"><input type="checkbox" bind:checked={showProperties} />Показывать свойства на графе</label>
      </div>
      <div class="view-switch"><button class:chosen={!listView} on:click={() => listView = false}>Граф</button><button class:chosen={listView} on:click={() => listView = true}>Список</button></div>
      <p class="count">{visible.length} из {data.nodes.length} узлов · {edges.length} связей</p>
    </aside>
    <section class="graph-area" aria-label="Карта интересов">
      {#if loading}<div class="empty" role="status"><span class="empty-symbol">◌</span><h2>Собираем карту интересов…</h2></div>
      {:else if !visible.length}<div class="empty"><span class="empty-symbol">◎</span><h2>{data.nodes.length ? 'Ничего не найдено' : 'Карта скоро появится'}</h2><p>{data.nodes.length ? 'Попробуйте другие свойства или сбросьте фильтры.' : 'Мы собираем увлечения и сообщества в одну карту.'}</p>{#if data.nodes.length}<button on:click={() => { filters = []; query = '' }}>Сбросить фильтры</button>{/if}</div>
      {:else if listView}<div class="node-list">{#each visible as node (node.id)}<article><button class="node-title" on:click={() => selected = node.id}><span class:community={node.kind === 'community'} class="dot"></span>{node.title}</button><small>{node.kind === 'community' ? 'Сообщество' : 'Увлечение'}</small><div><button disabled={busy !== null} on:click={() => subscribe(node)}>{node.subscribed ? 'Вы подписаны ✓' : node.kind === 'community' ? 'Подписаться' : 'Следить за обновлениями'}</button>{#if node.community_url}<a href={node.community_url}>Перейти ↗</a>{/if}</div></article>{/each}</div>
      {:else}<ExploreGraph nodes={visible} {edges} properties={data.properties} selected={active?.id ?? null} {showProperties} on:select={(event) => selected = event.detail} />{/if}
    </section>
    <aside class="detail" aria-label="Информация об узле">
      {#if active}
        <div class="section-title"><span class="eyebrow">{active.kind === 'community' ? 'Сообщество' : 'Увлечение'}</span><button aria-label="Закрыть карточку" on:click={() => selected = null}>×</button></div>
        <div class:community={active.kind === 'community'} class="node-mark">{active.kind === 'community' ? '◉' : '✳'}</div>
        <h2>{active.title}</h2>{#if active.description}<p>{active.description}</p>{/if}
        <button class="subscribe" class:subscribed={active.subscribed} disabled={busy !== null} on:click={() => subscribe(active!)}>{busy === active.id ? 'Сохраняем…' : active.subscribed ? 'Вы подписаны ✓' : active.kind === 'community' ? 'Подписаться на сообщество' : 'Следить за обновлениями'}</button>
        {#if active.community_url}<a class="open-community" href={active.community_url}>Перейти в сообщество ↗</a>{:else}<p class="note">Уведомим на сайте, когда здесь или в подразделах появится новое сообщество.</p>{/if}
        {#if active.subscribed}<button class="unsubscribe" disabled={busy !== null} on:click={() => subscribe(active!)}>Отписаться</button>{/if}
        {#if active.show_properties && active.property_ids.length}<div class="property-tags">{#each active.property_ids as id}<span>{optionLabels.get(id)}</span>{/each}</div>{/if}
        {#if neighbors.length}<h3>Рядом на карте</h3><div class="neighbor-list">{#each data.nodes.filter(node => neighbors.includes(node.id)) as node}<button on:click={() => { if (!visibleIds.has(node.id)) { filters = []; query = '' } selected = node.id }}>{node.title}<span>↗</span></button>{/each}</div>{/if}
      {:else}<div class="detail-empty"><span>✳</span><h2>У каждого увлечения<br />есть продолжение</h2><p>Выберите узел, чтобы увидеть связи, найти сообщество или подписаться на обновления.</p><div class="mini-path"><i></i><b></b><i></i><b></b><i></i></div></div>{/if}
    </aside>
  </div>
</main>
<LoginModal bind:open={loginOpen} registrationSource="explore" registrationPath="/explore" on:success={load} />

<style>
  .explore-page{--explore-ink:#2d3650;--explore-surface:#fff;--explore-canvas:#f6f7fb;padding:28px 20px;color:var(--explore-ink);max-width:1800px;width:100%;min-width:0;box-sizing:border-box;margin:auto;container-type:inline-size}header{display:flex;justify-content:space-between;gap:24px;align-items:center;margin-bottom:26px}.eyebrow{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#8b83a6;font-weight:600;margin-bottom:8px}h1{font-size:36px;letter-spacing:-1.5px;font-weight:650;line-height:1.2}h1 span{font-size:14px;letter-spacing:0;font-weight:400;color:#8b91a2;margin-left:16px}.intro{font-size:13px;color:#7b8498;margin-top:10px}.manage{font-size:12px;color:#7668b7}.explore-workspace{display:grid;grid-template-columns:210px minmax(280px,1fr);gap:16px;min-height:620px}.filters,.detail{border:1px solid #e2e6ee;background:var(--explore-surface);border-radius:18px;padding:18px;min-width:0}.filters{align-self:start}.section-title{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:16px}.section-title h2{font-size:15px;font-weight:600}.section-title button{font-size:11px;color:#8174ce}.search{box-sizing:border-box;width:100%;border:1px solid #dce2eb;border-radius:10px;padding:11px;font-size:12px;margin-bottom:16px;background:transparent}.filter-hint,.note{font-size:10px;line-height:1.65;color:#929bad;margin:14px 0}.toggle{display:flex;align-items:center;gap:8px;font-size:11px;margin:18px 0;line-height:1.5}.toggle input{accent-color:#8174ce}.view-switch{display:flex;background:var(--explore-canvas);border-radius:10px;padding:4px}.view-switch button{flex:1;padding:7px;font-size:12px;border-radius:7px}.chosen{background:var(--explore-surface);box-shadow:0 1px 4px #2a305012}.count{font-size:10px;color:#8a93a4;margin-top:15px}.graph-area{min-width:0;min-height:620px}.detail{grid-column:2}.detail h2{font-size:23px;line-height:1.3;font-weight:550;word-break:break-word}.detail p{font-size:12px;line-height:1.7;color:#8790a3;margin:14px 0}.node-mark{font-size:50px;color:#8174ce;margin:30px 0 20px}.node-mark.community{color:#dc9b50}.subscribe{width:100%;padding:12px 8px;border-radius:10px;background:#7766be;color:white;font-size:11px;margin-top:24px}.subscribe.subscribed{background:#edf5f2;color:#338a72}.open-community{display:block;text-align:center;margin-top:12px;font-size:12px;color:#8174ce}.unsubscribe{color:#8c94a4;font-size:10px}.property-tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:20px}.property-tags span{background:var(--explore-canvas);padding:5px 8px;border-radius:7px;font-size:10px}h3{margin-top:26px;font-size:11px;font-weight:600}.neighbor-list{margin-top:10px;display:grid;gap:4px}.neighbor-list button{display:flex;justify-content:space-between;text-align:left;padding:10px 0;border-bottom:1px solid #e6e9f0;font-size:12px}.neighbor-list span{color:#9c91c7}.detail-empty{padding-top:8px}.detail-empty>span,.detail-empty .mini-path{display:none}.detail-empty>span{font-size:48px;color:#c7c0dc}.detail-empty h2{font-size:19px;margin-top:24px}.mini-path{display:flex;align-items:center;margin-top:40px;opacity:.5}.mini-path i{width:12px;height:12px;background:#b4a9d6;border-radius:50%}.mini-path i:last-child{background:#dfb483}.mini-path b{height:1px;width:35px;background:#b4a9d6}.empty{height:100%;min-height:430px;background:var(--explore-canvas);border-radius:20px;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;padding:30px}.empty-symbol{font-size:50px;color:#a59bc3}.empty h2{font-size:19px;margin:18px 0 10px}.empty p{color:#8790a3;font-size:13px}.empty button{margin-top:20px;font-size:13px;color:#8174ce}.error{padding:14px;background:#fff1ef;color:#a63a32;border-radius:12px;margin-bottom:16px;font-size:13px}.error button{margin-left:12px;text-decoration:underline}.node-list{display:grid;gap:12px}.node-list article{padding:18px;border:1px solid #e2e6ee;border-radius:16px;background:var(--explore-surface)}.node-title{display:flex;align-items:center;gap:10px;font-weight:550;text-align:left}.dot{width:12px;height:12px;flex-shrink:0;border-radius:50%;background:#8174ce}.dot.community{background:#dc9b50}.node-list small{font-size:10px;color:#929bad;display:block;margin:6px 0 16px 22px}.node-list article>div{display:flex;gap:20px;font-size:11px;color:#8174ce}button{cursor:pointer}button:disabled{cursor:wait;opacity:.55}button:focus-visible,a:focus-visible,input:focus-visible{outline:2px solid #8174ce;outline-offset:3px}:global(.dark) .explore-page{--explore-ink:#d9dfec;--explore-surface:#242631;--explore-canvas:#1d202a}.explore-page :global(.property-pickers details){border-color:#b2b8ca40}@container(min-width:1150px){.explore-workspace{grid-template-columns:220px minmax(350px,1fr) 250px}.detail{grid-column:auto}.detail-empty{padding-top:70px}.detail-empty>span,.detail-empty .mini-path{display:flex}}@media(max-width:1150px){.explore-workspace{grid-template-columns:200px minmax(270px,1fr)}.detail{grid-column:1 / -1}.detail-empty{padding:10px}.detail-empty>span,.mini-path{display:none}.node-mark{margin:5px 0}.detail .subscribe{max-width:280px}.graph-area{min-height:540px}}@media(max-width:700px){.explore-page{padding:18px 10px}header{align-items:start;gap:10px}h1{font-size:30px}h1 span{display:block;margin:6px 0;font-size:12px}.intro{font-size:11px}.manage{font-size:10px}.explore-workspace{display:flex;flex-direction:column}.filters{width:100%;padding:14px}.filters :global(.property-pickers){grid-template-columns:1fr 1fr}.filter-hint{display:none}.graph-area{min-height:430px}.view-switch{max-width:180px}.count{margin-bottom:0}.detail{padding:18px}}

  .explore-workspace{position:relative}
  .mobile-filters{display:none}
  .detail{display:none;position:absolute;right:14px;top:58px;width:240px;max-height:530px;overflow:auto;z-index:2;box-shadow:0 12px 35px #30375112}
  .has-selection .detail{display:block}
  @container(min-width:1150px){.detail{display:block;position:static;width:auto;max-height:none;box-shadow:none}}
  @media(max-width:700px){.mobile-filters{display:block}.filter-details:not(.expanded){display:none}.detail{position:fixed;top:auto;bottom:90px;left:12px;right:12px;width:auto;max-height:45vh;box-shadow:0 8px 40px #20283c30;z-index:30}.detail .node-mark{display:none}.detail .subscribe{margin-top:12px}.detail h2{font-size:19px}}
</style>
