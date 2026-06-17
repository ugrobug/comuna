<script lang="ts">
  import { createEventDispatcher, onDestroy, tick } from 'svelte'
  import { buildComunWelcomePostOptionsUrl, type BackendPost } from '$lib/api/backend'

  export type WelcomePostOption = {
    id: number
    title: string
  }

  export let slug = ''
  export let token: string | null = null
  export let value: number | string | null | undefined = null
  export let selectedPost: BackendPost | null | undefined = null
  export let disabled = false
  export let limit = 5
  export let label = 'Приветственный пост'
  export let placeholder = 'Не выбран'
  export let searchPlaceholder = 'Поиск по названию'

  const dispatch = createEventDispatcher<{
    change: { postId: number | null; post: WelcomePostOption | null }
  }>()

  let options: WelcomePostOption[] = []
  let search = ''
  let open = false
  let loaded = false
  let loading = false
  let error = ''
  let searchTimer: ReturnType<typeof setTimeout> | null = null
  let requestSeq = 0
  let searchInput: HTMLInputElement | null = null

  const buildSelectedOption = (
    id: number,
    post: BackendPost | null | undefined,
    currentOptions: WelcomePostOption[]
  ): WelcomePostOption | null => {
    if (!id) return null
    const fromOptions = currentOptions.find((item) => item.id === id)
    if (fromOptions) return fromOptions
    if (Number(post?.id ?? 0) === id) {
      return { id, title: post?.title || `Пост ${id}` }
    }
    return { id, title: `Пост ${id}` }
  }

  $: selectedId = Number(value ?? selectedPost?.id ?? 0) || 0
  $: selectedOption = buildSelectedOption(selectedId, selectedPost, options)

  const setOptions = (items: WelcomePostOption[], includeSelected = true) => {
    const byId = new Map<number, WelcomePostOption>()
    if (includeSelected && selectedOption) byId.set(selectedOption.id, selectedOption)
    for (const item of items) byId.set(item.id, item)
    options = Array.from(byId.values())
  }

  const normalizeOptions = (items: any[]): WelcomePostOption[] =>
    items
      .map((item) => ({
        id: Number(item?.id ?? 0),
        title: String(item?.title ?? '').trim(),
      }))
      .filter((item) => item.id > 0 && item.title)

  const loadOptions = async (query = search) => {
    if (!slug || !token) return
    const requestId = ++requestSeq
    const normalizedQuery = query.trim()
    loading = true
    error = ''
    try {
      const response = await fetch(
        buildComunWelcomePostOptionsUrl(slug, {
          q: normalizedQuery,
          limit,
        }),
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      )
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить посты')
      }
      if (requestId !== requestSeq) return
      setOptions(normalizeOptions(Array.isArray(payload?.posts) ? payload.posts : []), !normalizedQuery)
      loaded = true
    } catch (requestError) {
      if (requestId !== requestSeq) return
      error = requestError instanceof Error ? requestError.message : 'Не удалось загрузить посты'
    } finally {
      if (requestId === requestSeq) loading = false
    }
  }

  const toggleOpen = () => {
    if (disabled) return
    if (open) {
      open = false
      return
    }
    open = true
    search = ''
    loaded = false
    error = ''
    setOptions([])
    void tick().then(() => searchInput?.focus())
    void loadOptions('')
  }

  const scheduleSearch = () => {
    if (!open) return
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      void loadOptions(search)
    }, 250)
  }

  const selectPost = (post: WelcomePostOption | null) => {
    dispatch('change', { postId: post?.id ?? null, post })
    open = false
    search = ''
  }

  onDestroy(() => {
    if (searchTimer) clearTimeout(searchTimer)
  })
</script>

<div class="flex flex-col gap-1">
  {#if label}
    <span class="text-sm text-slate-700 dark:text-zinc-300">{label}</span>
  {/if}
  <div class="relative">
    <button
      type="button"
      class="flex w-full items-center justify-between gap-3 rounded-xl border border-slate-300 bg-white px-3 py-2 text-left text-sm text-slate-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
      on:click={toggleOpen}
      disabled={disabled}
      aria-expanded={open}
    >
      <span class="min-w-0 truncate">
        {selectedOption ? selectedOption.title : placeholder}
      </span>
      <span class="shrink-0 text-xs text-slate-400">
        {open ? 'Закрыть' : 'Выбрать'}
      </span>
    </button>

    {#if open}
      <div
        class="absolute left-0 right-0 top-full z-30 mt-1 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg dark:border-zinc-700 dark:bg-zinc-900"
      >
        <div class="border-b border-slate-100 p-2 dark:border-zinc-800">
          <input
            bind:this={searchInput}
            bind:value={search}
            on:input={scheduleSearch}
            placeholder={searchPlaceholder}
            class="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
          />
        </div>
        <div class="max-h-64 overflow-y-auto py-1">
          <button
            type="button"
            class="block w-full px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-50 dark:text-zinc-300 dark:hover:bg-zinc-800"
            on:mousedown|preventDefault={() => selectPost(null)}
          >
            Не выбран
          </button>
          {#each options as option (option.id)}
            <button
              type="button"
              class="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50 dark:hover:bg-zinc-800 {selectedId === option.id
                ? 'bg-sky-50 text-sky-700 dark:bg-sky-950/40 dark:text-sky-300'
                : 'text-slate-900 dark:text-zinc-100'}"
              on:mousedown|preventDefault={() => selectPost(option)}
            >
              <span class="block truncate">{option.title}</span>
            </button>
          {/each}
          {#if loading}
            <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">Загрузка...</div>
          {:else if error}
            <div class="px-3 py-2 text-sm text-red-600">{error}</div>
          {:else if loaded && options.length === 0}
            <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">Постов не найдено</div>
          {/if}
        </div>
      </div>
    {/if}
  </div>
  {#if selectedOption}
    <button
      type="button"
      class="w-max rounded-lg px-2 py-1 text-sm font-medium text-rose-600 hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60 dark:text-rose-400 dark:hover:bg-rose-950/30"
      disabled={disabled}
      on:click={() => selectPost(null)}
    >
      Открепить пост
    </button>
  {/if}
</div>
