<script lang="ts">
  import { env } from '$env/dynamic/public'
  import TopAuthorsPeriodTabs from '$lib/components/ratings/TopAuthorsPeriodTabs.svelte'
  import TopAuthorsPodium from '$lib/components/ratings/TopAuthorsPodium.svelte'
  import TopAuthorsTable from '$lib/components/ratings/TopAuthorsTable.svelte'
  import type { BackendTopAuthor, BackendTopAuthorPeriod } from '$lib/api/backend'
  import { topAuthorPeriodTitleMap } from '$lib/ratings/topAuthors'

  export let data: {
    period: BackendTopAuthorPeriod
    authors: BackendTopAuthor[]
    totalAuthors: number
  }

  $: pageTitle = `Рейтинг авторов ${topAuthorPeriodTitleMap[data.period]} - ${env.PUBLIC_SITE_TITLE || 'Тамбур'}`
  $: pageDescription = `Полный рейтинг авторов сайта ${topAuthorPeriodTitleMap[data.period]}.`
  $: topThree = data.authors.slice(0, 3)
  $: remainingAuthors = data.authors.slice(3)
</script>

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="description" content={pageDescription} />
  <meta property="og:title" content={pageTitle} />
  <meta property="og:description" content={pageDescription} />
  <meta property="og:type" content="website" />
</svelte:head>

<div class="mx-auto flex w-full max-w-5xl flex-col gap-6">
  <section class="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900 sm:p-8">
    <div class="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
      <div class="flex max-w-2xl flex-col gap-3">
        <div class="inline-flex w-fit items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-600 dark:bg-zinc-800 dark:text-zinc-300">
          Рейтинг авторов
        </div>
        <div class="text-3xl font-semibold tracking-tight text-slate-950 dark:text-zinc-50 sm:text-4xl">
          Лучшие авторы сайта {topAuthorPeriodTitleMap[data.period]}
        </div>
      </div>

      <TopAuthorsPeriodTabs period={data.period} />
    </div>
  </section>

  {#if data.authors.length}
    <TopAuthorsPodium authors={topThree} period={data.period} />

    <TopAuthorsTable
      authors={remainingAuthors}
      period={data.period}
      totalAuthors={data.totalAuthors || data.authors.length}
    />
  {:else}
    <section class="rounded-[2rem] border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-slate-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
      Пока нет авторов с публикациями за выбранный период.
    </section>
  {/if}
</div>
