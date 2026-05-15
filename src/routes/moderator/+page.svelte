<script lang="ts">
  import { goto } from '$app/navigation'
  import { browser } from '$app/environment'
  import {
    buildModeratorAnalyticsUrl,
    buildModeratorPostViewSettingsUrl,
    buildModeratorPostViewSettingUrl,
  } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import {
    ChartBar,
    ChatBubbleLeftRight,
    Eye,
    Heart,
    Newspaper,
    UserGroup,
    Users,
    Icon,
  } from 'svelte-hero-icons'

  type AnalyticsTotals = {
    communities: number
    authors: number
    comments: number
    likes: number
    posts_telegram: number
    posts_site: number
    post_real_views: number
    average_real_views_per_post: number
  }

  type AnalyticsResponse = {
    ok: boolean
    error?: string
    period?: {
      from: string
      to: string
    }
    totals?: AnalyticsTotals
    breakdown?: {
      post_likes: number
      comment_likes: number
    }
  }

  type PostViewSettingsItem = {
    id: number
    title: string
    created_at: string
    real_views_count: number
    display_views_target: number
    display_views_current: number
    views_total: number
    author: {
      id: number
      username: string
      title?: string | null
    }
  }

  type PostViewSettingsResponse = {
    ok: boolean
    error?: string
    posts?: PostViewSettingsItem[]
    post?: PostViewSettingsItem
  }

  const dateValue = (date: Date) => {
    const year = date.getFullYear()
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    return `${year}-${month}-${day}`
  }
  const today = new Date()
  const monthAgo = new Date(today)
  monthAgo.setDate(monthAgo.getDate() - 30)

  let from = dateValue(monthAgo)
  let to = dateValue(today)
  let loading = true
  let error = ''
  let analytics: AnalyticsResponse | null = null
  let viewSettingsLoading = true
  let viewSettingsError = ''
  let viewSettingsQuery = ''
  let viewSettingsPosts: PostViewSettingsItem[] = []
  let savingViewSettings: Record<number, boolean> = {}

  const metrics = (totals: AnalyticsTotals) => [
    {
      key: 'communities',
      label: 'Сообщества',
      value: totals.communities,
      icon: UserGroup,
    },
    {
      key: 'authors',
      label: 'Авторы',
      value: totals.authors,
      icon: Users,
    },
    {
      key: 'comments',
      label: 'Комментарии',
      value: totals.comments,
      icon: ChatBubbleLeftRight,
    },
    {
      key: 'likes',
      label: 'Лайки',
      value: totals.likes,
      icon: Heart,
    },
    {
      key: 'posts_telegram',
      label: 'Публикации из Telegram',
      value: totals.posts_telegram,
      icon: ChartBar,
    },
    {
      key: 'posts_site',
      label: 'Публикации через сайт',
      value: totals.posts_site,
      icon: Newspaper,
    },
    {
      key: 'post_real_views',
      label: 'Просмотры постов',
      value: totals.post_real_views,
      icon: Eye,
    },
    {
      key: 'average_real_views_per_post',
      label: 'Среднее на пост',
      value: totals.average_real_views_per_post,
      icon: ChartBar,
    },
  ]

  const formatNumber = (value: number) => new Intl.NumberFormat('ru-RU').format(value)
  const formatDate = (value: string) =>
    new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(new Date(value))

  async function loadAnalytics() {
    if (!$siteUser?.is_staff) return
    loading = true
    error = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorAnalyticsUrl({ from, to }), {
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      const data = (await response.json()) as AnalyticsResponse
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Не удалось загрузить аналитику')
      }
      analytics = data
    } catch (err) {
      error = err instanceof Error ? err.message : 'Не удалось загрузить аналитику'
      analytics = null
    } finally {
      loading = false
    }
  }

  async function loadViewSettings() {
    if (!$siteUser?.is_staff) return
    viewSettingsLoading = true
    viewSettingsError = ''

    try {
      const token = $siteToken
      const response = await fetch(
        buildModeratorPostViewSettingsUrl({ q: viewSettingsQuery.trim(), limit: 30 }),
        {
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      )
      const data = (await response.json()) as PostViewSettingsResponse
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Не удалось загрузить просмотры')
      }
      viewSettingsPosts = data.posts ?? []
    } catch (err) {
      viewSettingsError = err instanceof Error ? err.message : 'Не удалось загрузить просмотры'
      viewSettingsPosts = []
    } finally {
      viewSettingsLoading = false
    }
  }

  async function saveViewSettings(post: PostViewSettingsItem) {
    const nextTarget = Math.max(0, Math.trunc(Number(post.display_views_target) || 0))
    post.display_views_target = nextTarget
    savingViewSettings = { ...savingViewSettings, [post.id]: true }
    viewSettingsError = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorPostViewSettingUrl(post.id), {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ display_views_target: nextTarget }),
      })
      const data = (await response.json()) as PostViewSettingsResponse
      if (!response.ok || !data.ok || !data.post) {
        throw new Error(data.error || 'Не удалось сохранить просмотры')
      }
      viewSettingsPosts = viewSettingsPosts.map((item) =>
        item.id === post.id ? data.post! : item
      )
    } catch (err) {
      viewSettingsError = err instanceof Error ? err.message : 'Не удалось сохранить просмотры'
    } finally {
      savingViewSettings = { ...savingViewSettings, [post.id]: false }
    }
  }

  function setPreset(days: number) {
    const end = new Date()
    const start = new Date(end)
    start.setDate(start.getDate() - days)
    from = dateValue(start)
    to = dateValue(end)
    loadAnalytics()
  }

  onMount(async () => {
    if (!browser) return
    const currentUser = $siteUser || (await refreshSiteUser())
    if (!currentUser) {
      goto(`/login?next=${encodeURIComponent('/moderator')}`)
      return
    }
    if (!currentUser.is_staff) {
      goto('/')
      return
    }
    loadAnalytics()
    loadViewSettings()
  })
</script>

<svelte:head>
  <title>Модераторская | Тамбур</title>
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<div class="moderator-dashboard">
  <section class="dashboard-header">
    <div>
      <p class="eyebrow">Модераторская</p>
      <h1>Аналитика сайта</h1>
    </div>

    <form class="period-form" on:submit|preventDefault={loadAnalytics}>
      <div class="preset-group" aria-label="Быстрый выбор периода">
        <button type="button" on:click={() => setPreset(7)}>7 дней</button>
        <button type="button" on:click={() => setPreset(30)}>30 дней</button>
        <button type="button" on:click={() => setPreset(90)}>90 дней</button>
      </div>
      <label>
        <span>С</span>
        <input type="date" bind:value={from} max={to} />
      </label>
      <label>
        <span>По</span>
        <input type="date" bind:value={to} min={from} />
      </label>
      <button class="primary-button" type="submit" disabled={loading}>
        Обновить
      </button>
    </form>
  </section>

  {#if error}
    <div class="notice error">{error}</div>
  {/if}

  {#if loading}
    <div class="metrics-grid">
      {#each Array(8) as _}
        <div class="metric-card skeleton"></div>
      {/each}
    </div>
  {:else if analytics?.totals}
    <div class="metrics-grid">
      {#each metrics(analytics.totals) as metric}
        <article class="metric-card">
          <div class="metric-icon">
            <Icon src={metric.icon} size="22" />
          </div>
          <div>
            <p>{metric.label}</p>
            <strong>{formatNumber(metric.value)}</strong>
          </div>
        </article>
      {/each}
    </div>

    <section class="analytics-section">
      <div>
        <p class="section-label">Раздел</p>
        <h2>Аналитика</h2>
      </div>
      <div class="summary-row">
        <span>Период: {analytics.period?.from} - {analytics.period?.to}</span>
        <span>
          Лайки постов: {formatNumber(analytics.breakdown?.post_likes ?? 0)}
        </span>
        <span>
          Лайки комментариев: {formatNumber(analytics.breakdown?.comment_likes ?? 0)}
        </span>
      </div>
    </section>
  {/if}

  <section class="view-settings-section">
    <div class="section-header">
      <div>
        <p class="section-label">Раздел</p>
        <h2>Настройки просмотров</h2>
      </div>
      <form class="view-settings-search" on:submit|preventDefault={loadViewSettings}>
        <input
          type="search"
          bind:value={viewSettingsQuery}
          placeholder="ID, заголовок или автор"
          aria-label="Поиск постов"
        />
        <button class="secondary-button" type="submit" disabled={viewSettingsLoading}>
          Найти
        </button>
      </form>
    </div>

    {#if viewSettingsError}
      <div class="notice error">{viewSettingsError}</div>
    {/if}

    {#if viewSettingsLoading}
      <div class="view-settings-table">
        {#each Array(5) as _}
          <div class="view-settings-row skeleton"></div>
        {/each}
      </div>
    {:else if viewSettingsPosts.length}
      <div class="view-settings-table">
        {#each viewSettingsPosts as post (post.id)}
          <article class="view-settings-row">
            <div class="post-info">
              <strong>{post.title}</strong>
              <span>
                #{post.id} · {post.author.title || post.author.username} · {formatDate(post.created_at)}
              </span>
            </div>
            <div class="view-cell">
              <span>Реальные</span>
              <strong>{formatNumber(post.real_views_count)}</strong>
            </div>
            <label class="display-input">
              <span>Цель отображения</span>
              <input
                type="number"
                min="0"
                max="1000000"
                step="1"
                bind:value={post.display_views_target}
              />
            </label>
            <div class="view-cell">
              <span>Отображение сейчас</span>
              <strong>{formatNumber(post.display_views_current)}</strong>
            </div>
            <div class="view-cell">
              <span>Итого</span>
              <strong>{formatNumber(post.views_total)}</strong>
            </div>
            <button
              class="secondary-button save-button"
              type="button"
              disabled={savingViewSettings[post.id]}
              on:click={() => saveViewSettings(post)}
            >
              {savingViewSettings[post.id] ? 'Сохраняю' : 'Сохранить'}
            </button>
          </article>
        {/each}
      </div>
    {:else}
      <div class="empty-state">Посты не найдены.</div>
    {/if}
  </section>
</div>

<style>
  .moderator-dashboard {
    width: min(1120px, 100%);
    margin: 0 auto;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .dashboard-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 18px;
    padding: 8px 0 4px;
  }

  .eyebrow,
  .section-label {
    margin: 0 0 4px;
    color: rgb(100 116 139);
    font-size: 13px;
  }

  h1,
  h2 {
    margin: 0;
    color: rgb(15 23 42);
    font-weight: 600;
    letter-spacing: 0;
  }

  h1 {
    font-size: 32px;
    line-height: 1.12;
  }

  h2 {
    font-size: 22px;
    line-height: 1.2;
  }

  .period-form {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    align-items: flex-end;
    gap: 10px;
  }

  .preset-group {
    display: inline-flex;
    min-height: 38px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    overflow: hidden;
    background: white;
  }

  .preset-group button {
    border: 0;
    border-right: 1px solid rgb(226 232 240);
    background: transparent;
    padding: 0 12px;
    color: rgb(51 65 85);
    cursor: pointer;
  }

  .preset-group button:last-child {
    border-right: 0;
  }

  .period-form label {
    display: grid;
    gap: 4px;
    color: rgb(71 85 105);
    font-size: 12px;
  }

  .period-form input {
    height: 38px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    padding: 0 10px;
    background: white;
    color: rgb(15 23 42);
  }

  .primary-button {
    height: 38px;
    border: 0;
    border-radius: 8px;
    padding: 0 16px;
    background: rgb(37 99 235);
    color: white;
    cursor: pointer;
  }

  .primary-button:disabled {
    opacity: 0.65;
    cursor: default;
  }

  .metrics-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }

  .metric-card {
    min-height: 118px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: white;
    padding: 18px;
    display: flex;
    align-items: flex-start;
    gap: 14px;
  }

  .metric-card p {
    margin: 0 0 10px;
    color: rgb(71 85 105);
    font-size: 14px;
  }

  .metric-card strong {
    display: block;
    color: rgb(15 23 42);
    font-size: 34px;
    line-height: 1;
    font-weight: 650;
  }

  .metric-icon {
    width: 42px;
    height: 42px;
    border-radius: 8px;
    display: grid;
    place-items: center;
    background: rgb(239 246 255);
    color: rgb(37 99 235);
    flex: 0 0 auto;
  }

  .analytics-section,
  .view-settings-section {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: white;
    padding: 18px;
  }

  .analytics-section {
    display: flex;
    justify-content: space-between;
    gap: 18px;
  }

  .section-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 16px;
    margin-bottom: 16px;
  }

  .summary-row {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: flex-end;
    gap: 8px;
    color: rgb(71 85 105);
    font-size: 14px;
  }

  .summary-row span {
    border: 1px solid rgb(226 232 240);
    border-radius: 999px;
    padding: 6px 10px;
    background: rgb(248 250 252);
  }

  .view-settings-search {
    display: flex;
    align-items: flex-end;
    gap: 10px;
  }

  .view-settings-search input,
  .display-input input {
    height: 38px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    padding: 0 10px;
    background: white;
    color: rgb(15 23 42);
  }

  .view-settings-search input {
    width: min(320px, 46vw);
  }

  .secondary-button {
    height: 38px;
    border: 1px solid rgb(203 213 225);
    border-radius: 8px;
    padding: 0 14px;
    background: white;
    color: rgb(15 23 42);
    cursor: pointer;
    white-space: nowrap;
  }

  .secondary-button:disabled {
    opacity: 0.6;
    cursor: default;
  }

  .view-settings-table {
    display: grid;
    gap: 10px;
  }

  .view-settings-row {
    min-height: 76px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    padding: 12px;
    display: grid;
    grid-template-columns: minmax(220px, 1.7fr) repeat(4, minmax(96px, 0.65fr)) auto;
    gap: 12px;
    align-items: center;
    background: rgb(248 250 252);
  }

  .post-info {
    min-width: 0;
    display: grid;
    gap: 5px;
  }

  .post-info strong {
    overflow: hidden;
    color: rgb(15 23 42);
    font-size: 15px;
    line-height: 1.25;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .post-info span,
  .view-cell span,
  .display-input span {
    color: rgb(100 116 139);
    font-size: 12px;
    line-height: 1.2;
  }

  .view-cell,
  .display-input {
    min-width: 0;
    display: grid;
    gap: 5px;
  }

  .view-cell strong {
    color: rgb(15 23 42);
    font-size: 18px;
    line-height: 1.2;
  }

  .display-input input {
    width: 100%;
    min-width: 0;
  }

  .save-button {
    justify-self: end;
  }

  .empty-state {
    border: 1px dashed rgb(203 213 225);
    border-radius: 8px;
    padding: 22px;
    color: rgb(71 85 105);
    text-align: center;
  }

  .notice {
    border-radius: 8px;
    padding: 12px 14px;
    font-size: 14px;
  }

  .notice.error {
    border: 1px solid rgb(254 202 202);
    background: rgb(254 242 242);
    color: rgb(153 27 27);
  }

  .skeleton {
    background: linear-gradient(90deg, rgb(241 245 249), white, rgb(241 245 249));
    background-size: 200% 100%;
    animation: pulse 1.2s ease-in-out infinite;
  }

  @keyframes pulse {
    from {
      background-position: 200% 0;
    }
    to {
      background-position: -200% 0;
    }
  }

  :global(.dark) .eyebrow,
  :global(.dark) .section-label,
  :global(.dark) .metric-card p,
  :global(.dark) .summary-row,
  :global(.dark) .period-form label,
  :global(.dark) .post-info span,
  :global(.dark) .view-cell span,
  :global(.dark) .display-input span,
  :global(.dark) .empty-state {
    color: rgb(161 161 170);
  }

  :global(.dark) h1,
  :global(.dark) h2,
  :global(.dark) .metric-card strong,
  :global(.dark) .period-form input,
  :global(.dark) .view-settings-search input,
  :global(.dark) .display-input input,
  :global(.dark) .secondary-button,
  :global(.dark) .post-info strong,
  :global(.dark) .view-cell strong {
    color: white;
  }

  :global(.dark) .metric-card,
  :global(.dark) .analytics-section,
  :global(.dark) .view-settings-section,
  :global(.dark) .view-settings-row,
  :global(.dark) .preset-group,
  :global(.dark) .period-form input,
  :global(.dark) .view-settings-search input,
  :global(.dark) .display-input input,
  :global(.dark) .secondary-button,
  :global(.dark) .empty-state {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27);
  }

  :global(.dark) .preset-group button {
    border-color: rgb(63 63 70);
    color: rgb(228 228 231);
  }

  :global(.dark) .metric-icon {
    background: rgb(30 58 138 / 0.35);
    color: rgb(147 197 253);
  }

  :global(.dark) .summary-row span {
    border-color: rgb(63 63 70);
    background: rgb(39 39 42);
  }

  :global(.dark) .skeleton {
    background: linear-gradient(90deg, rgb(39 39 42), rgb(24 24 27), rgb(39 39 42));
    background-size: 200% 100%;
  }

  @media (max-width: 900px) {
    .dashboard-header,
    .analytics-section,
    .section-header {
      align-items: stretch;
      flex-direction: column;
    }

    .period-form,
    .summary-row {
      justify-content: flex-start;
    }

    .metrics-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .view-settings-search {
      align-items: stretch;
    }

    .view-settings-search input {
      width: 100%;
    }

    .view-settings-row {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .post-info,
    .save-button {
      grid-column: 1 / -1;
    }

    .save-button {
      justify-self: stretch;
    }
  }

  @media (max-width: 560px) {
    h1 {
      font-size: 27px;
    }

    .period-form {
      display: grid;
      grid-template-columns: 1fr 1fr;
    }

    .preset-group,
    .primary-button {
      grid-column: 1 / -1;
    }

    .metrics-grid {
      grid-template-columns: 1fr;
    }

    .view-settings-search,
    .view-settings-row {
      grid-template-columns: 1fr;
    }

    .view-settings-search {
      display: grid;
    }
  }
</style>
