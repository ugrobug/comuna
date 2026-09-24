<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import {
    backendAuthorPath,
    buildBackendPostPath,
    buildSearchSuggestionsUrl,
    type SearchSuggestionPayload,
  } from '$lib/api/backend'
  import { t } from '$lib/translations'
  import {
    DocumentText,
    Icon,
    MagnifyingGlass,
    UserCircle,
    UserGroup,
  } from 'svelte-hero-icons'
  import { onDestroy } from 'svelte'
  import { SuggestionController } from '$lib/search/SuggestionController'

  type Suggestion = {
    key: string
    href: string
    title: string
    description?: string
    image?: string | null
    type: 'post' | 'author' | 'community'
  }

  type SuggestionGroup = {
    type: Suggestion['type']
    items: Suggestion[]
  }

  export let compact = false
  export let placeholder: string | undefined = undefined

  let query = ''
  let suggestionGroups: SuggestionGroup[] = []
  let loading = false
  let open = false
  let failed = false
  let syncedRoute = ''
  let rootElement: HTMLDivElement

  const stripText = (value: string | null | undefined, max = 96) => {
    const normalized = String(value ?? '').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim()
    if (normalized.length <= max) return normalized
    return `${normalized.slice(0, max).trim()}...`
  }

  const buildSuggestionGroups = (payload: SearchSuggestionPayload): SuggestionGroup[] => {
    const communities = (payload.communities ?? []).slice(0, 3).map((community) => ({
      key: `community-${community.id}`,
      href: `/comuns/${encodeURIComponent(community.slug)}`,
      title: community.name,
      description: stripText(community.product_description),
      image: community.logo_url,
      type: 'community' as const,
    }))

    const posts = (payload.posts ?? []).slice(0, 5).map((post) => ({
      key: `post-${post.id}`,
      href: buildBackendPostPath(post),
      title: post.title,
      description: stripText(post.description),
      image: post.thumbnail_url,
      type: 'post' as const,
    }))

    const authors = (payload.authors ?? []).slice(0, 3).map((author) => ({
      key: `author-${author.username}`,
      href: backendAuthorPath(author) || `/${author.username}`,
      title: author.title || author.username,
      description: stripText(author.description || author.username),
      image: author.avatar_url,
      type: 'author' as const,
    }))

    return [
      { type: 'community' as const, items: communities },
      { type: 'post' as const, items: posts },
      { type: 'author' as const, items: authors },
    ].filter((group) => group.items.length)
  }

  const controller = new SuggestionController<SearchSuggestionPayload>(
    async (value, signal) => {
      const response = await fetch(buildSearchSuggestionsUrl(value), { signal })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      const cacheControl = response.headers.get('Cache-Control') || ''
      return {
        payload: await response.json(),
        cacheable: cacheControl.includes('public') && !cacheControl.includes('no-store'),
      }
    },
    (state) => {
      open = state.open
      loading = state.loading
      failed = Boolean(state.failed)
      suggestionGroups = state.payload ? buildSuggestionGroups(state.payload) : []
    },
  )

  const submitSearch = async () => {
    const normalized = query.trim()
    if (!normalized) return
    controller.close()
    await goto(`/search?q=${encodeURIComponent(normalized)}&type=All`)
  }

  const selectSuggestion = () => {
    controller.close()
  }

  const closeFromOutside = (event: MouseEvent) => {
    if (!rootElement?.contains(event.target as Node)) {
      controller.close()
    }
  }

  const iconForType = (type: Suggestion['type']) => {
    if (type === 'community') return UserGroup
    if (type === 'author') return UserCircle
    return DocumentText
  }

  $: typeLabel = {
    post: $t('content.posts'),
    author: $t('content.users'),
    community: $t('content.communities'),
  }
  $: suggestionsCount = suggestionGroups.reduce((total, group) => total + group.items.length, 0)

  $: {
    const route = `${$page.url.pathname}?${$page.url.searchParams.get('q') || ''}`
    if (route !== syncedRoute) {
      syncedRoute = route
      controller.close()
      if ($page.url.pathname === '/search') query = $page.url.searchParams.get('q') || ''
    }
  }

  onDestroy(() => controller.destroy())
</script>

<svelte:window on:mousedown={closeFromOutside} />

<div bind:this={rootElement} class="relative w-full">
  <form on:submit|preventDefault={submitSearch} class="relative">
    <Icon
      src={MagnifyingGlass}
      size="16"
      mini
      class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500"
    />
    <input
      bind:value={query}
      type="search"
      maxlength="512"
      autocomplete="off"
      spellcheck="false"
      class="h-9 w-full rounded-full border border-slate-200 bg-white/80 py-0 pl-9 pr-3 text-sm text-slate-900 outline-none transition focus:border-primary-400 focus:bg-white focus:ring-2 focus:ring-primary-500/20 dark:border-zinc-800 dark:bg-zinc-950/70 dark:text-zinc-100 dark:focus:border-primary-500 {compact ? 'h-10 text-base' : ''}"
      placeholder={placeholder || $t('nav.search')}
      aria-label={$t('nav.search')}
      on:input={(event) => controller.search(event.currentTarget.value)}
      on:focus={() => controller.search(query)}
      on:keydown={(event) => {
        if (event.key === 'Escape') controller.close()
      }}
    />
  </form>

  {#if open && (loading || suggestionsCount || query.trim().length >= 2)}
    <div
      class="absolute left-0 right-0 top-full z-[160] mt-2 overflow-hidden rounded-xl border border-slate-200/80 bg-white shadow-xl dark:border-zinc-800 dark:bg-zinc-900"
    >
      {#if loading}
        <div class="flex items-center gap-2 px-3 py-3 text-sm text-slate-500 dark:text-zinc-400">
          <span class="h-3 w-3 rounded-full border-2 border-slate-300 border-t-primary-500 animate-spin"></span>
          {$t('nav.search')}
        </div>
      {:else if failed}
        <div role="alert" class="px-3 py-3 text-sm text-red-600">{$t('message.error')}</div>
      {:else if suggestionsCount}
        <div class="max-h-[70vh] overflow-y-auto py-1">
          {#each suggestionGroups as group (group.type)}
            <section class="py-1">
              <div class="px-3 pb-1 pt-1.5 text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-500">
                {typeLabel[group.type]}
              </div>
              {#each group.items as suggestion (suggestion.key)}
                <a
                  href={suggestion.href}
                  class="flex min-w-0 items-center gap-2 px-3 py-2.5 transition hover:bg-slate-50 dark:hover:bg-zinc-800"
                  on:click={selectSuggestion}
                >
                  <div class="flex h-9 w-9 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg bg-slate-100 text-slate-500 dark:bg-zinc-800 dark:text-zinc-400">
                    {#if suggestion.image}
                      <img src={suggestion.image} alt="" width="36" height="36" decoding="async" class="h-full w-full object-cover" />
                    {:else}
                      <Icon src={iconForType(suggestion.type)} size="18" mini />
                    {/if}
                  </div>
                  <div class="min-w-0 flex-1">
                    <div class="truncate text-sm font-medium text-slate-900 dark:text-zinc-100">
                      {suggestion.title}
                    </div>
                    {#if suggestion.description}
                      <div class="truncate text-xs text-slate-500 dark:text-zinc-400">
                        {suggestion.description}
                      </div>
                    {/if}
                  </div>
                </a>
              {/each}
            </section>
          {/each}
        </div>
      {:else}
        <div class="px-3 py-3 text-sm text-slate-500 dark:text-zinc-400">
          {$t('routes.search.noResults.title')}
        </div>
      {/if}
      <button
        type="button"
        class="flex w-full items-center justify-between border-t border-slate-100 px-3 py-2 text-left text-sm text-primary-700 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-primary-300 dark:hover:bg-zinc-800"
        on:click={submitSearch}
      >
        <span>{$t('routes.search.title')}</span>
        <span class="truncate text-xs text-slate-500 dark:text-zinc-400">{query.trim()}</span>
      </button>
    </div>
  {/if}
</div>
