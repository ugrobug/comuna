<script lang="ts">
  import { onMount } from 'svelte'
  import { Button } from 'mono-svelte'
  import { buildComunsCatalogUrl, type BackendComun } from '$lib/api/backend'
  import ComunCatalogCard from '$lib/components/comuns/ComunCatalogCard.svelte'
  import { cachedJson } from '$lib/api/publicCache'
  import { subscribeToComunBySlug } from '$lib/settings'

  export let selectedSlugs: string[] = []
  export let recommendedSlugs: string[] = []
  export let limit = 6
  export let title = 'Рекомендуемые сообщества'
  export let description = 'Подпишитесь на несколько сообществ, чтобы собрать свою персональную ленту.'

  let sourceComuns: BackendComun[] = []
  let recommendedComuns: BackendComun[] = []
  let loading = false
  let loaded = false
  let error = ''

  const normalizeSlug = (value: string | null | undefined) =>
    String(value ?? '').trim().toLowerCase()

  const loadRecommendedComuns = async () => {
    if (loading || loaded) return
    loading = true
    error = ''
    try {
      const normalizedRecommendedSlugs = recommendedSlugs.map(normalizeSlug).filter(Boolean)
      const payload = await cachedJson<{ comuns?: BackendComun[] }>(
        normalizedRecommendedSlugs.length
          ? `public:recommended-comuns:${normalizedRecommendedSlugs.join(',')}`
          : 'public:comuns-catalog:recommendations:50',
        buildComunsCatalogUrl(
          normalizedRecommendedSlugs.length
            ? { limit: normalizedRecommendedSlugs.length, slugs: recommendedSlugs }
            : { limit: 50 }
        ),
        { ttlMs: 21_600_000 }
      )
      sourceComuns = payload.comuns ?? []
    } catch (loadError) {
      error = loadError instanceof Error ? loadError.message : 'Ошибка загрузки рекомендаций'
    } finally {
      loaded = true
      loading = false
    }
  }

  const subscribeToComun = (comun: BackendComun) => {
    const slug = normalizeSlug(comun.slug)
    if (!slug) return
    subscribeToComunBySlug(comun.slug)
  }

  onMount(() => {
    void loadRecommendedComuns()
  })

  $: selectedSlugSet = new Set(selectedSlugs.map(normalizeSlug).filter(Boolean))
  $: recommendedComuns = sourceComuns
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
      <div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {#each recommendedComuns as comun}
          <ComunCatalogCard
            {comun}
            subscribed={selectedSlugSet.has(normalizeSlug(comun.slug))}
            showSubscribeText
            on:toggle={() => subscribeToComun(comun)}
          />
        {/each}
      </div>
    {:else}
      <div class="text-sm text-slate-500 dark:text-zinc-400">
        Рекомендации пока не загрузились.
      </div>
    {/if}
    <Button href="/comuns" color="ghost" class="w-full justify-center">
      Смотреть все сообщества
    </Button>
  </div>
</div>
