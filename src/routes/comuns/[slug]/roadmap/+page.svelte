<script lang="ts">
  import { page } from '$app/stores'
  import { onDestroy } from 'svelte'
  import { toast } from 'mono-svelte'
  import {
    Icon,
    MagnifyingGlass,
    Plus,
    XMark,
  } from 'svelte-hero-icons'
  import Portal from '$lib/mono/popover/Portal.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import {
    buildBackendPostPath,
    buildComunRoadmapPostsUrl,
    buildComunRoadmapUrl,
    type BackendComun,
    type BackendComunRoadmapItem,
    type BackendComunRoadmapStage,
    type BackendPost,
  } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { env } from '$env/dynamic/public'

  export let data

  type StageDefinition = {
    key: BackendComunRoadmapStage
    label: string
    empty: string
  }

  const STAGES: StageDefinition[] = [
    {
      key: 'planned',
      label: 'Планируется',
      empty: 'В планах пока нет постов.',
    },
    {
      key: 'in_progress',
      label: 'В работе',
      empty: 'Сейчас в работе ничего нет.',
    },
    {
      key: 'done',
      label: 'Сделано',
      empty: 'Завершенных задач пока нет.',
    },
  ]

  let comun: BackendComun | null = data?.comun ?? null
  let items: BackendComunRoadmapItem[] = Array.isArray(data?.items) ? data.items : []
  let addModalOpen = false
  let selectedStage: BackendComunRoadmapStage = 'planned'
  let searchQuery = ''
  let candidatePosts: BackendPost[] = []
  let candidatesLoading = false
  let addingPostId: number | null = null
  let searchTimer: ReturnType<typeof setTimeout> | null = null
  let requestSequence = 0

  const authHeaders = () => ({
    Authorization: `Bearer ${$siteToken}`,
    'Content-Type': 'application/json',
  })

  const stageStyleVars = (stage: BackendComunRoadmapStage) => {
    if (stage === 'planned') return '--lane-h: 34; --lane-s: 88%; --lane-l: 50%;'
    if (stage === 'in_progress') return '--lane-h: 153; --lane-s: 77%; --lane-l: 40%;'
    return '--lane-h: 340; --lane-s: 78%; --lane-l: 52%;'
  }

  const stageBadgeLabel = (stage: BackendComunRoadmapStage) => {
    if (stage === 'planned') return 'Дальше'
    if (stage === 'in_progress') return 'В работе'
    return 'Готово'
  }

  const formatCount = (value: number) =>
    new Intl.NumberFormat(data?.language === 'ru' ? 'ru-RU' : data?.language || 'en').format(value)

  const formatDate = (value?: string | null) => {
    if (!value) return ''
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return new Intl.DateTimeFormat(data?.language === 'ru' ? 'ru-RU' : data?.language || 'en', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }).format(date)
  }

  const postSnippet = (post: BackendPost) => {
    const source = String(post.content || '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()
    return source.length > 150 ? `${source.slice(0, 149).trimEnd()}…` : source
  }

  const closeAddModal = () => {
    addModalOpen = false
    searchQuery = ''
    candidatePosts = []
    addingPostId = null
    requestSequence += 1
  }

  const loadCandidates = async () => {
    if (!comun?.slug || !$siteToken) return
    const requestId = ++requestSequence
    candidatesLoading = true
    try {
      const response = await fetch(
        buildComunRoadmapPostsUrl(comun.slug, {
          q: searchQuery.trim() || undefined,
          limit: 30,
          language: data?.language,
        }),
        { headers: authHeaders() }
      )
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить посты')
      }
      if (requestId === requestSequence) {
        candidatePosts = Array.isArray(payload?.posts) ? payload.posts : []
      }
    } catch (error) {
      if (requestId === requestSequence) {
        candidatePosts = []
        toast({
          content: error instanceof Error ? error.message : 'Не удалось загрузить посты',
          type: 'error',
        })
      }
    } finally {
      if (requestId === requestSequence) candidatesLoading = false
    }
  }

  const openAddModal = (stage: BackendComunRoadmapStage) => {
    selectedStage = stage
    searchQuery = ''
    candidatePosts = []
    addModalOpen = true
    void loadCandidates()
  }

  const scheduleCandidateSearch = () => {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => void loadCandidates(), 250)
  }

  const addPost = async (post: BackendPost) => {
    if (!comun?.slug || !$siteToken || addingPostId) return
    addingPostId = post.id
    try {
      const response = await fetch(buildComunRoadmapUrl(comun.slug), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ post_id: post.id, stage: selectedStage }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(
          response.status === 409
            ? 'Этот пост уже добавлен в дорожную карту'
            : payload?.error || 'Не удалось добавить пост'
        )
      }
      if (payload?.item) {
        items = [...items, payload.item as BackendComunRoadmapItem]
      }
      closeAddModal()
      toast({ content: 'Пост добавлен в дорожную карту', type: 'success' })
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Не удалось добавить пост',
        type: 'error',
      })
    } finally {
      addingPostId = null
    }
  }

  $: currentUserId = Number($siteUser?.id ?? 0)
  $: canManageRoadmap = Boolean(
    $siteToken &&
      currentUserId > 0 &&
      Number(comun?.creator?.id ?? 0) === currentUserId
  )
  $: selectedStageDefinition =
    STAGES.find((stage) => stage.key === selectedStage) ?? STAGES[0]
  $: pageTitle = `Дорожная карта — ${comun?.name || 'Сообщество'}`
  $: pageDescription =
    comun?.product_description?.trim() ||
    `Дорожная карта сообщества «${comun?.name || 'Сообщество'}».`
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

  onDestroy(() => {
    if (searchTimer) clearTimeout(searchTimer)
  })
</script>

<div class="mx-auto flex w-full max-w-7xl flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="min-w-0">
      <Header noMargin>Публичная дорожная карта</Header>
      {#if comun?.name}
        <div class="truncate text-sm text-slate-600 dark:text-zinc-400">{comun.name}</div>
      {/if}
    </div>
    <a
      href={comun?.slug ? `/comuns/${encodeURIComponent(comun.slug)}` : '/comuns'}
      class="inline-flex items-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-800/60"
    >
      Назад к сообществу
    </a>
  </div>

  <section class="roadmap-page-shell overflow-hidden rounded-3xl">
    <div class="roadmap-page-glow"></div>
    <div class="roadmap-page-content relative z-10 p-4 sm:p-5 lg:p-6">
      <div class="roadmap-grid">
        {#each STAGES as stage}
          {@const stageItems = items
            .filter((item) => item.stage === stage.key)
            .sort((a, b) => Number(a.position ?? 0) - Number(b.position ?? 0))}
          <section class="roadmap-lane rounded-2xl p-4" style={stageStyleVars(stage.key)}>
            <header class="lane-header">
              <div class="min-w-0">
                <div class="lane-pill">{stageBadgeLabel(stage.key)}</div>
                <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                  {formatCount(stageItems.length)} карточек
                </div>
              </div>
              {#if canManageRoadmap}
                <button
                  type="button"
                  class="add-button rounded-xl"
                  on:click={() => openAddModal(stage.key)}
                  aria-label={`Добавить пост в столбец «${stage.label}»`}
                  title={`Добавить пост в «${stage.label}»`}
                >
                  <Icon src={Plus} size="18" micro />
                </button>
              {/if}
            </header>

            <div class="lane-content">
              {#if stageItems.length}
                {#each stageItems as item (item.id)}
                  {@const snippet = postSnippet(item.post)}
                  <a href={buildBackendPostPath(item.post)} class="mini-card rounded-xl p-3">
                    <div class="mini-card__title">{item.post.title || 'Без заголовка'}</div>
                    {#if snippet}
                      <div class="mini-card__snippet">{snippet}</div>
                    {/if}
                    <div class="mini-card__meta">
                      <span>Голоса {formatCount(item.post.likes_count ?? 0)}</span>
                      <span>Комментарии {formatCount(item.post.comments_count ?? 0)}</span>
                      {#if formatDate(item.post.created_at)}
                        <span>{formatDate(item.post.created_at)}</span>
                      {/if}
                    </div>
                    <div class="mini-card__cta">Открыть карточку и обсуждение</div>
                  </a>
                {/each}
              {:else}
                <div class="lane-state">{stage.empty}</div>
              {/if}
            </div>
          </section>
        {/each}
      </div>
    </div>
  </section>
</div>

{#if addModalOpen}
  <Portal class="roadmap-add-portal">
    <div class="fixed inset-0 z-[2147483000] flex items-center justify-center p-4" role="dialog" aria-modal="true">
      <button
        type="button"
        class="absolute inset-0 bg-slate-950/50"
        on:click={closeAddModal}
        aria-label="Закрыть"
      ></button>
      <section class="relative z-10 flex max-h-[min(720px,90dvh)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-zinc-700 dark:bg-zinc-950">
        <header class="flex items-start justify-between gap-4 border-b border-slate-200 p-4 dark:border-zinc-800">
          <div>
            <h2 class="text-lg font-semibold text-slate-950 dark:text-zinc-100">Добавить пост</h2>
            <p class="mt-1 text-sm text-slate-500 dark:text-zinc-400">
              Столбец «{selectedStageDefinition.label}»
            </p>
          </div>
          <button type="button" class="close-button rounded-xl" on:click={closeAddModal} aria-label="Закрыть">
            <Icon src={XMark} size="20" micro />
          </button>
        </header>

        <div class="border-b border-slate-200 p-4 dark:border-zinc-800">
          <label class="search-field rounded-xl">
            <Icon src={MagnifyingGlass} size="18" micro />
            <input
              type="search"
              bind:value={searchQuery}
              on:input={scheduleCandidateSearch}
              placeholder="Поиск по постам сообщества"
              autocomplete="off"
            />
          </label>
        </div>

        <div class="min-h-[220px] overflow-y-auto p-2">
          {#if candidatesLoading}
            <div class="p-6 text-center text-sm text-slate-500 dark:text-zinc-400">Загружаем посты…</div>
          {:else if candidatePosts.length}
            {#each candidatePosts as post (post.id)}
              <button
                type="button"
                class="candidate-row"
                disabled={addingPostId !== null}
                on:click={() => addPost(post)}
              >
                <span class="min-w-0 flex-1">
                  <span class="block truncate text-sm font-medium text-slate-950 dark:text-zinc-100">
                    {post.title || 'Без заголовка'}
                  </span>
                  <span class="mt-1 block text-left text-xs text-slate-500 dark:text-zinc-400">
                    {formatDate(post.created_at)}
                  </span>
                </span>
                {#if addingPostId === post.id}
                  <span class="text-xs text-slate-500">Добавляем…</span>
                {:else}
                  <Icon src={Plus} size="18" micro />
                {/if}
              </button>
            {/each}
          {:else}
            <div class="p-6 text-center text-sm text-slate-500 dark:text-zinc-400">
              {searchQuery.trim()
                ? 'По вашему запросу ничего не найдено.'
                : 'Все доступные посты уже добавлены или в сообществе пока нет постов.'}
            </div>
          {/if}
        </div>
      </section>
    </div>
  </Portal>
{/if}

<svelte:head>
  <title>{pageTitle}</title>
  <meta name="description" content={pageDescription} />
  <meta property="og:title" content={pageTitle} />
  <meta property="og:description" content={pageDescription} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
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

  .roadmap-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
    align-items: start;
  }

  .roadmap-lane {
    border: 1px solid rgba(148, 163, 184, 0.22);
    background: linear-gradient(
      180deg,
      hsla(var(--lane-h), 95%, 97%, 0.84),
      rgba(255, 255, 255, 0.86)
    );
  }

  :global(.dark) .roadmap-lane {
    border-color: rgba(63, 63, 70, 0.85);
    background: linear-gradient(
      180deg,
      hsla(var(--lane-h), 44%, 15%, 0.4),
      rgba(24, 24, 27, 0.84)
    );
  }

  .lane-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .lane-pill {
    display: inline-flex;
    align-items: center;
    border-radius: 9999px;
    padding: 0.22rem 0.55rem;
    border: 1px solid hsla(var(--lane-h), 84%, 56%, 0.2);
    background: hsla(var(--lane-h), 92%, 93%, 0.94);
    color: hsl(var(--lane-h) 60% 30%);
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  :global(.dark) .lane-pill {
    border-color: hsla(var(--lane-h), 62%, 52%, 0.22);
    background: hsla(var(--lane-h), 46%, 18%, 0.58);
    color: hsl(var(--lane-h) 88% 82%);
  }

  .add-button,
  .close-button {
    display: inline-flex;
    width: 2rem;
    height: 2rem;
    flex: none;
    align-items: center;
    justify-content: center;
    border: 1px solid hsla(var(--lane-h, 220), 55%, 45%, 0.24);
    background: rgba(255, 255, 255, 0.72);
    color: hsl(var(--lane-h, 220) 62% 34%);
    transition:
      background-color 0.15s ease,
      color 0.15s ease,
      transform 0.15s ease;
  }

  .add-button:hover,
  .close-button:hover {
    background: rgba(255, 255, 255, 0.96);
    color: hsl(var(--lane-h, 220) 72% 26%);
    transform: translateY(-1px);
  }

  :global(.dark) .add-button,
  :global(.dark) .close-button {
    border-color: rgba(82, 82, 91, 0.86);
    background: rgba(24, 24, 27, 0.72);
    color: rgb(212 212 216);
  }

  :global(.dark) .add-button:hover,
  :global(.dark) .close-button:hover {
    background: rgb(39 39 42);
    color: white;
  }

  .lane-content {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin-top: 0.75rem;
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
    overflow: hidden;
    color: rgb(15 23 42);
    font-size: 0.88rem;
    font-weight: 600;
    line-height: 1.28;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .mini-card__snippet {
    line-clamp: 3;
    display: -webkit-box;
    overflow: hidden;
    color: rgb(71 85 105);
    font-size: 0.78rem;
    line-height: 1.4;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
  }

  .mini-card__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem 0.6rem;
    color: rgb(100 116 139);
    font-size: 0.72rem;
  }

  .mini-card__cta {
    color: hsl(var(--lane-h) 62% 36%);
    font-size: 0.76rem;
    font-weight: 600;
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
    border: 1px dashed rgba(148, 163, 184, 0.28);
    border-radius: 0.85rem;
    background: rgba(248, 250, 252, 0.78);
    color: rgb(71 85 105);
    font-size: 0.82rem;
    line-height: 1.38;
    padding: 0.8rem;
  }

  :global(.dark) .lane-state {
    border-color: rgba(82, 82, 91, 0.9);
    background: rgba(9, 9, 11, 0.34);
    color: rgb(212 212 216);
  }

  .search-field {
    display: flex;
    height: 2.75rem;
    align-items: center;
    gap: 0.65rem;
    border: 1px solid rgb(203 213 225);
    padding: 0 0.8rem;
    color: rgb(100 116 139);
  }

  .search-field:focus-within {
    border-color: rgb(37 99 235);
    box-shadow: 0 0 0 2px rgb(37 99 235 / 0.15);
  }

  .search-field input {
    min-width: 0;
    flex: 1;
    border: 0;
    background: transparent;
    color: rgb(15 23 42);
    outline: none;
  }

  :global(.dark) .search-field {
    border-color: rgb(63 63 70);
  }

  :global(.dark) .search-field input {
    color: rgb(244 244 245);
  }

  .candidate-row {
    display: flex;
    width: 100%;
    min-height: 64px;
    align-items: center;
    gap: 1rem;
    border-bottom: 1px solid rgb(241 245 249);
    padding: 0.75rem;
    text-align: left;
    color: rgb(71 85 105);
  }

  .candidate-row:hover:not(:disabled) {
    background: rgb(248 250 252);
    color: rgb(37 99 235);
  }

  .candidate-row:disabled {
    cursor: wait;
    opacity: 0.65;
  }

  :global(.dark) .candidate-row {
    border-color: rgb(39 39 42);
    color: rgb(161 161 170);
  }

  :global(.dark) .candidate-row:hover:not(:disabled) {
    background: rgb(24 24 27);
    color: rgb(96 165 250);
  }

  @media (max-width: 900px) {
    .roadmap-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
