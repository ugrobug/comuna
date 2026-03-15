<script lang="ts">
  import { env } from '$env/dynamic/public'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { Icon, Trophy } from 'svelte-hero-icons'
  import type { BackendTopAuthor, BackendTopAuthorPeriod } from '$lib/api/backend'

  export let data: {
    period: BackendTopAuthorPeriod
    authors: BackendTopAuthor[]
    totalAuthors: number
  }

  const authorRatingHref = '/authors/rating'

  const periodOptions: Array<{ value: BackendTopAuthorPeriod; label: string }> = [
    { value: 'week', label: 'За неделю' },
    { value: 'month', label: 'За месяц' },
    { value: 'all', label: 'За все время' },
  ]

  const periodTitleMap: Record<BackendTopAuthorPeriod, string> = {
    week: 'за неделю',
    month: 'за месяц',
    all: 'за все время',
  }

  const ratingLabelMap: Record<BackendTopAuthorPeriod, string> = {
    week: 'Рейтинг за 7 дней',
    month: 'Рейтинг за 30 дней',
    all: 'Рейтинг за все время',
  }

  const heroRatingLabelMap: Record<BackendTopAuthorPeriod, string> = {
    week: 'Рейтинг автора',
    month: 'Рейтинг автора',
    all: 'Рейтинг автора',
  }

  const formatNumber = (value: number | undefined) => {
    if (!value && value !== 0) return '0'
    return value.toLocaleString('ru-RU')
  }

  const buildPeriodHref = (period: BackendTopAuthorPeriod) => {
    const params = new URLSearchParams()
    if (period !== 'month') {
      params.set('period', period)
    }
    const query = params.toString()
    return query ? `${authorRatingHref}?${query}` : authorRatingHref
  }

  const rankBadgeClass = (index: number) => {
    if (index === 0) return 'rank-badge rank-badge--gold'
    if (index === 1) return 'rank-badge rank-badge--silver'
    return 'rank-badge rank-badge--bronze'
  }

  const heroCardClass = (index: number) => {
    if (index === 0) return 'hero-card hero-card--gold'
    if (index === 1) return 'hero-card hero-card--silver'
    return 'hero-card hero-card--bronze'
  }

  $: pageTitle = `Рейтинг авторов ${periodTitleMap[data.period]} - ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  $: pageDescription = `Полный рейтинг авторов сайта ${periodTitleMap[data.period]}.`
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
          <Icon src={Trophy} size="14" class="text-amber-500" />
          Рейтинг авторов
        </div>
        <div class="text-3xl font-semibold tracking-tight text-slate-950 dark:text-zinc-50 sm:text-4xl">
          Лучшие авторы сайта {periodTitleMap[data.period]}
        </div>
      </div>

      <div class="flex flex-wrap gap-2">
        {#each periodOptions as option}
          <a
            href={buildPeriodHref(option.value)}
            class:period-link--active={data.period === option.value}
            class="period-link"
          >
            {option.label}
          </a>
        {/each}
      </div>
    </div>
  </section>

  {#if data.authors.length}
    <section class="grid gap-4 lg:grid-cols-3">
      {#each topThree as author, index}
        <a href={`/${author.username}`} class={heroCardClass(index)}>
          <div class="flex items-start">
            <div class={rankBadgeClass(index)}>
              {index + 1}
            </div>
          </div>

          <div class="mt-5 flex items-start gap-4">
            <Avatar
              url={author.avatar_url || undefined}
              alt={author.title || author.username}
              width={64}
              class_="h-8 w-8 rounded-full ring-4 ring-white/70 dark:ring-zinc-950/70"
            />
            <div class="min-w-0">
              <div class="hero-card__title">
                {author.title || author.username}
              </div>
              <div class="mt-1 truncate text-sm text-slate-500 dark:text-zinc-400">
                @{author.username}
              </div>
            </div>
          </div>

          <div class="mt-6 text-sm">
            <div class="stat-card">
              <div class="stat-card__label">{heroRatingLabelMap[data.period]}</div>
              <div class="mt-3 flex items-center gap-2 text-slate-900 dark:text-zinc-50">
                <Icon src={Trophy} size="18" class="text-amber-500" />
                <div class="stat-card__value stat-card__value--inline">
                  {formatNumber(author.rating ?? author.score)}
                </div>
              </div>
            </div>
          </div>
        </a>
      {/each}
    </section>

    <section class="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      <div class="flex items-center justify-between gap-4 border-b border-slate-200 px-5 py-4 dark:border-zinc-800 sm:px-6">
        <div>
          <div class="text-lg font-semibold text-slate-950 dark:text-zinc-50">
            Весь рейтинг
          </div>
          <div class="text-sm text-slate-500 dark:text-zinc-400">
            Всего авторов: {formatNumber(data.totalAuthors || data.authors.length)}
          </div>
        </div>
        <div class="hidden text-sm text-slate-500 dark:text-zinc-400 sm:block">
          {ratingLabelMap[data.period]}
        </div>
      </div>

      <div class="flex flex-col">
        {#each remainingAuthors as author, offset}
          {@const rank = offset + 4}
          <a href={`/${author.username}`} class="rating-row">
            <div class="flex items-center gap-4">
              <div class="row-rank">
                {rank}
              </div>
              <Avatar
                url={author.avatar_url || undefined}
                alt={author.title || author.username}
                width={44}
                class_="h-11 w-11 rounded-full"
              />
              <div class="min-w-0 flex-1">
                <div class="truncate text-base font-semibold text-slate-900 dark:text-zinc-100">
                  {author.title || author.username}
                </div>
                <div class="truncate text-sm text-slate-500 dark:text-zinc-400">
                  @{author.username}
                </div>
              </div>
            </div>

            <div class="flex items-center gap-6 text-right">
              <div class="min-w-[88px]">
                <div class="text-xs uppercase tracking-wide text-slate-400 dark:text-zinc-500">
                  Рейтинг
                </div>
                <div class="text-base font-semibold text-slate-900 dark:text-zinc-100">
                  {formatNumber(author.rating ?? author.score)}
                </div>
              </div>
              <div class="min-w-[72px]">
                <div class="text-xs uppercase tracking-wide text-slate-400 dark:text-zinc-500">
                  Посты
                </div>
                <div class="text-base font-semibold text-slate-900 dark:text-zinc-100">
                  {formatNumber(author.posts_count)}
                </div>
              </div>
            </div>
          </a>
        {/each}
      </div>
    </section>
  {:else}
    <section class="rounded-[2rem] border border-dashed border-slate-300 bg-white px-6 py-10 text-center text-slate-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
      Пока нет авторов с публикациями за выбранный период.
    </section>
  {/if}
</div>

<style>
  .period-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 9999px;
    padding: 0.625rem 1rem;
    font-size: 0.9375rem;
    font-weight: 500;
    color: rgb(71 85 105);
    background: rgb(241 245 249);
    transition:
      background-color 0.15s ease,
      color 0.15s ease,
      transform 0.15s ease;
  }

  .period-link:hover {
    background: rgb(226 232 240);
    transform: translateY(-1px);
  }

  .period-link--active {
    color: white;
    background: rgb(15 23 42);
  }

  :global(.dark) .period-link {
    color: rgb(212 212 216);
    background: rgb(39 39 42);
  }

  :global(.dark) .period-link:hover {
    background: rgb(63 63 70);
  }

  :global(.dark) .period-link--active {
    color: rgb(24 24 27);
    background: rgb(244 244 245);
  }

  .hero-card {
    border-radius: 2rem;
    padding: 1.5rem;
    border: 1px solid rgb(226 232 240);
    background: white;
    box-shadow: 0 1px 2px rgb(15 23 42 / 0.06);
    transition:
      transform 0.15s ease,
      box-shadow 0.15s ease;
  }

  .hero-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 16px 32px rgb(15 23 42 / 0.08);
  }

  .hero-card--gold {
    background: linear-gradient(180deg, rgb(255 251 235), white 55%);
  }

  .hero-card--silver {
    background: linear-gradient(180deg, rgb(248 250 252), white 55%);
  }

  .hero-card--bronze {
    background: linear-gradient(180deg, rgb(255 247 237), white 55%);
  }

  :global(.dark) .hero-card {
    border-color: rgb(39 39 42);
    background: rgb(24 24 27);
    box-shadow: none;
  }

  :global(.dark) .hero-card--gold {
    background: linear-gradient(180deg, rgb(69 26 3), rgb(24 24 27) 58%);
  }

  :global(.dark) .hero-card--silver {
    background: linear-gradient(180deg, rgb(39 39 42), rgb(24 24 27) 58%);
  }

  :global(.dark) .hero-card--bronze {
    background: linear-gradient(180deg, rgb(67 20 7), rgb(24 24 27) 58%);
  }

  .rank-badge {
    width: 3rem;
    height: 3rem;
    border-radius: 9999px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 1.125rem;
    font-weight: 700;
    color: white;
  }

  .rank-badge--gold {
    background: linear-gradient(135deg, rgb(245 158 11), rgb(217 119 6));
  }

  .rank-badge--silver {
    background: linear-gradient(135deg, rgb(148 163 184), rgb(100 116 139));
  }

  .rank-badge--bronze {
    background: linear-gradient(135deg, rgb(249 115 22), rgb(194 65 12));
  }

  .stat-card {
    border-radius: 1.25rem;
    background: rgb(255 255 255 / 0.75);
    padding: 0.875rem 1rem;
  }

  :global(.dark) .stat-card {
    background: rgb(24 24 27 / 0.7);
  }

  .stat-card__label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgb(100 116 139);
  }

  .stat-card__value {
    margin-top: 0.375rem;
    font-size: 1.25rem;
    font-weight: 700;
    color: rgb(15 23 42);
  }

  .stat-card__value--inline {
    margin-top: 0;
  }

  :global(.dark) .stat-card__label {
    color: rgb(161 161 170);
  }

  :global(.dark) .stat-card__value {
    color: rgb(244 244 245);
  }

  .rating-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    padding: 1rem 1.25rem;
    border-top: 1px solid rgb(241 245 249);
    transition: background-color 0.15s ease;
  }

  .rating-row:hover {
    background: rgb(248 250 252);
  }

  :global(.dark) .rating-row {
    border-top-color: rgb(39 39 42);
  }

  :global(.dark) .rating-row:hover {
    background: rgb(39 39 42 / 0.65);
  }

  .row-rank {
    width: 2.25rem;
    text-align: center;
    font-size: 1rem;
    font-weight: 700;
    color: rgb(100 116 139);
    flex-shrink: 0;
  }

  .hero-card__title {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    font-size: 1.25rem;
    font-weight: 600;
    line-height: 1.2;
    color: rgb(15 23 42);
    overflow-wrap: anywhere;
  }

  :global(.dark) .hero-card__title {
    color: rgb(244 244 245);
  }

  @media (max-width: 640px) {
    .rating-row {
      flex-direction: column;
      align-items: flex-start;
    }

    .rating-row > :last-child {
      width: 100%;
      justify-content: space-between;
    }
  }
</style>
