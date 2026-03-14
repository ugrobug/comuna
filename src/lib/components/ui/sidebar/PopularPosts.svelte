<script lang="ts">
  import { onMount } from 'svelte'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { Button } from 'mono-svelte'
  import { Trophy, Icon } from 'svelte-hero-icons'
  import { buildTopAuthorsUrl, type BackendTopAuthor } from '$lib/api/backend'

  const authorRatingHref = '/authors/rating'

  let authors: BackendTopAuthor[] = []
  let loading = true
  let error: string | null = null

  async function fetchTopAuthors() {
    try {
      const response = await fetch(buildTopAuthorsUrl({ period: 'month', limit: 5 }))
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

  const formatNumber = (value: number | undefined) => {
    if (!value && value !== 0) return '0'
    return value.toLocaleString('ru-RU')
  }

  const rankClassName = (index: number) => {
    if (index === 0) return 'rank-badge rank-badge--gold'
    if (index === 1) return 'rank-badge rank-badge--silver'
    if (index === 2) return 'rank-badge rank-badge--bronze'
    return 'rank-badge rank-badge--default'
  }

  const rowClassName = (index: number) => {
    if (index === 0) return 'author-row author-row--gold'
    if (index === 1) return 'author-row author-row--silver'
    if (index === 2) return 'author-row author-row--bronze'
    return 'author-row'
  }
</script>

<div class="flex flex-col gap-2 bg-white dark:bg-zinc-900 rounded-xl p-4">
  <a
    href={authorRatingHref}
    class="text-base font-normal text-slate-900 dark:text-zinc-200 mb-2 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
  >
    Топ авторов за месяц
  </a>

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
      {#each authors as author, index}
        <a
          href={`/${author.username}`}
          class={`${rowClassName(index)} block group py-3 first:pt-1 last:pb-1`}
        >
          <div class="flex flex-col gap-2">
            <div class="flex items-center gap-2">
              <div class={rankClassName(index)}>
                {index + 1}
              </div>
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
                {formatNumber(author.score)}
              </span>
              <span class="flex items-center gap-1">
                {formatNumber(author.posts_count)} постов
              </span>
            </div>
          </div>
        </a>
      {/each}
    </div>
    <Button
      href={authorRatingHref}
      color="ghost"
      rounding="xl"
      class="mt-3 w-full justify-center !text-sm"
    >
      Весь рейтинг
    </Button>
  {/if}
</div> 

<style>
  .author-row {
    border-radius: 1rem;
    margin: 0 -0.25rem;
    padding-left: 0.25rem;
    padding-right: 0.25rem;
    transition: background-color 0.15s ease;
  }

  .author-row:hover {
    background: rgb(248 250 252);
  }

  :global(.dark) .author-row:hover {
    background: rgb(39 39 42 / 0.8);
  }

  .author-row--gold {
    background: linear-gradient(90deg, rgb(254 243 199 / 0.9), transparent 55%);
  }

  .author-row--silver {
    background: linear-gradient(90deg, rgb(226 232 240 / 0.9), transparent 55%);
  }

  .author-row--bronze {
    background: linear-gradient(90deg, rgb(254 215 170 / 0.9), transparent 55%);
  }

  :global(.dark) .author-row--gold {
    background: linear-gradient(90deg, rgb(120 53 15 / 0.35), transparent 55%);
  }

  :global(.dark) .author-row--silver {
    background: linear-gradient(90deg, rgb(71 85 105 / 0.35), transparent 55%);
  }

  :global(.dark) .author-row--bronze {
    background: linear-gradient(90deg, rgb(124 45 18 / 0.35), transparent 55%);
  }

  .rank-badge {
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 0.75rem;
    font-weight: 700;
    flex-shrink: 0;
  }

  .rank-badge--gold {
    background: rgb(245 158 11);
    color: white;
  }

  .rank-badge--silver {
    background: rgb(148 163 184);
    color: white;
  }

  .rank-badge--bronze {
    background: rgb(234 88 12);
    color: white;
  }

  .rank-badge--default {
    background: rgb(226 232 240);
    color: rgb(51 65 85);
  }

  :global(.dark) .rank-badge--default {
    background: rgb(63 63 70);
    color: rgb(228 228 231);
  }
</style>
