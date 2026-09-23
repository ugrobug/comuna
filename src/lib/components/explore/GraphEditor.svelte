<script lang="ts">
  import { createEventDispatcher, tick } from 'svelte'
  import { beforeNavigate } from '$app/navigation'
  import { ExploreApi } from '$lib/explore/api'
  import type { ExploreData, ExploreNode, ExploreEdge } from '$lib/explore/types'
  import PropertyPicker from './PropertyPicker.svelte'
  import NodeSearch from './NodeSearch.svelte'

  export let data: ExploreData
  export let initialNode: number | null = null
  const api = new ExploreApi()
  const dispatch = createEventDispatcher<{ select: number | null; close: void }>()
  let busy = false, error = '', notice = '', collapsed = false
  let nodeForm: HTMLFormElement
  let content: HTMLDivElement
  let editing: number | undefined
  let kind: 'element' | 'community' = 'element'
  let title = '', description = '', communityId: number | null = null, communitySearch = ''
  let propertyIds: number[] = [], showProperties = false, active = true
  let mode: 'welcome' | 'node' | 'link' = 'welcome'
  let source: number | null = null, target: number | null = null
  let edgeId: number | undefined
  let picking: 'source' | 'target' | null = null
  let savedDraft = draftKey(), savedLink = ''
  if (initialNode !== null) {
    const node = data.nodes.find(item => item.id === initialNode)
    if (node) edit(node)
  }
  $: imageUrl = data.nodes.find(node => node.id === editing)?.image_url
  $: nodeNames = new Map(data.nodes.map(node => [node.id, node.title]))
  $: linkedCommunityIds = new Set(data.nodes.filter(node => node.id !== editing).map(node => node.community_id))
  $: communityOptions = (data.communities ?? []).filter(item => !linkedCommunityIds.has(item.id) && item.name.toLocaleLowerCase('ru').includes(communitySearch.toLocaleLowerCase('ru')))
  $: attachedEdges = data.edges.filter(edge => edge.source === editing || edge.target === editing)
  $: dirty = mode === 'node' ? draftKey(kind, title, description, communityId, propertyIds, showProperties, active) !== savedDraft : mode === 'link' && linkKey(source, target) !== savedLink

  function draftData() {
    return { kind, title, description, community_id: kind === 'community' ? communityId : null,
      property_ids: [...propertyIds].sort((a, b) => a - b), show_properties: showProperties, is_active: active }
  }
  // Arguments make Svelte track all fields used by the draft comparison.
  function draftKey(..._fields: unknown[]) { return JSON.stringify(draftData()) }
  function linkKey(a = source, b = target) { return JSON.stringify([a, b]) }
  export async function flush() {
    if (busy) return false
    if (mode === 'node' && draftKey() !== savedDraft) return save()
    if (mode === 'link' && linkKey() !== savedLink) return saveLink()
    return true
  }
  async function switchDraft(next: () => void) {
    if (!await flush()) return
    error = ''; notice = ''; collapsed = false; picking = null
    next()
    await tick(); content?.scrollTo({ top: 0 })
  }
  function reset(nextKind: 'element' | 'community' = 'element') {
    mode = 'node'; editing = undefined; kind = nextKind; title = ''; description = ''; communityId = null
    propertyIds = []; showProperties = false; active = true; communitySearch = ''
    savedDraft = draftKey(); dispatch('select', null)
  }
  function edit(node: ExploreNode) {
    mode = 'node'; editing = node.id; kind = node.kind; title = node.title; description = node.description
    communityId = node.community_id; propertyIds = [...node.property_ids]
    showProperties = node.show_properties; active = node.is_active; communitySearch = ''
    savedDraft = draftKey()
  }
  export async function selectFromGraph(id: number) {
    if (busy) return
    if (mode === 'link' && picking) {
      if (picking === 'source') source = id; else target = id
      picking = null; collapsed = false; dispatch('select', id)
      await tick(); content?.scrollTo({ top: 0 })
      return
    }
    await switchDraft(() => {
      const node = data.nodes.find(item => item.id === id)
      if (node) { edit(node); dispatch('select', id) }
    })
  }
  export async function editEdge(edge: ExploreEdge) {
    await switchDraft(() => {
      mode = 'link'; edgeId = edge.id; source = edge.source; target = edge.target
      savedLink = linkKey(); dispatch('select', source)
    })
  }
  async function action(operation: () => Promise<unknown>, message: string) {
    if (busy) return false
    busy = true; error = ''; notice = ''
    try {
      await operation(); notice = message
      // A failed refresh must never turn a successful create into a duplicate retry.
      try { data = await api.graph(true) }
      catch { error = 'Изменения сохранены, но граф не обновился. Нажмите «Обновить граф».' }
      return true
    } catch (problem) { error = (problem as Error).message; return false }
    finally { busy = false }
  }
  function discard() {
    if (busy) return
    error = ''; notice = ''; picking = null; collapsed = false
    const node = data.nodes.find(item => item.id === editing)
    if (mode === 'node' && node) edit(node)
    else if (mode === 'link' && edgeId) {
      const edge = data.edges.find(item => item.id === edgeId)
      if (edge) { source = edge.source; target = edge.target; savedLink = linkKey() }
      else mode = 'welcome'
    } else { mode = 'welcome'; editing = undefined; dispatch('select', null) }
  }

  async function refresh() {
    if (busy) return
    busy = true
    try { data = await api.graph(true); error = '' }
    catch (problem) { error = (problem as Error).message }
    finally { busy = false }
  }
  async function save() {
    collapsed = false
    await tick()
    if (busy || !nodeForm?.reportValidity()) return false
    const saved = await action(async () => {
      const result = await api.saveNode(draftData(), editing)
      editing = result.id
      if (kind === 'community') title = data.communities?.find(item => item.id === communityId)?.name ?? title
      savedDraft = draftKey()
    }, 'Узел сохранён.')
    if (saved) dispatch('select', editing!)
    return saved
  }
  async function remove() {
    if (!editing || !window.confirm('Убрать узел из графа вместе с его связями и подписками? Само сообщество останется на сайте.')) return
    const id = editing
    await action(async () => { await api.removeNode(id); mode = 'welcome'; editing = undefined; dispatch('select', null) }, 'Узел удалён из графа.')
  }
  async function uploadImage(event: Event) {
    const input = event.currentTarget as HTMLInputElement
    const file = input.files?.[0]; input.value = ''
    if (!file || busy) return
    if (file.size > 10 * 1024 * 1024) { error = 'Изображение должно быть не больше 10 МБ.'; return }
    if ((editing === undefined || draftKey() !== savedDraft) && !await save()) return
    await action(() => api.uploadImage(editing!, file), 'Изображение сохранено в WebP.')
  }
  async function startLink() {
    await switchDraft(() => {
      source = editing ?? null; target = null; edgeId = undefined; mode = 'link'; savedLink = linkKey()
    })
  }
  async function saveLink() {
    if (source === null || target === null) { error = 'Выберите оба узла связи.'; collapsed = false; return false }
    return action(async () => {
      const result = await api.saveEdge(source!, target!, edgeId)
      edgeId = result.id; savedLink = linkKey(); picking = null
    }, 'Связь сохранена.')
  }
  async function removeLink(edge: ExploreEdge) {
    if (!window.confirm(`Удалить связь «${nodeNames.get(edge.source)} — ${nodeNames.get(edge.target)}»?`)) return
    await action(async () => {
      await api.removeEdge(edge.id)
      if (mode === 'link') { mode = 'welcome'; edgeId = undefined; picking = null }
    }, 'Связь удалена.')
  }
  async function close() { if (await flush()) dispatch('close') }
  beforeNavigate(event => {
    if ((busy || dirty) && !window.confirm('Есть несохранённые изменения графа. Покинуть страницу?')) event.cancel()
  })
  function beforeUnload(event: BeforeUnloadEvent) {
    if (busy || dirty) { event.preventDefault(); event.returnValue = '' }
  }
</script>

<svelte:window on:beforeunload={beforeUnload} />
<aside class="graph-editor" class:collapsed aria-label="Редактор графа">
  <header><strong>{picking ? 'Выберите точку на графе' : 'Редактор графа'}</strong><button type="button" aria-label={collapsed ? 'Развернуть редактор' : 'Свернуть редактор'} on:click={() => { collapsed = !collapsed; if (!collapsed) picking = null }}>{collapsed ? 'Развернуть' : 'Свернуть'}</button><button type="button" disabled={busy} aria-label="Закончить редактирование" on:click={close}>×</button></header>
  <div class="editor-content" bind:this={content} hidden={collapsed}>
    <div class="new-buttons"><button disabled={busy} on:click={() => switchDraft(() => reset('element'))}>+ Элемент</button><button disabled={busy} on:click={() => switchDraft(() => reset('community'))}>+ Сообщество</button><button disabled={busy} on:click={startLink}>+ Связь</button></div>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    {#if notice}<p class="notice" role="status">{notice}</p>{/if}
    {#if mode === 'welcome'}<p class="hint">Нажмите на узел или линию графа для редактирования. Здесь также видны скрытые узлы — посетители их не видят.</p>{/if}
    {#if mode === 'node'}
      <form class="panel node-form" bind:this={nodeForm} on:submit|preventDefault={save}>
        <h2>{editing ? 'Редактировать' : 'Добавить'} {kind === 'element' ? 'элемент' : 'сообщество'}</h2>
        <p class="hint">Изменения сохраняются при переходе к другому узлу. Новый элемент можно сохранить без связей.</p>
        {#if kind === 'element'}<label>Название<input required maxlength="160" bind:value={title} disabled={busy} /></label>
        {:else if editing}<label>Сообщество<input value={title} disabled /></label>
        {:else}<label>Поиск сообщества<input placeholder="Начните вводить название" bind:value={communitySearch} disabled={busy} /></label><label>Существующее сообщество<select required bind:value={communityId} disabled={busy}><option value={null}>Выберите сообщество</option>{#each communityOptions as item}<option value={item.id}>{item.name}</option>{/each}</select></label><p class="hint">Каждое сообщество добавляется один раз; к нему можно провести несколько связей.</p>{/if}
        <label>Описание<textarea rows="3" maxlength="4000" bind:value={description} disabled={busy}></textarea></label>
        <h3>Изображение карточки</h3>
        <p class="hint">JPEG, PNG, WebP или GIF, до 10 МБ. Автоматическая обрезка по центру до 640×360, WebP с качеством 75%. Для GIF сохраняется первый кадр. Загрузка сразу сохраняет узел и изображение.</p>
        {#if imageUrl}<img class="image-preview" src={api.imageUrl(imageUrl)} alt="Изображение карточки" width="640" height="360" decoding="async" />{/if}
        <label>{imageUrl ? 'Заменить изображение' : 'Загрузить изображение'}<input type="file" accept="image/jpeg,image/png,image/webp,image/gif" disabled={busy} on:change={uploadImage} /></label>
        {#if imageUrl && editing}<button type="button" class="danger" disabled={busy} on:click={() => action(() => api.removeImage(editing!), 'Изображение удалено.')}>Удалить изображение</button>{/if}
        <h3>Свойства</h3><p class="hint">В каждом списке можно выбрать несколько вариантов. Незаполненные свойства не ограничивают узел, пока посетитель не включил соответствующий фильтр.</p>
        <PropertyPicker properties={data.properties} bind:selected={propertyIds} disabled={busy} emptyLabel="Не задано" />
        <label class="checkbox"><input type="checkbox" bind:checked={showProperties} disabled={busy} />Показывать свойства в карточке и на графе</label><p class="hint">Скрытые свойства по-прежнему учитываются в фильтрах.</p>
        <label class="checkbox"><input type="checkbox" bind:checked={active} disabled={busy} />Показывать узел на публичном графе</label>
        <div class="actions"><button type="submit" class="primary" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить'}</button>{#if editing}<button type="button" class="connect-button" disabled={busy} on:click={() => startLink()}>Добавить связь</button><button type="button" class="danger" disabled={busy} on:click={remove}>Удалить из графа</button>{/if}</div>
      </form>

      {#if editing}
        <section class="connections"><h3>Связи узла · {attachedEdges.length}</h3>
          {#each attachedEdges as edge (edge.id)}<div class="edge-row"><span>{nodeNames.get(edge.source)} → {nodeNames.get(edge.target)}</span><button disabled={busy} on:click={() => editEdge(edge)}>Изменить</button><button class="danger" disabled={busy} on:click={() => removeLink(edge)}>Удалить</button></div>{/each}
        </section>
      {/if}
    {:else if mode === 'link'}
      <form class="link-form" on:submit|preventDefault={saveLink}>
        <h2>{edgeId ? 'Изменить связь' : 'Добавить связь'}</h2>
        <p class="hint">Найдите два узла или выберите их прямо на графе. Между увлечениями направление идёт от первого ко второму.</p>
        <NodeSearch id="edge-source" label="Первый узел" nodes={data.nodes} bind:selected={source} exclude={target} disabled={busy} />
        <button type="button" disabled={busy} on:click={() => { picking = 'source'; collapsed = true }}>Выбрать первую точку на графе</button>
        <NodeSearch id="edge-target" label="Второй узел" nodes={data.nodes} bind:selected={target} exclude={source} disabled={busy} />
        <button type="button" disabled={busy} on:click={() => { picking = 'target'; collapsed = true }}>Выбрать вторую точку на графе</button>
        <div class="actions"><button class="primary" disabled={busy || source === null || target === null}>Сохранить связь</button>
          {#if edgeId}<button type="button" class="danger" disabled={busy} on:click={() => removeLink(data.edges.find(edge => edge.id === edgeId)!)}>Удалить связь</button>{/if}
        </div>
      </form>
    {/if}
    <div class="footer"><button disabled={busy} on:click={refresh}>Обновить граф</button>{#if dirty}<button disabled={busy} on:click={discard}>Отменить изменения</button>{/if}</div>
  </div>
</aside>
<style>
  .graph-editor{position:absolute;z-index:6;top:92px;right:20px;bottom:76px;width:370px;max-width:calc(100% - 40px);display:flex;flex-direction:column;border:1px solid #b2b8ca60;border-radius:16px;background:var(--explore-surface,#fff);color:var(--explore-ink,#303b50);box-shadow:0 10px 32px #30375124;overflow:hidden}
  .graph-editor.collapsed{bottom:auto}
  header{display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #b2b8ca40;flex-shrink:0}header strong{flex:1;font-size:14px}header button{font-size:11px}header button:last-child{font-size:26px;min-width:36px;min-height:36px}
  .editor-content{padding:16px;overflow:auto;min-height:0;overscroll-behavior:contain}.editor-content[hidden]{display:none}
  h2{font-size:16px;font-weight:600;margin:16px 0}h3{font-size:13px;font-weight:600;margin-top:20px}
  .new-buttons,.actions{display:flex;gap:8px;flex-wrap:wrap}.new-buttons button{padding:8px;background:#8174ce16;border-radius:8px;color:#8174ce;font-size:12px}
  label{display:grid;gap:8px;font-size:12px;margin:16px 0}input:not([type=checkbox]),textarea,select{width:100%;box-sizing:border-box;border:1px solid #b2b8ca60;border-radius:9px;padding:10px;font-size:13px;background:transparent;color:inherit}
  .checkbox{display:flex;align-items:center;gap:10px;line-height:1.5}.checkbox input{accent-color:#8174ce}.hint{font-size:12px;line-height:1.6;color:#8790a3;margin:10px 0 16px}.image-preview{display:block;width:100%;height:auto;aspect-ratio:16/9;object-fit:cover;border-radius:10px}
  .actions{margin-top:20px;align-items:center}.primary{background:#7969be;color:#fff;padding:10px 14px;border-radius:9px;font-size:12px}.danger{color:#bd5555;font-size:12px}.connect-button{font-size:12px;color:#8174ce}.error,.notice{padding:10px;border-radius:9px;font-size:12px;margin-top:12px}.error{background:#fff0ee;color:#a33d39}.notice{background:#ecf7f0;color:#37825b}
  .connections{border-top:1px solid #b2b8ca40;margin-top:20px}.edge-row{display:flex;gap:8px;flex-wrap:wrap;padding:12px 0;border-bottom:1px solid #b2b8ca40;font-size:12px}.edge-row span{width:100%;overflow-wrap:anywhere}.edge-row button{font-size:12px}.link-form>button{color:#8174ce;font-size:12px;margin:8px 0 20px}.footer{display:flex;justify-content:space-between;font-size:11px;color:#8790a3;margin-top:24px}button{cursor:pointer}button:disabled{opacity:.5;cursor:wait}button:focus-visible{outline:2px solid #8174ce;outline-offset:2px}
  @media(max-width:700px){.graph-editor{top:auto;bottom:70px;right:10px;left:10px;width:auto;max-width:none;max-height:60%}.graph-editor.collapsed{top:auto;bottom:70px}header{padding:8px 12px}.editor-content{padding:12px}}
</style>
