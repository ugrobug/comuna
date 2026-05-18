<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import {
    buildComunKnowledgeBaseItemUrl,
    buildComunKnowledgeBaseUrl,
    type BackendComun,
    type BackendComunKnowledgeBaseItem,
  } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import { Button, toast } from 'mono-svelte'

  export let data

  let comun: BackendComun | null = data?.comun ?? null
  let items: BackendComunKnowledgeBaseItem[] = data?.items ?? []
  let flatItems: BackendComunKnowledgeBaseItem[] = data?.flatItems ?? []
  let groupTitle = ''
  let saving = false
  let errorMessage = ''

  $: canManage = Boolean($siteToken && comun?.can_moderate)
  $: comunBackPath = comun?.slug ? `/comuns/${encodeURIComponent(comun.slug)}` : '/comuns'
  $: groupOptions = flatItems.filter((item) => item.item_type === 'group')

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

  const availableParents = (item: BackendComunKnowledgeBaseItem) =>
    groupOptions.filter((group) => Number(group.id) !== Number(item.id))

  const addGroup = async () => {
    if (!comun?.slug || !canManage || saving) return
    const title = groupTitle.trim()
    if (!title) {
      errorMessage = 'Введите название группы'
      return
    }
    saving = true
    errorMessage = ''
    try {
      const response = await fetch(buildComunKnowledgeBaseUrl(comun.slug), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ title }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось добавить группу')
      }
      applyPayload(payload)
      groupTitle = ''
      toast({ content: 'Группа добавлена', type: 'success' })
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Не удалось добавить группу'
      toast({ content: errorMessage, type: 'error' })
    } finally {
      saving = false
    }
  }

  const updateItem = async (
    item: BackendComunKnowledgeBaseItem,
    patch: Partial<BackendComunKnowledgeBaseItem>
  ) => {
    if (!comun?.slug || !canManage || saving) return
    saving = true
    errorMessage = ''
    try {
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
      toast({ content: 'База знаний обновлена', type: 'success' })
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Не удалось обновить базу знаний'
      toast({ content: errorMessage, type: 'error' })
    } finally {
      saving = false
    }
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

  {#if canManage}
    <section class="rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
      <div class="text-base font-semibold text-slate-900 dark:text-zinc-100">
        Управление базой знаний
      </div>
      <div class="mt-3 flex flex-col gap-2 sm:flex-row">
        <input
          bind:value={groupTitle}
          type="text"
          placeholder="Название новой группы"
          class="min-w-0 flex-1 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
        />
        <Button on:click={addGroup} disabled={saving || !groupTitle.trim()}>
          Добавить группу
        </Button>
      </div>
    </section>
  {/if}

  <section class="rounded-2xl border border-slate-200 bg-white/95 p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
    {#if flatItems.length}
      <div class="flex flex-col gap-2">
        {#each flatItems as item (item.id)}
          <article
            class="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/60"
            style={itemLevelStyle(item)}
          >
            {#if canManage}
              <div class="grid gap-3 md:grid-cols-[minmax(0,1fr)_9rem_12rem_auto] md:items-center">
                <input
                  value={itemTitle(item)}
                  on:change={(event) =>
                    updateItem(item, { title: (event.currentTarget as HTMLInputElement).value })}
                  class="min-w-0 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
                />
                <input
                  value={Number(item.sort_order ?? 0)}
                  type="number"
                  on:change={(event) =>
                    updateItem(item, {
                      sort_order: Number((event.currentTarget as HTMLInputElement).value) || 0,
                    })}
                  class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
                  aria-label="Порядок"
                />
                <select
                  value={item.parent_id ?? ''}
                  on:change={(event) =>
                    updateItem(item, {
                      parent_id:
                        Number((event.currentTarget as HTMLSelectElement).value) || null,
                    })}
                  class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
                  aria-label="Родительская группа"
                >
                  <option value="">Без группы</option>
                  {#each availableParents(item) as parent}
                    <option value={parent.id}>{'—'.repeat(Number(parent.depth ?? 0))} {parent.title}</option>
                  {/each}
                </select>
                <button
                  type="button"
                  class="rounded-xl border border-rose-200 px-3 py-2 text-sm font-medium text-rose-700 transition hover:bg-rose-50 dark:border-rose-900/50 dark:text-rose-300 dark:hover:bg-rose-950/30"
                  on:click={() => deleteItem(item)}
                  disabled={saving}
                >
                  Удалить
                </button>
              </div>
              {#if item.item_type === 'post' && item.post_path}
                <a
                  href={item.post_path}
                  class="mt-2 inline-flex text-sm font-medium text-blue-700 hover:underline dark:text-blue-300"
                >
                  Открыть статью
                </a>
              {/if}
            {:else if item.item_type === 'group'}
              <div class="text-base font-semibold text-slate-900 dark:text-zinc-100">
                {itemTitle(item)}
              </div>
            {:else if item.post_path}
              <a
                href={item.post_path}
                class="text-base font-semibold text-slate-900 hover:underline dark:text-zinc-100"
              >
                {itemTitle(item)}
              </a>
            {:else}
              <div class="text-base font-semibold text-slate-900 dark:text-zinc-100">
                {itemTitle(item)}
              </div>
            {/if}
          </article>
        {/each}
      </div>
    {:else}
      <div class="rounded-2xl border border-dashed border-slate-300 px-4 py-8 text-center text-sm text-slate-500 dark:border-zinc-700 dark:text-zinc-400">
        В базе знаний пока нет статей.
      </div>
    {/if}
  </section>
</div>
