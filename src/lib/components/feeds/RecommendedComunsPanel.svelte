<script lang="ts">
  import { onMount } from 'svelte'
  import { Button } from 'mono-svelte'
  import { buildComunsCatalogUrl, type BackendComun } from '$lib/api/backend'
  import { cachedJson } from '$lib/api/publicCache'
  import { subscribeToComunBySlug } from '$lib/settings'
  import { siteToken } from '$lib/siteAuth'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { t } from '$lib/translations'

  export let selectedSlugs: string[] = []
  export let recommendedSlugs: string[] = []
  export let limit = 6
  export let title = ''
  export let description = ''

  let sourceComuns: BackendComun[] = []
  let recommendedComuns: BackendComun[] = []
  let loading = false
  let loaded = false
  let error = ''
  let loginModalOpen = false

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
      error = loadError instanceof Error ? loadError.message : $t('site.sidebar.recommended.loadError')
    } finally {
      loaded = true
      loading = false
    }
  }

  const subscribeToComun = (comun: BackendComun) => {
    const slug = normalizeSlug(comun.slug)
    if (!slug) return
    if (!$siteToken) {
      loginModalOpen = true
      return
    }
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
        {title || $t('site.sidebar.recommended.title')}
      </div>
      {#if description || $t('site.sidebar.recommended.description')}
        <div class="text-sm text-slate-500 dark:text-zinc-400">
          {description || $t('site.sidebar.recommended.description')}
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
          <article class="recommended-comun-card rounded-2xl border border-slate-200 bg-white p-4 transition hover:border-blue-300 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-900/80 dark:hover:border-blue-700">
            <a href={`/comuns/${comun.slug}`} class="flex min-w-0 items-start gap-3">
              <span
                class="h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-slate-200 bg-slate-100 dark:border-zinc-800 dark:bg-zinc-800"
                aria-hidden="true"
              >
                {#if comun.logo_url}
                  <img src={comun.logo_url} alt="" class="h-full w-full object-cover" />
                {:else}
                  <span
                    class="comun-logo-fallback grid h-full w-full place-items-center text-xl font-bold"
                    style={comunPlaceholderStyle(comun.name)}
                  >
                    {comunInitial(comun.name)}
                  </span>
                {/if}
              </span>
              <span class="min-w-0 flex-1">
                <span class="line-clamp-2 text-base font-semibold leading-snug text-slate-900 dark:text-zinc-100">
                  {comun.name}
                </span>
                {#if comun.product_description}
                  <span class="mt-1 line-clamp-3 text-sm leading-snug text-slate-600 dark:text-zinc-400">
                    {comun.product_description}
                  </span>
                {/if}
              </span>
            </a>
            <button
              type="button"
              class={`mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-full border px-4 text-sm font-semibold transition ${
                selectedSlugSet.has(normalizeSlug(comun.slug))
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300'
                  : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-900/70 dark:bg-blue-950/40 dark:text-blue-300'
              }`}
              aria-label={selectedSlugSet.has(normalizeSlug(comun.slug)) ? $t('site.sidebar.recommended.unsubscribeFrom', { name: comun.name }) : $t('site.sidebar.recommended.subscribeTo', { name: comun.name })}
              aria-pressed={selectedSlugSet.has(normalizeSlug(comun.slug))}
              on:click={() => subscribeToComun(comun)}
            >
              {#if selectedSlugSet.has(normalizeSlug(comun.slug))}
                <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M4.5 10.4 8.1 14 15.7 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
                <span>{$t('site.sidebar.recommended.subscribed')}</span>
              {:else}
                <svg class="h-4 w-4 shrink-0" viewBox="0 0 20 20" fill="none" aria-hidden="true">
                  <path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" />
                </svg>
                <span>{$t('site.sidebar.recommended.subscribe')}</span>
              {/if}
            </button>
          </article>
        {/each}
      </div>
    {:else}
      <div class="text-sm text-slate-500 dark:text-zinc-400">
        {$t('site.sidebar.recommended.empty')}
      </div>
    {/if}
    <Button href="/comuns" color="ghost" class="w-full justify-center">
      {$t('site.sidebar.recommended.viewAll')}
    </Button>
  </div>
</div>

<LoginModal bind:open={loginModalOpen} initialMode="login" />

<style>
  .recommended-comun-card {
    min-height: 196px;
  }

  .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 60% 92%);
    color: hsl(var(--comun-h, 220) 70% 34%);
  }

  :global(.dark) .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 35% 20%);
    color: hsl(var(--comun-h, 220) 78% 72%);
  }
</style>
