<script lang="ts">
  import { onMount } from 'svelte'
  import { refreshSiteUser, siteUser } from '$lib/siteAuth'
  import { ExploreApi } from '$lib/explore/api'
  import { emptyGraph, type ExploreNode } from '$lib/explore/types'
  import PropertyPicker from '$lib/components/explore/PropertyPicker.svelte'

  const api = new ExploreApi()
  let data = emptyGraph(), loading = true, busy = false, error = '', notice = ''
  let search = '', communitySearch = ''
  let editing: number | undefined
  let kind: 'element' | 'community' = 'element'
  let title = '', description = '', communityId: number | null = null
  let propertyIds: number[] = [], showProperties = false, active = true
  let source: number | null = null, target: number | null = null
  $: nodes = data.nodes.filter(node => node.title.toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru')))
  $: nodeNames = new Map(data.nodes.map(node => [node.id, node.title]))
  $: linkedCommunityIds = new Set(data.nodes.filter(node => node.id !== editing).map(node => node.community_id))
  $: communityOptions = (data.communities ?? []).filter(item => !linkedCommunityIds.has(item.id) && item.name.toLocaleLowerCase('ru').includes(communitySearch.toLocaleLowerCase('ru')))

  function reset(nextKind: 'element' | 'community' = 'element') {
    editing = undefined; kind = nextKind; title = ''; description = ''; communityId = null
    propertyIds = []; showProperties = false; active = true; communitySearch = ''
  }
  function edit(node: ExploreNode) {
    editing = node.id; kind = node.kind; title = node.title; description = node.description
    communityId = node.community_id; propertyIds = [...node.property_ids]
    showProperties = node.show_properties; active = node.is_active; communitySearch = ''
    error = ''; notice = ''
  }
  async function load() { data = await api.graph(true) }
  async function action(operation: () => Promise<unknown>, message: string) {
    if (busy) return
    busy = true; error = ''; notice = ''
    try { await operation(); await load(); notice = message }
    catch (problem) { error = (problem as Error).message }
    finally { busy = false }
  }
  function save() {
    return action(async () => {
      const result = await api.saveNode({ kind, title, description, community_id: kind === 'community' ? communityId : null, property_ids: propertyIds, show_properties: showProperties, is_active: active }, editing)
      editing = result.id
      if (kind === 'community') title = data.communities?.find(item => item.id === communityId)?.name ?? title
    }, 'Узел и свойства сохранены.')
  }
  function remove() {
    if (!editing || !window.confirm('Убрать узел из Explore вместе с его связями и подписками? Само сообщество останется на сайте.')) return
    const id = editing
    return action(async () => { await api.removeNode(id); reset() }, 'Узел удалён из графа.')
  }
  function addLink() {
    if (source === null || target === null) return
    return action(async () => { await api.addEdge(source!, target!); target = null }, 'Связь добавлена. Подписчики уведомлены о новых сообществах, если они появились.')
  }
  onMount(async () => {
    try { await refreshSiteUser(); if ($siteUser?.is_staff) await load() }
    catch (problem) { error = (problem as Error).message }
    finally { loading = false }
  })
</script>

<svelte:head><title>Explore — управление графом | Модераторская</title><meta name="robots" content="noindex,nofollow" /></svelte:head>
<main class="manager">
  <header><div><a href="/moderator">← Модераторская</a><h1>Explore</h1><p>Увлечения, сообщества и связи между ними</p></div><a class="public-link" href="/explore">Открыть граф ↗</a></header>
  {#if error}<p class="error" role="alert">{error}</p>{/if}{#if notice}<p class="notice" role="status">{notice}</p>{/if}
  {#if loading}<p role="status">Загрузка…</p>{:else if !$siteUser?.is_staff}<section class="panel"><h2>Доступ только модераторам сайта</h2><a href="/account?next=%2Fmoderator%2Fexplore">Войти в аккаунт</a></section>
  {:else}
    <div class="columns">
      <section class="panel nodes"><h2>Узлы <small>{data.nodes.length}</small></h2><div class="new-buttons"><button disabled={busy} on:click={() => reset('element')}>+ Элемент</button><button disabled={busy} on:click={() => reset('community')}>+ Сообщество</button></div><input aria-label="Найти узел" placeholder="Поиск по названию" bind:value={search} />
        <div class="node-list">{#each nodes as node (node.id)}<button disabled={busy} class:selected={editing === node.id} on:click={() => edit(node)}><span>{node.title}</span><small>{node.kind === 'element' ? 'Элемент' : 'Сообщество'}{!node.is_active ? ' · скрыт' : ''}</small></button>{/each}{#if !nodes.length}<p class="hint">Узлов пока нет. Добавьте первый элемент.</p>{/if}</div>
      </section>
      <form class="panel node-form" on:submit|preventDefault={save}>
        <h2>{editing ? 'Редактировать' : 'Добавить'} {kind === 'element' ? 'элемент' : 'сообщество'}</h2>
        {#if kind === 'element'}<label>Название<input required maxlength="160" bind:value={title} disabled={busy} /></label>
        {:else if editing}<label>Сообщество<input value={title} disabled /></label>
        {:else}<label>Поиск сообщества<input placeholder="Начните вводить название" bind:value={communitySearch} disabled={busy} /></label><label>Существующее сообщество<select required bind:value={communityId} disabled={busy}><option value={null}>Выберите сообщество</option>{#each communityOptions as item}<option value={item.id}>{item.name}</option>{/each}</select></label><p class="hint">Каждое сообщество добавляется один раз; к нему можно провести несколько связей.</p>{/if}
        <label>Описание<textarea rows="3" maxlength="4000" bind:value={description} disabled={busy}></textarea></label>
        <h3>Свойства</h3><p class="hint">В каждом списке можно выбрать несколько вариантов. Незаполненные свойства не ограничивают узел, пока посетитель не включил соответствующий фильтр.</p>
        <PropertyPicker properties={data.properties} bind:selected={propertyIds} disabled={busy} emptyLabel="Не задано" />
        <label class="checkbox"><input type="checkbox" bind:checked={showProperties} disabled={busy} />Показывать свойства в карточке и на графе</label><p class="hint">Скрытые свойства по-прежнему учитываются в фильтрах.</p>
        <label class="checkbox"><input type="checkbox" bind:checked={active} disabled={busy} />Показывать узел на публичном графе</label>
        <div class="actions"><button type="submit" class="primary" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</button>{#if editing}<button type="button" class="danger" disabled={busy} on:click={remove}>Удалить из графа</button>{/if}</div>
      </form>
    </div>
    <section class="panel connections"><h2>Связи <small>{data.edges.length}</small></h2><p class="hint">Направление: родительский элемент → подраздел или сообщество. У подраздела может быть несколько родителей. Например: «Мотоциклы → Питбайк» и «Туризм → Питбайк». Циклические связи запрещены.</p>
      <form class="link-form" on:submit|preventDefault={addLink}><label>Родительский элемент<select bind:value={source} required disabled={busy}><option value={null}>Выберите элемент</option>{#each data.nodes.filter(node => node.kind === 'element') as node}<option value={node.id}>{node.title}</option>{/each}</select></label><span>→</span><label>Подраздел или сообщество<select bind:value={target} required disabled={busy}><option value={null}>Выберите узел</option>{#each data.nodes.filter(node => node.id !== source) as node}<option value={node.id}>{node.title} ({node.kind === 'element' ? 'элемент' : 'сообщество'})</option>{/each}</select></label><button class="primary" disabled={busy || !source || !target}>Добавить связь</button></form>
      <div class="edge-list">{#each data.edges as edge (edge.id)}<div><span>{nodeNames.get(edge.source)} <b>→</b> {nodeNames.get(edge.target)}</span><button disabled={busy} aria-label={`Удалить связь ${nodeNames.get(edge.source)} — ${nodeNames.get(edge.target)}`} on:click={() => action(() => api.removeEdge(edge.id), 'Связь удалена.')}>Удалить связь</button></div>{/each}</div>
    </section>
  {/if}
</main>

<style>
  .manager{max-width:1200px;padding:28px 20px;margin:auto;color:#303b50}header{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:26px}header a{font-size:12px;color:#7868bc}h1{font-size:34px;font-weight:650;margin:12px 0 4px}header p{font-size:13px;color:#8490a2}.panel{padding:24px;border:1px solid #e0e5ed;background:#fff;border-radius:18px}h2{font-size:18px;font-weight:600;margin-bottom:18px}h2 small{font-size:12px;color:#8b91a4;margin-left:8px}.columns{display:grid;grid-template-columns:minmax(240px,1fr) minmax(350px,1.7fr);gap:20px}.nodes{align-self:start}.new-buttons{display:flex;gap:8px;margin-bottom:16px}.new-buttons button{background:#f1eef9;color:#7868bc;border-radius:8px;padding:9px;font-size:12px}input:not([type=checkbox]),textarea,select{width:100%;box-sizing:border-box;border:1px solid #d9dfeb;border-radius:9px;padding:10px 12px;font-size:13px;background:transparent;color:inherit}input:disabled,select:disabled{opacity:.6}label{display:grid;gap:8px;font-size:12px;margin:16px 0}.node-list{display:grid;gap:6px;margin-top:16px;max-height:700px;overflow:auto}.node-list button{text-align:left;padding:12px;border-radius:10px}.node-list button:hover,.node-list button.selected{background:#f2effa;color:#7060b2}.node-list span,.node-list small{display:block}.node-list span{font-size:13px}.node-list small{font-size:10px;color:#8b94a6;margin-top:5px}.hint{font-size:11px;line-height:1.7;color:#8691a3;margin:10px 0 16px}h3{font-size:14px;font-weight:550;margin-top:22px}.checkbox{display:flex;align-items:center;gap:10px;line-height:1.6}.checkbox input{accent-color:#7969be}.actions{display:flex;justify-content:space-between;gap:12px;margin-top:22px}.primary{padding:11px 18px;border-radius:10px;background:#7969be;color:white;font-size:12px}.danger{color:#be5555;font-size:12px}.connections{margin-top:20px}.link-form{display:flex;align-items:end;gap:14px}.link-form label{flex:1;min-width:0;margin:0}.link-form>span{padding-bottom:12px;color:#9b91ba}.edge-list{margin-top:22px;display:grid;gap:0}.edge-list>div{display:flex;align-items:center;justify-content:space-between;gap:15px;border-bottom:1px solid #edf0f5;padding:13px 0;font-size:12px}.edge-list b{margin:0 10px;color:#9689bd}.edge-list button{font-size:10px;color:#bd7777;white-space:nowrap}.error,.notice{padding:13px;border-radius:10px;margin-bottom:18px;font-size:13px}.error{background:#fff0ee;color:#a33d39}.notice{background:#ecf7f0;color:#37825b}button:disabled{opacity:.5;cursor:wait}button{cursor:pointer}button:focus-visible,a:focus-visible{outline:2px solid #8174ce;outline-offset:3px}:global(.dark) .manager{color:#d3d9e4}:global(.dark) .panel{background:#242631;border-color:#414454}:global(.dark) .node-list button.selected,:global(.dark) .node-list button:hover{background:#3a334f;color:#c6b8f2}@media(max-width:720px){.manager{padding:18px 10px}.columns{display:flex;flex-direction:column}.panel{padding:18px}.nodes{width:100%}.node-list{max-height:230px}.link-form{flex-direction:column;align-items:stretch}.link-form>span{display:none}}
</style>
