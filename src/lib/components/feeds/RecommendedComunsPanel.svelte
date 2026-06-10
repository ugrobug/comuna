<script lang="ts">
  import { onMount } from 'svelte'
  import { Button } from 'mono-svelte'
  import { buildTopComunsUrl, type BackendTopComun } from '$lib/api/backend'
  import { cachedJson } from '$lib/api/publicCache'
  import { subscribeToComunBySlug } from '$lib/settings'

  export let selectedSlugs: string[] = []
  export let limit = 6
  export let title = 'Рекомендуемые сообщества'
  export let description = 'Подпишитесь на несколько сообществ, чтобы собрать свою персональную ленту.'

  let topComuns: BackendTopComun[] = []
  let recommendedComuns: BackendTopComun[] = []
  let loading = false
  let loaded = false
  let error = ''

  const normalizeSlug = (value: string | null | undefined) =>
    String(value ?? '').trim().toLowerCase()

  const hashString = (value?: string | null) => {
    const source = (value ?? '').trim() || 'comuna'
    let hash = 0
    for (let i = 0; i < source.length; i += 1) {
      hash = (hash * 31 + source.charCodeAt(i)) % 360
    }
    return Math.abs(hash)
  }

  const comunPlaceholderStyle = (name?: string | null) => `--comun-h:${hashString(name)}`

  const comunInitial = (name?: string | null) =>
    (name ?? '').trim().slice(0, 1).toUpperCase() || 'C'

  const formatNumber = (value?: number | null) => {
    const numeric = Math.max(Number(value ?? 0) || 0, 0)
    return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(2).replace(/\.?0+$/, '')
  }

  const loadRecommendedComuns = async () => {
    if (loading || loaded) return
    loading = true
    error = ''
    try {
      const payload = await cachedJson<{ comuns?: BackendTopComun[] }>(
        'public:top-comuns:50',
        buildTopComunsUrl({ limit: 50 }),
        { ttlMs: 21_600_000 }
      )
      topComuns = payload.comuns ?? []
    } catch (loadError) {
      error = loadError instanceof Error ? loadError.message : 'Ошибка загрузки рекомендаций'
    } finally {
      loaded = true
      loading = false
    }
  }

  const subscribeToComun = (comun: BackendTopComun) => {
    const slug = normalizeSlug(comun.slug)
    if (!slug) return
    subscribeToComunBySlug(comun.slug)
  }

  onMount(() => {
    void loadRecommendedComuns()
  })

  $: selectedSlugSet = new Set(selectedSlugs.map(normalizeSlug).filter(Boolean))
  $: recommendedComuns = topComuns
    .filter((comun) => !selectedSlugSet.has(normalizeSlug(comun.slug)))
    .slice(0, limit)
</script>

<div class="rounded-2xl border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
  <div class="flex flex-col gap-4">
    <div class="flex flex-col gap-2">
      <div class="text-base font-medium text-slate-800 dark:text-zinc-100">
        {title}
      </div>
      {#if description}
        <div class="text-sm text-slate-500 dark:text-zinc-400">
          {description}
        </div>
      {/if}
    </div>

    {#if loading}
      <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {#each Array(limit) as _}
          <div class="h-28 animate-pulse rounded-xl border border-slate-200 bg-slate-50 dark:border-zinc-800 dark:bg-zinc-800/60"></div>
        {/each}
      </div>
    {:else if error}
      <div class="text-sm text-rose-600 dark:text-rose-300">{error}</div>
    {:else if recommendedComuns.length}
      <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {#each recommendedComuns as comun}
          <div class="flex min-w-0 flex-col gap-3 rounded-xl border border-slate-200 p-3 dark:border-zinc-800">
            <a
              href={`/comuns/${encodeURIComponent(comun.slug)}`}
              class="flex min-w-0 items-start gap-3"
            >
              <div class="h-10 w-10 shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-slate-100 dark:border-zinc-800 dark:bg-zinc-800">
                {#if comun.logo_url || comun.avatar_url}
                  <img
                    src={comun.logo_url || comun.avatar_url}
                    alt={comun.name}
                    class="h-full w-full object-cover"
                  />
                {:else}
                  <div
                    class="comun-logo-fallback grid h-full w-full place-items-center text-base font-bold"
                    style={comunPlaceholderStyle(comun.name)}
                  >
                    {comunInitial(comun.name)}
                  </div>
                {/if}
              </div>
              <div class="min-w-0">
                <div class="truncate text-sm font-medium text-slate-900 hover:text-blue-600 dark:text-zinc-100 dark:hover:text-blue-400">
                  {comun.name}
                </div>
                <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                  Рейтинг {formatNumber(comun.rating ?? comun.score)} · {formatNumber(comun.posts_count)} постов
                </div>
              </div>
            </a>
            <Button color="ghost" on:click={() => subscribeToComun(comun)}>
              Подписаться
            </Button>
          </div>
        {/each}
      </div>
    {:else}
      <a href="/comuns" class="inline-flex text-sm text-blue-600 hover:underline dark:text-blue-400">
        Смотреть все сообщества
      </a>
    {/if}
  </div>
</div>

<style>
  .comun-logo-fallback {
    background:
      radial-gradient(circle at 30% 20%, hsla(var(--comun-h), 82%, 72%, 0.7), transparent 45%),
      linear-gradient(135deg, hsl(var(--comun-h), 65%, 53%), hsl(calc(var(--comun-h) + 42), 70%, 46%));
    color: white;
  }
</style>
