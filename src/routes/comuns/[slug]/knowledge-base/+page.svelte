<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import {
    buildComunKnowledgeBaseItemUrl,
    buildComunKnowledgeBaseUrl,
    type BackendComun,
    type BackendComunKnowledgeBaseItem,
  } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import { toast } from 'mono-svelte'

  export let data

  let comun: BackendComun | null = data?.comun ?? null
  let items: BackendComunKnowledgeBaseItem[] = data?.items ?? []
  let flatItems: BackendComunKnowledgeBaseItem[] = data?.flatItems ?? []
  let saving = false
  let errorMessage = ''
  let draggedItemId: number | null = null
  let dragOverKey = ''

  $: canManage = Boolean($siteToken && comun?.can_moderate)
  $: comunBackPath = comun?.slug ? `/comuns/${encodeURIComponent(comun.slug)}` : '/comuns'
  $: itemById = new Map(flatItems.map((item) => [Number(item.id), item]))

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const applyPayload = (payload: Record<string, unknown>) => {
    items = (payload.items as BackendComunKnowledgeBaseItem[] | undefined) ?? items
    flatItems =
      (payload.flat_items as BackendComunKnowledgeBaseItem[] | undefined) ??
      (payload.flatItems as BackendComunKnowledgeBaseItem[] | undefined) ??
      flatItems
  }

  const itemTitle = (item: BackendComunKnowledgeBaseItem) =>
    String(item.title || (item.item_type === 'group' ? 'Группа' : 'Пост')).trim()

  const itemLevelStyle = (item: BackendComunKnowledgeBaseItem) =>
    `padding-left: ${Math.min(Number(item.depth ?? 0), 8) * 1.25}rem`

  const normalizedParentId = (parentId: unknown) => {
    const parsed = Number(parentId ?? 0)
    if (!Number.isFinite(parsed) || parsed <= 0) return null
    return itemById.has(parsed) ? parsed : null
  }

  const itemParentId = (item: BackendComunKnowledgeBaseItem) => normalizedParentId(item.parent_id)

  const itemFrameClass = (item: BackendComunKnowledgeBaseItem) => {
    const dragState = `${dragOverKey === `into-${item.id}` ? ' ring-2 ring-blue-200 dark:ring-blue-900/60' : ''}${draggedItemId === Number(item.id) ? ' opacity-50' : ''}`
    const dragClass = canManage ? ' cursor-grab active:cursor-grabbing' : ''
    if (item.item_type === 'group') {
      return `mt-5 border-b border-slate-200 pb-2 pt-1 transition dark:border-zinc-800${dragClass}${dragState}`
    }
    return `rounded-lg border border-transparent bg-transparent px-2 py-1.5 transition hover:bg-slate-50 dark:hover:bg-zinc-900/70${dragClass}${dragState}`
  }

  const childItems = (parentId: number | null) =>
    flatItems.filter((item) => Number(itemParentId(item) ?? 0) === Number(parentId ?? 0))

  const itemDescendantIds = (itemId: number) => {
    const result = new Set<number>()
    const visit = (parentId: number) => {
      for (const child of childItems(parentId)) {
        const childId = Number(child.id)
        result.add(childId)
        visit(childId)
      }
    }
    visit(itemId)
    return result
  }

  const canMoveInto = (itemId: number, parentId: number | null) => {
    if (!parentId) return true
    if (itemId === parentId) return false
    return !itemDescendantIds(itemId).has(parentId)
  }

  const updateItem = async (
    item: BackendComunKnowledgeBaseItem,
    patch: Partial<BackendComunKnowledgeBaseItem>
  ) => patchItem(item, patch, true)

  const patchItem = async (
    item: BackendComunKnowledgeBaseItem,
    patch: Partial<BackendComunKnowledgeBaseItem>,
    showToast = false
  ) => {
    if (!comun?.slug || !canManage) return null
    const response = await fetch(buildComunKnowledgeBaseItemUrl(comun.slug, item.id), {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify(patch),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(payload?.error || 'Не удалось обновить базу знаний')
    }
    applyPayload(payload)
    if (showToast) toast({ content: 'База знаний обновлена', type: 'success' })
    return payload
  }

  const createGroup = async (title: string, parentId: number | null) => {
    if (!comun?.slug || !canManage) return null
    const response = await fetch(buildComunKnowledgeBaseUrl(comun.slug), {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ title, parent_id: parentId }),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) {
      throw new Error(payload?.error || 'Не удалось создать группу')
    }
    applyPayload(payload)
    return payload?.item as BackendComunKnowledgeBaseItem | undefined
  }

  const persistSiblingOrder = async (
    parentId: number | null,
    orderedIds: number[],
    movedItemId?: number,
    fallbackItems: Map<number, BackendComunKnowledgeBaseItem> = new Map()
  ) => {
    let payload: Record<string, unknown> | null = null
    for (const [index, itemId] of orderedIds.entries()) {
      const item = itemById.get(itemId) ?? fallbackItems.get(itemId)
      if (!item) continue
      const patch: Partial<BackendComunKnowledgeBaseItem> = { sort_order: (index + 1) * 10 }
      if (itemId === movedItemId || Number(itemParentId(item) ?? 0) !== Number(parentId ?? 0)) {
        patch.parent_id = parentId
      }
      payload = await patchItem(item, patch)
    }
    if (payload) applyPayload(payload)
  }

  const moveRelativeToItem = async (
    draggedId: number,
    target: BackendComunKnowledgeBaseItem,
    position: 'before' | 'after'
  ) => {
    const dragged = itemById.get(draggedId)
    if (!dragged || draggedId === Number(target.id)) return

    const parentId = itemParentId(target)
    if (!canMoveInto(draggedId, parentId)) {
      throw new Error('Нельзя вложить группу в саму себя')
    }

    const orderedIds = childItems(parentId)
      .map((item) => Number(item.id))
      .filter((itemId) => itemId !== draggedId)
    const targetIndex = orderedIds.indexOf(Number(target.id))
    const insertIndex = position === 'before' ? targetIndex : targetIndex + 1
    orderedIds.splice(Math.max(insertIndex, 0), 0, draggedId)
    await persistSiblingOrder(parentId, orderedIds, draggedId)
  }

  const moveIntoGroup = async (draggedId: number, group: BackendComunKnowledgeBaseItem) => {
    const dragged = itemById.get(draggedId)
    const groupId = Number(group.id)
    if (!dragged || draggedId === groupId) return
    if (!canMoveInto(draggedId, groupId)) {
      throw new Error('Нельзя вложить группу в саму себя')
    }
    const orderedIds = [
      ...childItems(groupId)
        .map((item) => Number(item.id))
        .filter((itemId) => itemId !== draggedId),
      draggedId,
    ]
    await persistSiblingOrder(groupId, orderedIds, draggedId)
  }

  const createGroupFromDrop = async (
    draggedId: number,
    target: BackendComunKnowledgeBaseItem
  ) => {
    const dragged = itemById.get(draggedId)
    if (!dragged || draggedId === Number(target.id)) return
    const title = window.prompt('Название группы')
    if (!title?.trim()) return

    const parentId = itemParentId(target)
    const group = await createGroup(title.trim(), parentId)
    const groupId = Number(group?.id ?? 0)
    if (!groupId) throw new Error('Не удалось создать группу')

    const originalSiblings = childItems(parentId)
      .map((item) => Number(item.id))
      .filter((itemId) => itemId !== draggedId)
    const targetIndex = originalSiblings.indexOf(Number(target.id))
    const parentSiblings = originalSiblings.filter((itemId) => itemId !== Number(target.id))
    parentSiblings.splice(Math.max(targetIndex, 0), 0, groupId)
    await persistSiblingOrder(parentId, parentSiblings, groupId, new Map([[groupId, group]]))
    await patchItem(target, { parent_id: groupId, sort_order: 10 })
    await patchItem(dragged, { parent_id: groupId, sort_order: 20 })
  }

  const withDragSave = async (action: () => Promise<void>) => {
    if (saving || !canManage) return
    saving = true
    errorMessage = ''
    try {
      await action()
      toast({ content: 'База знаний обновлена', type: 'success' })
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Не удалось обновить базу знаний'
      toast({ content: errorMessage, type: 'error' })
    } finally {
      saving = false
      draggedItemId = null
      dragOverKey = ''
    }
  }

  const onDragStart = (event: DragEvent, item: BackendComunKnowledgeBaseItem) => {
    if (!canManage) return
    draggedItemId = Number(item.id)
    event.dataTransfer?.setData('text/plain', String(item.id))
    if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
  }

  const onDragEnd = () => {
    draggedItemId = null
    dragOverKey = ''
  }

  const draggedIdFromEvent = (event: DragEvent) =>
    Number(event.dataTransfer?.getData('text/plain') || draggedItemId || 0)

  const onDropZone = (event: DragEvent, target: BackendComunKnowledgeBaseItem, position: 'before' | 'after') => {
    event.preventDefault()
    const draggedId = draggedIdFromEvent(event)
    if (!draggedId) return
    withDragSave(() => moveRelativeToItem(draggedId, target, position))
  }

  const onDropItem = (event: DragEvent, target: BackendComunKnowledgeBaseItem) => {
    event.preventDefault()
    const draggedId = draggedIdFromEvent(event)
    if (!draggedId || draggedId === Number(target.id)) return
    withDragSave(() =>
      target.item_type === 'group'
        ? moveIntoGroup(draggedId, target)
        : createGroupFromDrop(draggedId, target)
    )
  }

  const deleteItem = async (item: BackendComunKnowledgeBaseItem) => {
    if (!comun?.slug || !canManage || saving) return
    const confirmed = window.confirm('Удалить элемент из базы знаний? Сам пост не будет удален.')
    if (!confirmed) return
    saving = true
    errorMessage = ''
    try {
      const response = await fetch(buildComunKnowledgeBaseItemUrl(comun.slug, item.id), {
        method: 'DELETE',
        headers: authHeaders(),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось удалить элемент')
      }
      applyPayload(payload)
      toast({ content: 'Элемент удален', type: 'success' })
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Не удалось удалить элемент'
      toast({ content: errorMessage, type: 'error' })
    } finally {
      saving = false
    }
  }

  const onTitleChange = (item: BackendComunKnowledgeBaseItem, event: Event) => {
    const title = (event.currentTarget as HTMLElement | null)?.textContent?.trim() ?? ''
    if (!title || title === itemTitle(item)) return
    saving = true
    updateItem(item, { title })
      .catch((error) => {
        errorMessage = error instanceof Error ? error.message : 'Не удалось обновить заголовок'
        toast({ content: errorMessage, type: 'error' })
      })
      .finally(() => {
        saving = false
      })
  }
</script>

<div class="flex w-full flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="min-w-0">
      <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
        Сообщество
      </div>
      <Header noMargin>База знаний</Header>
      {#if comun?.name}
        <div class="truncate text-sm text-slate-600 dark:text-zinc-400">{comun.name}</div>
      {/if}
    </div>
    <a
      href={comunBackPath}
      class="inline-flex items-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-800/60"
    >
      Назад к сообществу
    </a>
  </div>

  {#if errorMessage}
    <div class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300">
      {errorMessage}
    </div>
  {/if}

  <section class="rounded-2xl border border-slate-200 bg-white/95 p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
    {#if canManage}
      <div class="mb-4 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400">
        Перетащите элемент выше или ниже другого, чтобы поменять порядок. Перетащите на группу, чтобы вложить. Перетащите запись на запись, чтобы создать новую группу.
      </div>
    {/if}
    {#if flatItems.length}
      <div class={canManage ? 'flex flex-col gap-0' : 'flex flex-col gap-2'}>
        {#each flatItems as item (item.id)}
          {#if canManage}
            <div
              class="h-1 rounded-full transition {dragOverKey === `before-${item.id}` ? 'bg-blue-200 dark:bg-blue-900/50' : 'bg-transparent'}"
              role="presentation"
              on:dragenter={() => (dragOverKey = `before-${item.id}`)}
              on:dragover|preventDefault={() => (dragOverKey = `before-${item.id}`)}
              on:drop={(event) => onDropZone(event, item, 'before')}
            ></div>
          {/if}
          <article
            draggable={canManage && !saving}
            class={itemFrameClass(item)}
            style={itemLevelStyle(item)}
            on:dragstart={(event) => onDragStart(event, item)}
            on:dragend={onDragEnd}
            on:dragenter={() => (dragOverKey = `into-${item.id}`)}
            on:dragover|preventDefault={() => (dragOverKey = `into-${item.id}`)}
            on:drop={(event) => onDropItem(event, item)}
          >
            {#if canManage}
              <div class="group flex items-center gap-2">
                <div class="flex h-6 w-4 shrink-0 items-center justify-center text-xs text-slate-300 transition group-hover:text-slate-500 dark:text-zinc-600 dark:group-hover:text-zinc-400" aria-hidden="true">
                  ⋮⋮
                </div>
                {#if item.item_type === 'group'}
                  <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs text-slate-600 dark:bg-zinc-800 dark:text-zinc-300" aria-hidden="true">▾</span>
                  <div
                    class="min-w-0 flex-1 rounded-md px-1 py-0.5 text-lg font-bold text-slate-950 outline-none focus:bg-white focus:ring-2 focus:ring-blue-200 dark:text-zinc-50 dark:focus:bg-zinc-950 dark:focus:ring-blue-900"
                    contenteditable="true"
                    role="textbox"
                    tabindex="0"
                    on:blur={(event) => onTitleChange(item, event)}
                    on:keydown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        ;(event.currentTarget as HTMLElement).blur()
                      }
                    }}
                  >{itemTitle(item)}</div>
                {:else}
                  {#if item.post_path}
                    <a
                      href={item.post_path}
                      class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs text-slate-500 transition hover:bg-blue-50 hover:text-blue-700 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-blue-950/40 dark:hover:text-blue-300"
                      aria-label="Открыть статью"
                      title="Открыть статью"
                    >
                      ↗
                    </a>
                  {:else}
                    <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs text-slate-500 dark:bg-zinc-800 dark:text-zinc-400" aria-hidden="true">·</span>
                  {/if}
                  <div
                    class="min-w-0 flex-1 truncate rounded-md px-1 py-0.5 text-base font-medium text-slate-800 outline-none underline-offset-4 focus:bg-white focus:ring-2 focus:ring-blue-200 dark:text-zinc-100 dark:focus:bg-zinc-950 dark:focus:ring-blue-900"
                    contenteditable="true"
                    role="textbox"
                    tabindex="0"
                    on:blur={(event) => onTitleChange(item, event)}
                    on:keydown={(event) => {
                      if (event.key === 'Enter') {
                        event.preventDefault()
                        ;(event.currentTarget as HTMLElement).blur()
                      }
                    }}
                  >{itemTitle(item)}</div>
                {/if}
                <button
                  type="button"
                  class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-lg leading-none text-slate-300 opacity-70 transition hover:bg-rose-50 hover:text-rose-700 group-hover:opacity-100 dark:text-zinc-600 dark:hover:bg-rose-950/30 dark:hover:text-rose-300"
                  on:click={() => deleteItem(item)}
                  disabled={saving}
                  aria-label="Удалить из базы знаний"
                  title="Удалить"
                >
                  ×
                </button>
              </div>
            {:else if item.item_type === 'group'}
              <div class="flex items-center gap-2">
                <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs text-slate-600 dark:bg-zinc-800 dark:text-zinc-300" aria-hidden="true">▾</span>
                <div class="text-lg font-bold text-slate-950 dark:text-zinc-50">
                  {itemTitle(item)}
                </div>
              </div>
            {:else if item.post_path}
              <a
                href={item.post_path}
                class="group inline-flex min-w-0 items-center gap-2 text-base font-medium text-slate-800 dark:text-zinc-100"
              >
                <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs text-slate-500 transition group-hover:bg-blue-50 group-hover:text-blue-700 dark:bg-zinc-800 dark:text-zinc-400 dark:group-hover:bg-blue-950/40 dark:group-hover:text-blue-300" aria-hidden="true">↗</span>
                <span class="truncate underline-offset-4 group-hover:underline">{itemTitle(item)}</span>
              </a>
            {:else}
              <div class="inline-flex min-w-0 items-center gap-2 text-base font-medium text-slate-800 dark:text-zinc-100">
                <span class="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-slate-100 text-xs text-slate-500 dark:bg-zinc-800 dark:text-zinc-400" aria-hidden="true">·</span>
                <span class="truncate">{itemTitle(item)}</span>
              </div>
            {/if}
          </article>
          {#if canManage}
            <div
              class="h-1 rounded-full transition {dragOverKey === `after-${item.id}` ? 'bg-blue-200 dark:bg-blue-900/50' : 'bg-transparent'}"
              role="presentation"
              on:dragenter={() => (dragOverKey = `after-${item.id}`)}
              on:dragover|preventDefault={() => (dragOverKey = `after-${item.id}`)}
              on:drop={(event) => onDropZone(event, item, 'after')}
            ></div>
          {/if}
        {/each}
      </div>
    {:else}
      <div class="rounded-2xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 dark:border-zinc-700 dark:text-zinc-400">
        В базе знаний пока нет статей.
      </div>
    {/if}
  </section>
</div>
