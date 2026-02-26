<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { Button, toast } from 'mono-svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import {
    buildBackendPostPath,
    type BackendComun,
    type BackendComunCategory,
    type BackendPost,
  } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import { env } from '$env/dynamic/public'

  export let data

  type CategoryCountRow = {
    category_id?: number | null
    slug?: string | null
    count?: number | null
  }

  type CategoryPreviewRow = {
    category_slug?: string | null
    posts?: BackendPost[]
    total_count?: number | null
    error?: string | null
  }

  type RoadmapStageKey = 'suggestions' | 'backlog' | 'planned' | 'in_progress' | 'released'

  type RoadmapStageDefinition = {
    key: RoadmapStageKey
    label: string
    shortLabel: string
    description: string
    exactSlugs: string[]
    slugKeywords: string[]
    nameKeywords: string[]
  }

  type RoadmapLane = {
    id: string
    key: RoadmapStageKey | 'custom'
    category: BackendComunCategory
    label: string
    shortLabel: string
    description: string
    count: number
    error: string | null
    posts: BackendPost[]
    totalCount: number | null
    isKnownStage: boolean
  }

  const KNOWN_STAGE_DEFINITIONS: RoadmapStageDefinition[] = [
    {
      key: 'suggestions',
      label: 'Идеи от пользователей',
      shortLabel: 'Идеи',
      description: 'Пожелания, гипотезы и feature requests от пользователей.',
      exactSlugs: ['feature-ideas', 'suggestions', 'ideas', 'feature-requests', 'requests'],
      slugKeywords: ['idea', 'suggest', 'request', 'feedback', 'feature'],
      nameKeywords: ['иде', 'предлож', 'запрос', 'фидбек', 'улучш'],
    },
    {
      key: 'backlog',
      label: 'Беклог',
      shortLabel: 'Беклог',
      description: 'Отобранные задачи и идеи, которые команда рассматривает и приоритизирует.',
      exactSlugs: ['backlog'],
      slugKeywords: ['backlog', 'queue'],
      nameKeywords: ['беклог', 'очеред', 'приорит'],
    },
    {
      key: 'planned',
      label: 'Запланировано',
      shortLabel: 'План',
      description: 'То, что команда собирается делать следующим шагом.',
      exactSlugs: ['planned', 'plan', 'next', 'up-next', 'next-up'],
      slugKeywords: ['plan', 'planned', 'next'],
      nameKeywords: ['план', 'заплан', 'следующ', 'далее'],
    },
    {
      key: 'in_progress',
      label: 'В работе',
      shortLabel: 'В работе',
      description: 'Задачи, которые уже взяты в разработку.',
      exactSlugs: ['in-progress', 'in_progress', 'progress', 'doing', 'wip'],
      slugKeywords: ['progress', 'doing', 'wip', 'develop', 'active'],
      nameKeywords: ['в работе', 'разработ', 'делаем', 'делается'],
    },
    {
      key: 'released',
      label: 'Сделано / релизы',
      shortLabel: 'Готово',
      description: 'Изменения, которые уже доставлены пользователям.',
      exactSlugs: ['done', 'completed', 'shipped', 'released', 'changelog'],
      slugKeywords: ['done', 'complete', 'ship', 'release', 'changelog', 'live'],
      nameKeywords: ['готов', 'сделан', 'релиз', 'выпущ'],
    },
  ]

  const ROADMAP_PREVIEW_LIMIT = Number(data?.previewLimit ?? 12) || 12

  let comun: BackendComun | null = data?.comun ?? null
  let categoryCounts: CategoryCountRow[] = Array.isArray(data?.categoryCounts) ? data.categoryCounts : []
  let categoryPreviews: CategoryPreviewRow[] = Array.isArray(data?.categoryPreviews)
    ? data.categoryPreviews
    : []
  let totalCount = Math.max(Number(data?.totalCount ?? 0) || 0, 0)
  let uncategorizedCount = Math.max(Number(data?.uncategorizedCount ?? 0) || 0, 0)

  const normalizeToken = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/[_\s]+/g, '-')
      .replace(/-+/g, '-')
      .trim()

  const normalizeText = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim()

  const countFormat = (value?: number | null) =>
    new Intl.NumberFormat('ru-RU').format(Math.max(Number(value ?? 0) || 0, 0))

  const dateFormat = (value?: string | null) => {
    if (!value) return ''
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: 'short',
    }).format(parsed)
  }

  const stripHtml = (value?: string | null) =>
    (value ?? '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()

  const snippet = (post: BackendPost, maxLength = 180) => {
    const text = stripHtml(post.content)
    if (!text) return ''
    if (text.length <= maxLength) return text
    return `${text.slice(0, maxLength - 1).trimEnd()}…`
  }

  const previewScore = (post: BackendPost) =>
    Number(post.likes_count ?? 0) * 3 +
    Number(post.comments_count ?? 0) * 5 +
    Number(post.views_count ?? 0) * 0.02

  const sortPreviewPosts = (posts: BackendPost[]) =>
    [...posts]
      .sort((a, b) => {
        const scoreDiff = previewScore(b) - previewScore(a)
        if (scoreDiff !== 0) return scoreDiff
        return String(b.created_at ?? '').localeCompare(String(a.created_at ?? ''))
      })
      .slice(0, ROADMAP_PREVIEW_LIMIT)

  const scoreCandidate = (
    stage: RoadmapStageDefinition,
    category: BackendComunCategory
  ) => {
    const slug = normalizeToken(category.slug)
    const name = normalizeText(category.name)
    if (!slug && !name) return 0
    if (stage.exactSlugs.includes(slug)) return 100
    let score = 0
    if (stage.key === 'suggestions' && ['suggestions', 'feature-ideas'].includes(slug)) {
      score = Math.max(score, 95)
    }
    if (stage.slugKeywords.some((keyword) => slug.includes(keyword))) score = Math.max(score, 70)
    if (stage.nameKeywords.some((keyword) => name.includes(keyword))) score = Math.max(score, 60)
    return score
  }

  const stageStyleVars = (key: RoadmapLane['key']) => {
    switch (key) {
      case 'suggestions':
        return '--lane-h: 201; --lane-s: 88%; --lane-l: 47%;'
      case 'backlog':
        return '--lane-h: 262; --lane-s: 72%; --lane-l: 52%;'
      case 'planned':
        return '--lane-h: 34; --lane-s: 88%; --lane-l: 50%;'
      case 'in_progress':
        return '--lane-h: 153; --lane-s: 77%; --lane-l: 40%;'
      case 'released':
        return '--lane-h: 340; --lane-s: 78%; --lane-l: 52%;'
      default:
        return '--lane-h: 220; --lane-s: 72%; --lane-l: 52%;'
    }
  }

  const laneStateLabel = (lane: RoadmapLane) => {
    switch (lane.key) {
      case 'suggestions':
        return 'Собираем'
      case 'backlog':
        return 'Приоритет'
      case 'planned':
        return 'Дальше'
      case 'in_progress':
        return 'В работе'
      case 'released':
        return 'Готово'
      default:
        return 'Этап'
    }
  }

  const openSubmitFlow = () => {
    if (!comun?.slug) return
    if ($siteToken && comun?.can_moderate) {
      goto(`/comuns/${comun.slug}/new-post`)
      return
    }
    if (!$siteToken) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    goto('/create/post')
  }

  const copyRoadmapLink = async () => {
    if (!browser) return
    try {
      await navigator.clipboard.writeText(shareUrl)
      toast({ content: 'Ссылка на публичную дорожную карту скопирована', type: 'success' })
    } catch {
      toast({ content: 'Не удалось скопировать ссылку', type: 'error' })
    }
  }

  $: categories = Array.isArray(comun?.categories) ? (comun?.categories ?? []) : []
  $: countByCategoryId = new Map<number, number>(
    categoryCounts
      .map((row) => [Number(row?.category_id ?? 0), Math.max(Number(row?.count ?? 0) || 0, 0)] as const)
      .filter(([id]) => id > 0)
  )
  $: previewBySlug = new Map<string, CategoryPreviewRow>(
    categoryPreviews
      .map((row) => [String(row?.category_slug ?? '').trim(), row] as const)
      .filter(([slug]) => Boolean(slug))
  )

  $: usedCategoryIds = new Set<number>()
  $: knownStageLanes = KNOWN_STAGE_DEFINITIONS.map((stage) => {
    const candidate = categories
      .filter((category) => !usedCategoryIds.has(category.id))
      .map((category) => ({ category, score: scoreCandidate(stage, category) }))
      .filter((item) => item.score > 0)
      .sort((a, b) => {
        if (b.score !== a.score) return b.score - a.score
        return (
          Number(a.category.sort_order ?? 0) - Number(b.category.sort_order ?? 0) ||
          a.category.name.localeCompare(b.category.name, 'ru')
        )
      })[0]
    if (!candidate) return null
    usedCategoryIds.add(candidate.category.id)
    const preview = previewBySlug.get(candidate.category.slug)
    return {
      id: `${stage.key}:${candidate.category.id}`,
      key: stage.key,
      category: candidate.category,
      label: stage.label,
      shortLabel: stage.shortLabel,
      description: stage.description,
      count: Math.max(countByCategoryId.get(candidate.category.id) ?? 0, 0),
      error: (preview?.error as string | null) ?? null,
      posts: sortPreviewPosts((preview?.posts ?? []) as BackendPost[]),
      totalCount: typeof preview?.total_count === 'number' ? Number(preview.total_count) : null,
      isKnownStage: true,
    } satisfies RoadmapLane
  }).filter(Boolean) as RoadmapLane[]

  $: extraLanes = categories
    .filter((category) => !usedCategoryIds.has(category.id))
    .sort(
      (a, b) =>
        Number(a.sort_order ?? 0) - Number(b.sort_order ?? 0) ||
        a.name.localeCompare(b.name, 'ru')
    )
    .map((category) => {
      const preview = previewBySlug.get(category.slug)
      return {
        id: `custom:${category.id}`,
        key: 'custom',
        category,
        label: category.name,
        shortLabel: category.name,
        description:
          category.description?.trim() ||
          'Отдельный этап/срез в вашей публичной дорожной карте.',
        count: Math.max(countByCategoryId.get(category.id) ?? 0, 0),
        error: (preview?.error as string | null) ?? null,
        posts: sortPreviewPosts((preview?.posts ?? []) as BackendPost[]),
        totalCount: typeof preview?.total_count === 'number' ? Number(preview.total_count) : null,
        isKnownStage: false,
      } satisfies RoadmapLane
    })

  $: roadmapLanes = [...knownStageLanes, ...extraLanes]
  $: trackedCount = roadmapLanes.reduce((sum, lane) => sum + Math.max(lane.count, 0), 0)
  $: selectedCategorySlug = String($page.url.searchParams.get('category') || '').trim()
  $: highlightedLane = roadmapLanes.find((lane) => lane.category.slug === selectedCategorySlug) ?? null
  $: comunName = comun?.name || 'Комуна'
  $: pageTitle = `Публичная дорожная карта — ${comunName}`
  $: pageDescription =
    comun?.product_description?.trim() ||
    `Публичная дорожная карта и беклог продукта «${comunName}»: что планируется дальше и что обсуждают пользователи.`
  $: canonicalUrl = new URL(
    $page.url.pathname + ($page.url.search || ''),
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
  $: shareUrl = canonicalUrl

  $: founderPrompt =
    comun?.product_tag?.name
      ? `Попросите пользователей публиковать идеи с тегом #${comun.product_tag.name}, затем переносите лучшие карточки по этапам.`
      : 'Задайте тег продукта в настройках комуны, чтобы новые карточки автоматически попадали в дорожную карту.'
</script>

<div class="mx-auto flex w-full max-w-7xl flex-col gap-6">
  <section class="roadmap-page-shell overflow-hidden rounded-3xl">
    <div class="roadmap-page-glow"></div>
    <div class="roadmap-page-content relative z-10 flex flex-col gap-5 p-4 sm:p-5 lg:p-6">
      <div class="grid gap-4 lg:grid-cols-[1.25fr_minmax(280px,0.75fr)]">
        <div class="roadmap-hero-card rounded-2xl p-4 sm:p-5">
          <div class="mb-3 flex flex-wrap items-center gap-2">
            <span class="hero-badge">Публичная дорожная карта</span>
            <span class="hero-badge hero-badge--muted">Отдельная ссылка для пользователей</span>
            {#if highlightedLane}
              <span class="hero-badge hero-badge--lane" style={stageStyleVars(highlightedLane.key)}>
                Фильтр: {highlightedLane.shortLabel}
              </span>
            {/if}
          </div>

          <div class="space-y-2">
            <Header noMargin>{comunName}</Header>
            <p class="hero-text">
              Здесь основатель может публично показать, что команда планирует делать дальше, а пользователи
              могут перейти в карточки, проголосовать и обсудить изменения.
            </p>
          </div>

          <div class="mt-4 flex flex-wrap gap-2">
            <a href={`/comuns/${comun?.slug ?? ''}`} class="ghost-link">Комуна</a>
            {#if comun?.slug}
              <a href={`/comuns/${comun.slug}?category=backlog`} class="ghost-link">Беклог</a>
            {/if}
            {#if comun?.website_url}
              <a href={comun.website_url} target="_blank" rel="nofollow noopener" class="ghost-link">
                Сайт продукта
              </a>
            {/if}
          </div>

          <div class="mt-4 rounded-2xl border border-slate-200/80 bg-white/70 p-3 dark:border-zinc-800 dark:bg-zinc-900/45">
            <div class="mb-2 text-xs uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">
              Ссылка для отправки пользователям
            </div>
            <div class="flex flex-col gap-2 sm:flex-row sm:items-center">
              <code class="share-url flex-1 rounded-xl px-3 py-2 text-xs sm:text-sm">{shareUrl}</code>
              <Button on:click={copyRoadmapLink}>Скопировать</Button>
            </div>
          </div>
        </div>

        <div class="roadmap-side-card rounded-2xl p-4 sm:p-5">
          <div class="text-xs uppercase tracking-[0.12em] text-slate-500 dark:text-zinc-400">Сводка</div>
          <div class="mt-3 grid grid-cols-2 gap-2">
            <div class="stat-box rounded-xl p-3">
              <div class="stat-label">Всего карточек</div>
              <div class="stat-value">{countFormat(totalCount)}</div>
            </div>
            <div class="stat-box rounded-xl p-3">
              <div class="stat-label">В этапах roadmap</div>
              <div class="stat-value">{countFormat(trackedCount)}</div>
            </div>
            <div class="stat-box rounded-xl p-3">
              <div class="stat-label">Колонок</div>
              <div class="stat-value">{countFormat(roadmapLanes.length)}</div>
            </div>
            <div class="stat-box rounded-xl p-3">
              <div class="stat-label">Без категории</div>
              <div class="stat-value">{countFormat(uncategorizedCount)}</div>
            </div>
          </div>

          <div class="mt-4 rounded-xl border border-slate-200/80 bg-slate-50/70 p-3 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-900/40 dark:text-zinc-300">
            <div class="font-semibold text-slate-900 dark:text-zinc-100">Как привлекать фидбек</div>
            <div class="mt-1">
              {founderPrompt}
            </div>
            <div class="mt-2 flex flex-wrap gap-2">
              <Button size="sm" on:click={openSubmitFlow}>
                {comun?.can_moderate && $siteToken ? 'Добавить карточку' : 'Предложить идею'}
              </Button>
              {#if comun?.slug}
                <a href={`/comuns/${comun.slug}`} class="ghost-link ghost-link--small">
                  Открыть ленту комуны
                </a>
              {/if}
            </div>
          </div>
        </div>
      </div>

      {#if roadmapLanes.length}
        <div class="roadmap-grid">
          {#each roadmapLanes as lane}
            <section
              class="roadmap-lane rounded-2xl p-4"
              style={stageStyleVars(lane.key)}
              data-highlight={selectedCategorySlug === lane.category.slug ? '1' : '0'}
            >
              <div class="mb-3 flex items-start justify-between gap-2">
                <div class="min-w-0">
                  <div class="lane-pill">{laneStateLabel(lane)}</div>
                  <div class="mt-2 text-sm font-semibold text-slate-900 dark:text-zinc-100">
                    {lane.label}
                  </div>
                  <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                    {countFormat(lane.count)} карточек
                    {#if lane.totalCount !== null && lane.totalCount !== lane.count}
                      · загружено {countFormat(lane.posts.length)} из {countFormat(lane.totalCount)}
                    {/if}
                  </div>
                </div>
                <a href={`/comuns/${comun?.slug ?? ''}?category=${encodeURIComponent(lane.category.slug)}`} class="lane-link">
                  Открыть
                </a>
              </div>

              <p class="lane-description">{lane.description}</p>

              {#if lane.error}
                <div class="lane-state lane-state--error">{lane.error}</div>
              {:else if lane.posts.length}
                <div class="mt-3 flex flex-col gap-2">
                  {#each lane.posts as post}
                    {@const postSnippet = snippet(post)}
                    {@const postDate = dateFormat(post.created_at)}
                    <a href={buildBackendPostPath(post)} class="mini-card rounded-xl p-3">
                      <div class="mini-card__title">{post.title || 'Без заголовка'}</div>
                      {#if postSnippet}
                        <div class="mini-card__snippet">{postSnippet}</div>
                      {/if}
                      <div class="mini-card__meta">
                        <span>Голоса {countFormat(post.likes_count ?? 0)}</span>
                        <span>Комментарии {countFormat(post.comments_count ?? 0)}</span>
                        {#if postDate}
                          <span>{postDate}</span>
                        {/if}
                      </div>
                      <div class="mini-card__cta">
                        Открыть карточку и обсуждение
                      </div>
                    </a>
                  {/each}
                </div>
              {:else}
                <div class="lane-state">
                  В этой колонке пока нет карточек.
                </div>
              {/if}
            </section>
          {/each}
        </div>
      {:else}
        <section class="empty-roadmap rounded-2xl p-5">
          <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">
            Публичная дорожная карта пока не настроена
          </div>
          <div class="mt-2 text-sm text-slate-600 dark:text-zinc-400">
            Добавьте в коммуну категории вроде <span class="font-semibold">backlog</span>,
            <span class="font-semibold"> suggestions</span>, <span class="font-semibold">planned</span>,
            <span class="font-semibold"> in-progress</span> и публикуйте карточки по тегу продукта.
          </div>
          <div class="mt-4 flex flex-wrap gap-2">
            {#if comun?.slug}
              <a href={`/comuns/${comun.slug}`} class="ghost-link">Открыть коммуну</a>
              {#if comun?.can_moderate && $siteToken}
                <a href={`/comuns/${comun.slug}/settings`} class="ghost-link">Настройки комуны</a>
              {/if}
            {/if}
            <Button on:click={openSubmitFlow}>
              {comun?.can_moderate && $siteToken ? 'Добавить карточку' : 'Предложить идею'}
            </Button>
          </div>
        </section>
      {/if}
    </div>
  </section>
</div>

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="description" content={pageDescription} />
  <meta property="og:title" content={pageTitle} />
  <meta property="og:description" content={pageDescription} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  {#if comun?.logo_url}
    <meta property="og:image" content={comun.logo_url} />
    <meta name="twitter:image" content={comun.logo_url} />
    <meta name="twitter:card" content="summary_large_image" />
  {/if}
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>

<style>
  .roadmap-page-shell {
    position: relative;
    border: 1px solid rgba(148, 163, 184, 0.28);
    background:
      radial-gradient(circle at 12% 12%, rgba(59, 130, 246, 0.12), transparent 38%),
      radial-gradient(circle at 88% 8%, rgba(249, 115, 22, 0.12), transparent 34%),
      linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.95));
    box-shadow: 0 24px 60px rgba(15, 23, 42, 0.08);
  }

  :global(.dark) .roadmap-page-shell {
    border-color: rgba(63, 63, 70, 0.9);
    background:
      radial-gradient(circle at 12% 12%, rgba(59, 130, 246, 0.18), transparent 38%),
      radial-gradient(circle at 88% 8%, rgba(249, 115, 22, 0.14), transparent 34%),
      linear-gradient(180deg, rgba(24, 24, 27, 0.96), rgba(10, 10, 11, 0.97));
    box-shadow: 0 24px 60px rgba(0, 0, 0, 0.34);
  }

  .roadmap-page-glow {
    position: absolute;
    inset: -4px;
    pointer-events: none;
    border-radius: 1.7rem;
    background: linear-gradient(
      125deg,
      rgba(59, 130, 246, 0.22),
      rgba(168, 85, 247, 0.14),
      rgba(16, 185, 129, 0.16)
    );
    filter: blur(24px);
    opacity: 0.4;
  }

  .roadmap-hero-card,
  .roadmap-side-card,
  .empty-roadmap {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: rgba(255, 255, 255, 0.78);
    backdrop-filter: blur(8px);
  }

  :global(.dark) .roadmap-hero-card,
  :global(.dark) .roadmap-side-card,
  :global(.dark) .empty-roadmap {
    border-color: rgba(63, 63, 70, 0.85);
    background: rgba(24, 24, 27, 0.72);
  }

  .hero-badge {
    display: inline-flex;
    align-items: center;
    border-radius: 9999px;
    padding: 0.35rem 0.7rem;
    border: 1px solid rgba(59, 130, 246, 0.25);
    background: rgba(239, 246, 255, 0.85);
    color: rgb(30 64 175);
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .hero-badge--muted {
    border-color: rgba(148, 163, 184, 0.26);
    background: rgba(248, 250, 252, 0.85);
    color: rgb(51 65 85);
  }

  .hero-badge--lane {
    border-color: hsla(var(--lane-h), 70%, 45%, 0.28);
    background: hsla(var(--lane-h), 92%, 95%, 0.9);
    color: hsl(var(--lane-h) 62% 28%);
  }

  :global(.dark) .hero-badge {
    border-color: rgba(59, 130, 246, 0.35);
    background: rgba(30, 41, 59, 0.72);
    color: rgb(147 197 253);
  }

  :global(.dark) .hero-badge--muted {
    border-color: rgba(82, 82, 91, 0.9);
    background: rgba(39, 39, 42, 0.7);
    color: rgb(212 212 216);
  }

  :global(.dark) .hero-badge--lane {
    border-color: hsla(var(--lane-h), 55%, 58%, 0.3);
    background: hsla(var(--lane-h), 44%, 18%, 0.55);
    color: hsl(var(--lane-h) 88% 82%);
  }

  .hero-text {
    color: rgb(71 85 105);
    line-height: 1.55;
    font-size: 0.95rem;
  }

  :global(.dark) .hero-text {
    color: rgb(161 161 170);
  }

  .share-url {
    background: rgba(248, 250, 252, 0.86);
    border: 1px solid rgba(148, 163, 184, 0.24);
    color: rgb(51 65 85);
    word-break: break-all;
  }

  :global(.dark) .share-url {
    background: rgba(9, 9, 11, 0.46);
    border-color: rgba(63, 63, 70, 0.85);
    color: rgb(212 212 216);
  }

  .ghost-link {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 0.8rem;
    border: 1px solid rgba(148, 163, 184, 0.26);
    padding: 0.55rem 0.8rem;
    font-size: 0.88rem;
    color: rgb(51 65 85);
    background: rgba(255, 255, 255, 0.64);
    transition: background-color 0.15s ease, border-color 0.15s ease;
  }

  .ghost-link:hover {
    border-color: rgba(100, 116, 139, 0.38);
    background: rgba(248, 250, 252, 0.9);
  }

  .ghost-link--small {
    font-size: 0.8rem;
    padding: 0.42rem 0.7rem;
  }

  :global(.dark) .ghost-link {
    border-color: rgba(63, 63, 70, 0.85);
    color: rgb(212 212 216);
    background: rgba(24, 24, 27, 0.5);
  }

  :global(.dark) .ghost-link:hover {
    border-color: rgba(82, 82, 91, 0.95);
    background: rgba(39, 39, 42, 0.7);
  }

  .stat-box {
    border: 1px solid rgba(148, 163, 184, 0.2);
    background: rgba(248, 250, 252, 0.82);
  }

  :global(.dark) .stat-box {
    border-color: rgba(63, 63, 70, 0.85);
    background: rgba(9, 9, 11, 0.38);
  }

  .stat-label {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgb(100 116 139);
  }

  .stat-value {
    margin-top: 0.25rem;
    font-size: 1.05rem;
    line-height: 1.15;
    font-weight: 700;
    color: rgb(15 23 42);
  }

  :global(.dark) .stat-label {
    color: rgb(161 161 170);
  }

  :global(.dark) .stat-value {
    color: rgb(244 244 245);
  }

  .roadmap-grid {
    display: grid;
    gap: 0.9rem;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    align-items: start;
  }

  .roadmap-lane {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background:
      linear-gradient(
        180deg,
        hsla(var(--lane-h), 95%, 97%, 0.84),
        rgba(255, 255, 255, 0.86)
      );
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
  }

  .roadmap-lane[data-highlight='1'] {
    border-color: hsla(var(--lane-h), 78%, 46%, 0.4);
    box-shadow: 0 0 0 1px hsla(var(--lane-h), 78%, 46%, 0.18) inset;
  }

  :global(.dark) .roadmap-lane {
    border-color: rgba(63, 63, 70, 0.85);
    background:
      linear-gradient(
        180deg,
        hsla(var(--lane-h), 44%, 15%, 0.4),
        rgba(24, 24, 27, 0.84)
      );
  }

  :global(.dark) .roadmap-lane[data-highlight='1'] {
    border-color: hsla(var(--lane-h), 72%, 56%, 0.42);
    box-shadow: 0 0 0 1px hsla(var(--lane-h), 72%, 56%, 0.2) inset;
  }

  .lane-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 9999px;
    padding: 0.22rem 0.55rem;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: hsl(var(--lane-h) 60% 30%);
    background: hsla(var(--lane-h), 92%, 93%, 0.94);
    border: 1px solid hsla(var(--lane-h), 84%, 56%, 0.2);
  }

  :global(.dark) .lane-pill {
    color: hsl(var(--lane-h) 88% 82%);
    background: hsla(var(--lane-h), 46%, 18%, 0.58);
    border-color: hsla(var(--lane-h), 62%, 52%, 0.22);
  }

  .lane-link {
    display: inline-flex;
    align-items: center;
    border-radius: 0.75rem;
    padding: 0.42rem 0.62rem;
    font-size: 0.78rem;
    font-weight: 600;
    color: rgb(30 64 175);
    background: rgba(239, 246, 255, 0.9);
    border: 1px solid rgba(96, 165, 250, 0.2);
  }

  :global(.dark) .lane-link {
    color: rgb(147 197 253);
    background: rgba(30, 41, 59, 0.78);
    border-color: rgba(59, 130, 246, 0.3);
  }

  .lane-description {
    margin: 0;
    color: rgb(71 85 105);
    font-size: 0.82rem;
    line-height: 1.4;
  }

  :global(.dark) .lane-description {
    color: rgb(161 161 170);
  }

  .mini-card {
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
    border: 1px solid rgba(148, 163, 184, 0.18);
    background: rgba(255, 255, 255, 0.86);
    transition:
      transform 0.14s ease,
      box-shadow 0.14s ease,
      border-color 0.14s ease;
  }

  .mini-card:hover {
    transform: translateY(-1px);
    border-color: hsla(var(--lane-h), 80%, 48%, 0.28);
    box-shadow: 0 8px 18px rgba(15, 23, 42, 0.07);
  }

  :global(.dark) .mini-card {
    border-color: rgba(63, 63, 70, 0.78);
    background: rgba(9, 9, 11, 0.36);
  }

  :global(.dark) .mini-card:hover {
    border-color: hsla(var(--lane-h), 70%, 56%, 0.3);
    box-shadow: 0 8px 18px rgba(0, 0, 0, 0.24);
  }

  .mini-card__title {
    line-clamp: 2;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: 0.88rem;
    line-height: 1.28;
    font-weight: 600;
    color: rgb(15 23 42);
  }

  .mini-card__snippet {
    line-clamp: 3;
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    font-size: 0.78rem;
    line-height: 1.4;
    color: rgb(71 85 105);
  }

  .mini-card__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.6rem;
    font-size: 0.72rem;
    color: rgb(100 116 139);
  }

  .mini-card__cta {
    font-size: 0.76rem;
    font-weight: 600;
    color: hsl(var(--lane-h) 62% 36%);
  }

  :global(.dark) .mini-card__title {
    color: rgb(244 244 245);
  }

  :global(.dark) .mini-card__snippet,
  :global(.dark) .mini-card__meta {
    color: rgb(161 161 170);
  }

  :global(.dark) .mini-card__cta {
    color: hsl(var(--lane-h) 90% 80%);
  }

  .lane-state {
    margin-top: 0.8rem;
    border-radius: 0.85rem;
    border: 1px dashed rgba(148, 163, 184, 0.28);
    background: rgba(248, 250, 252, 0.78);
    color: rgb(71 85 105);
    font-size: 0.82rem;
    line-height: 1.38;
    padding: 0.8rem;
  }

  .lane-state--error {
    border-color: rgba(244, 63, 94, 0.3);
    background: rgba(255, 241, 242, 0.84);
    color: rgb(159 18 57);
  }

  :global(.dark) .lane-state {
    border-color: rgba(82, 82, 91, 0.9);
    background: rgba(9, 9, 11, 0.34);
    color: rgb(212 212 216);
  }

  :global(.dark) .lane-state--error {
    border-color: rgba(190, 24, 93, 0.34);
    background: rgba(80, 7, 36, 0.3);
    color: rgb(253 164 175);
  }
</style>
