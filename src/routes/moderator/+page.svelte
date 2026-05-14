<script lang="ts">
  import { goto } from '$app/navigation'
  import { browser } from '$app/environment'
  import { buildModeratorAnalyticsUrl } from '$lib/api/backend'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import {
    ChartBar,
    ChatBubbleLeftRight,
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
  ]

  const formatNumber = (value: number) => new Intl.NumberFormat('ru-RU').format(value)

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
      {#each Array(6) as _}
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

  .analytics-section {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: white;
    padding: 18px;
    display: flex;
    justify-content: space-between;
    gap: 18px;
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
  :global(.dark) .period-form label {
    color: rgb(161 161 170);
  }

  :global(.dark) h1,
  :global(.dark) h2,
  :global(.dark) .metric-card strong,
  :global(.dark) .period-form input {
    color: white;
  }

  :global(.dark) .metric-card,
  :global(.dark) .analytics-section,
  :global(.dark) .preset-group,
  :global(.dark) .period-form input {
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
    .analytics-section {
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
  }
</style>
