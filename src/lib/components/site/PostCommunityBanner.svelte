<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { feedSettingsHydrated, userSettings } from '$lib/settings'
  import { siteToken } from '$lib/siteAuth'
  import { locale, t } from '$lib/translations'
  import type { BackendComun } from '$lib/api/backend'
  import { ArrowRight, Check, Icon, UserGroup } from 'svelte-hero-icons'

  export let comun: BackendComun

  let countDelta = 0
  let lastSlug = ''

  $: slug = String(comun?.slug ?? '').trim()
  $: if (slug !== lastSlug) {
    lastSlug = slug
    countDelta = 0
  }
  $: subscribedInSettings = ($userSettings.myFeedComuns ?? [])
    .some((value) => String(value).trim() === slug)
  $: isSubscribed = Boolean(
    subscribedInSettings || (!$feedSettingsHydrated && comun?.is_subscribed)
  )
  $: subscribersCount = Math.max(
    0,
    Number(comun?.subscribers_count ?? 0) + countDelta
  )
  $: communityPath = `/comuns/${encodeURIComponent(slug)}`
  $: communityName = comun?.name || $t('routes.communityPage.community')

  const formatCount = (value: number) => {
    try {
      return new Intl.NumberFormat($locale || 'ru').format(value)
    } catch {
      return String(value)
    }
  }

  const translate = (key: string, values?: Record<string, string | number>) =>
    ($t as (translationKey: string, payload?: Record<string, unknown>) => string)(key, values)

  const toggleSubscription = () => {
    if (!slug) return
    if (!$siteToken) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      void goto(`/account?next=${next}`)
      return
    }

    const nextComuns = new Set(
      ($userSettings.myFeedComuns ?? []).map((value) => String(value).trim()).filter(Boolean)
    )
    const nextCategoryMap = { ...($userSettings.myFeedComunCategories ?? {}) }
    if (isSubscribed) {
      nextComuns.delete(slug)
      delete nextCategoryMap[slug]
      countDelta -= 1
    } else {
      nextComuns.add(slug)
      countDelta += 1
    }
    $userSettings = {
      ...$userSettings,
      myFeedComuns: Array.from(nextComuns),
      myFeedComunCategories: nextCategoryMap,
    }
  }
</script>

{#if slug}
  <aside
    class="community-banner overflow-hidden rounded-lg border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-900"
    aria-label={$t('routes.communityPage.community')}
  >
    <div class="flex flex-col gap-5 p-4 sm:flex-row sm:items-center sm:p-5">
      <a
        href={communityPath}
        class="flex min-w-0 flex-1 items-start gap-4 rounded-md focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-zinc-900"
        aria-label={translate('site.communitiesPage.card.open', { name: communityName })}
      >
        <div
          class="grid h-14 w-14 shrink-0 place-items-center overflow-hidden rounded-full border border-slate-200 bg-slate-100 text-slate-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
        >
          {#if comun.logo_url}
            <img
              src={comun.logo_url}
              alt={communityName}
              class="h-full w-full object-cover"
              loading="lazy"
            />
          {:else}
            <Icon src={UserGroup} size="26" />
          {/if}
        </div>

        <div class="min-w-0 flex-1">
          <div class="text-xs font-medium text-blue-700 dark:text-blue-300">
            {$t('routes.communityPage.community')}
          </div>
          <div class="mt-0.5 flex items-center gap-1.5 text-base font-semibold text-slate-950 dark:text-zinc-50">
            <span class="truncate">{communityName}</span>
            <Icon src={ArrowRight} size="15" class="shrink-0 text-slate-400 dark:text-zinc-500" />
          </div>
          {#if comun.product_description}
            <p class="mt-1 line-clamp-2 text-sm leading-5 text-slate-600 dark:text-zinc-300">
              {comun.product_description}
            </p>
          {/if}
          <div class="mt-2 text-xs text-slate-500 dark:text-zinc-400">
            {translate('routes.communityPage.subscribers', { count: formatCount(subscribersCount) })}
            {#if Number(comun.authors_count ?? 0) > 0}
              <span aria-hidden="true"> · </span>
              {translate('routes.communityPage.authors', { count: formatCount(Number(comun.authors_count)) })}
            {/if}
          </div>
        </div>
      </a>

      <button
        type="button"
        class="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-md border px-4 py-2 text-sm font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-zinc-900 {isSubscribed
          ? 'border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700'
          : 'border-blue-600 bg-blue-600 text-white hover:border-blue-700 hover:bg-blue-700'}"
        on:click={toggleSubscription}
      >
        {#if isSubscribed}
          <Icon src={Check} size="16" />
        {/if}
        {isSubscribed
          ? $t('routes.communityPage.subscribed')
          : $t('routes.communityPage.subscribe')}
      </button>
    </div>
  </aside>
{/if}
