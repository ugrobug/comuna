<script lang="ts">
  import { onMount } from 'svelte'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { Trophy, Icon } from 'svelte-hero-icons'
  import { buildTopAuthorsMonthUrl } from '$lib/api/backend'

  type TopAuthor = {
    username: string
    title?: string | null
    avatar_url?: string | null
    channel_url?: string | null
    month_score: number
    month_posts: number
  }

  let authors: TopAuthor[] = []
  let loading = true
  let error: string | null = null

  async function fetchTopAuthors() {
    try {
      const response = await fetch(buildTopAuthorsMonthUrl(5))
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const data = await response.json()
      authors = data.authors ?? []
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Неизвестная ошибка'
    } finally {
      loading = false
    }
  }

  onMount(fetchTopAuthors)
</script>

<div class="flex flex-col gap-2 bg-white dark:bg-zinc-900 rounded-xl p-4">
  <span class="text-base font-normal text-slate-900 dark:text-zinc-200 mb-2">
    Топ авторов за месяц
  </span>

  {#if loading}
    <div class="animate-pulse space-y-3">
      {#each Array(5) as _}
        <div class="h-4 bg-slate-100 dark:bg-zinc-800 rounded"></div>
      {/each}
    </div>
  {:else if error}
    <div class="text-sm text-red-500">
      {error}
    </div>
  {:else if authors.length === 0}
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      Нет данных за месяц
    </div>
  {:else}
    <div class="flex flex-col divide-y divide-slate-200 dark:divide-zinc-800">
      {#each authors as author}
        <a
          href={`/${author.username}`}
          class="block group py-3 first:pt-1 last:pb-1"
        >
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-2">
              <Avatar
                url={author.avatar_url || undefined}
                alt={author.title || author.username}
                width={32}
                class_="w-8 h-8 rounded-full"
              />
              <span class="text-sm font-medium text-slate-900 dark:text-zinc-200">
                {author.title || author.username}
              </span>
            </div>
            <div class="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-zinc-400">
              <span class="flex items-center gap-1">
                <Icon src={Trophy} size="14" class="text-amber-500" />
                {author.month_score}
              </span>
              <span class="flex items-center gap-1">
                {author.month_posts} постов
              </span>
            </div>
          </div>
        </a>
      {/each}
    </div>
  {/if}
</div> 
