<script lang="ts">
  import { onMount } from 'svelte'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { Button } from 'mono-svelte'
  import { Trophy, ChatBubbleLeftRight, Icon } from 'svelte-hero-icons'
  import { buildTopComunsUrl, type BackendTopComun } from '$lib/api/backend'
  import { cachedJson } from '$lib/api/publicCache'
  import { formatTopAuthorNumber } from '$lib/ratings/topAuthors'

  let comuns: BackendTopComun[] = []
  let loading = true
  let error: string | null = null

  async function fetchTopComuns() {
    try {
      const data = await cachedJson<{ comuns?: BackendTopComun[] }>(
        'public:top-comuns:5',
        buildTopComunsUrl({ limit: 5 }),
        { ttlMs: 21_600_000 }
      )
      comuns = data.comuns ?? []
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Неизвестная ошибка'
    } finally {
      loading = false
    }
  }

  onMount(fetchTopComuns)
</script>

<div class="flex flex-col gap-2 rounded-xl bg-white p-4 dark:bg-zinc-900">
  <a
    href="/comuns"
    class="mb-2 text-base font-normal text-slate-900 transition-colors hover:text-blue-600 dark:text-zinc-200 dark:hover:text-blue-400"
  >
    Топ сообществ
  </a>

  {#if loading}
    <div class="animate-pulse space-y-3">
      {#each Array(5) as _}
        <div class="h-4 rounded bg-slate-100 dark:bg-zinc-800"></div>
      {/each}
    </div>
  {:else if error}
    <div class="text-sm text-red-500">
      {error}
    </div>
  {:else if comuns.length === 0}
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      Нет данных по сообществам
    </div>
  {:else}
    <div class="flex flex-col divide-y divide-slate-200 dark:divide-zinc-800">
      {#each comuns as comun, index}
        <a
          href={`/comuns/${comun.slug}`}
          class="comun-row block group py-3 first:pt-1 last:pb-1"
        >
          <div class="flex flex-col gap-2">
            <div class="flex min-w-0 items-center gap-2">
              <div class="rank-badge rank-badge--default">
                {index + 1}
              </div>
              <Avatar
                url={comun.logo_url || comun.avatar_url || undefined}
                alt={comun.name}
                width={32}
                class_="h-8 w-8 rounded-full"
              />
              <span class="min-w-0 flex-1 truncate text-sm font-medium text-slate-900 dark:text-zinc-200">
                {comun.name}
              </span>
            </div>
            <div class="flex items-center gap-2 text-xs font-medium text-slate-600 dark:text-zinc-400">
              <span class="flex items-center gap-1">
                <Icon src={Trophy} size="14" class="text-amber-500" />
                {formatTopAuthorNumber(comun.rating ?? comun.score)}
              </span>
              <span class="flex items-center gap-1">
                {formatTopAuthorNumber(comun.posts_count)} постов
              </span>
              <span class="flex items-center gap-1">
                <Icon src={ChatBubbleLeftRight} size="14" class="text-sky-500" />
                {formatTopAuthorNumber(comun.comments_count)}
              </span>
            </div>
          </div>
        </a>
      {/each}
    </div>
    <Button
      href="/comuns"
      color="ghost"
      rounding="xl"
      class="mt-3 w-full justify-center !text-sm"
    >
      Все сообщества
    </Button>
  {/if}
</div>

<style>
  .comun-row {
    border-radius: 1rem;
    margin: 0 -0.25rem;
    padding-left: 0.25rem;
    padding-right: 0.25rem;
    transition: background-color 0.15s ease;
  }

  .comun-row:hover {
    background: rgb(248 250 252);
  }

  :global(.dark) .comun-row:hover {
    background: rgb(39 39 42 / 0.8);
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

  .rank-badge--default {
    background: rgb(226 232 240);
    color: rgb(51 65 85);
  }

  :global(.dark) .rank-badge--default {
    background: rgb(63 63 70);
    color: rgb(228 228 231);
  }
</style>
