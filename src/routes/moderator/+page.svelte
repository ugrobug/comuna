<script lang="ts">
  import { goto } from '$app/navigation'
  import { browser } from '$app/environment'
  import {
    buildModeratorAnalyticsUrl,
    buildModeratorPostViewSettingsUrl,
    buildModeratorPostViewSettingUrl,
    buildModeratorRatingSettingsUrl,
    buildModeratorRatingSettingsUpdateUrl,
  } from '$lib/api/backend'
  import {
    EDITABLE_STATIC_PAGE_META,
    type EditableStaticPageSlug,
  } from '$lib/staticPageContent'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import {
    ChartBar,
    ChatBubbleLeftRight,
    Eye,
    Heart,
    Newspaper,
    PencilSquare,
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

  type RatingSettings = {
    post_vote_weight: number
    post_comment_weight: number
    post_comment_like_weight: number
    post_community_rating_weight: number
    post_author_rating_weight: number
    community_post_rating_weight: number
    community_post_rating_days: number
    home_posts_per_community_per_day: number
    author_post_rating_weight: number
    author_comment_like_weight: number
    updated_at?: string | null
  }

  type RatingSettingsResponse = {
    ok: boolean
    error?: string
    settings?: RatingSettings
    recalculated_comuns?: number
  }

  type ModeratorTab = 'analytics' | 'views' | 'rating' | 'static-pages'

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
  let activeTab: ModeratorTab = 'analytics'
  let ratingSettingsLoading = true
  let ratingSettingsSaving = false
  let ratingSettingsError = ''
  let ratingSettingsNotice = ''
  let ratingSettings: RatingSettings | null = null
  const staticPages = (Object.entries(EDITABLE_STATIC_PAGE_META) as Array<
    [EditableStaticPageSlug, (typeof EDITABLE_STATIC_PAGE_META)[EditableStaticPageSlug]]
  >).map(([slug, meta]) => ({
    slug,
    editPath: `/edit-page/${slug}`,
    publicPath: slug === 'about' ? '/about' : `/${slug}`,
    ...meta,
  }))

  const dashboardTitle = (tab: ModeratorTab) => {
    if (tab === 'views') return 'Настройки просмотров'
    if (tab === 'rating') return 'Настройки рейтинга'
    if (tab === 'static-pages') return 'Статичные страницы'
    return 'Аналитика сайта'
  }

  const ratingFields: {
    key: Exclude<keyof RatingSettings, 'updated_at'>
    label: string
    description: string
    step: string
    min: string
    max?: string
  }[] = [
    {
      key: 'post_vote_weight',
      label: 'Голос пользователя за пост',
      description: 'Множитель для суммы лайков и дизлайков поста.',
      step: '0.1',
      min: '0',
    },
    {
      key: 'post_comment_weight',
      label: 'Комментарий к посту',
      description: 'Сколько рейтинга получает пост за один комментарий.',
      step: '0.1',
      min: '0',
    },
    {
      key: 'post_comment_like_weight',
      label: 'Лайк комментария',
      description: 'Сколько рейтинга получает пост за лайк комментария.',
      step: '0.1',
      min: '0',
    },
    {
      key: 'post_community_rating_weight',
      label: 'Рейтинг сообщества в посте',
      description: 'Вклад рейтинга сообщества в итоговый рейтинг поста.',
      step: '0.1',
      min: '0',
    },
    {
      key: 'post_author_rating_weight',
      label: 'Рейтинг автора в посте',
      description: 'Вклад рейтинга автора в итоговый рейтинг поста.',
      step: '0.1',
      min: '0',
    },
    {
      key: 'community_post_rating_weight',
      label: 'Посты в рейтинге сообщества',
      description: 'Множитель суммы рейтингов постов для рейтинга сообщества.',
      step: '0.01',
      min: '0',
    },
    {
      key: 'community_post_rating_days',
      label: 'Окно рейтинга сообщества',
      description: 'Сколько первых дней жизни поста учитывать для рейтинга сообщества.',
      step: '1',
      min: '1',
      max: '365',
    },
    {
      key: 'home_posts_per_community_per_day',
      label: 'Постов сообщества на главной в день',
      description: 'Максимум постов одного сообщества за один день в ленте «Горячее».',
      step: '1',
      min: '1',
      max: '100',
    },
    {
      key: 'author_post_rating_weight',
      label: 'Посты в рейтинге автора',
      description: 'Множитель рейтинга постов автора.',
      step: '0.1',
      min: '0',
    },
    {
      key: 'author_comment_like_weight',
      label: 'Лайки комментариев автора',
      description: 'Сколько рейтинга автор получает за лайк его комментария.',
      step: '0.1',
      min: '0',
    },
  ]

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
  async function readModeratorJson<T>(response: Response): Promise<T> {
    const contentType = response.headers.get('content-type') ?? ''
    if (!contentType.includes('application/json')) {
      throw new Error(`Сервер вернул не JSON (${response.status})`)
    }
    return (await response.json()) as T
  }

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
      const data = await readModeratorJson<AnalyticsResponse>(response)
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
      const data = await readModeratorJson<PostViewSettingsResponse>(response)
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
      const data = await readModeratorJson<PostViewSettingsResponse>(response)
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

  async function loadRatingSettings() {
    if (!$siteUser?.is_staff) return
    ratingSettingsLoading = true
    ratingSettingsError = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorRatingSettingsUrl(), {
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      const data = await readModeratorJson<RatingSettingsResponse>(response)
      if (!response.ok || !data.ok || !data.settings) {
        throw new Error(data.error || 'Не удалось загрузить настройки рейтинга')
      }
      ratingSettings = data.settings
    } catch (err) {
      ratingSettingsError =
        err instanceof Error ? err.message : 'Не удалось загрузить настройки рейтинга'
      ratingSettings = null
    } finally {
      ratingSettingsLoading = false
    }
  }

  async function saveRatingSettings() {
    if (!ratingSettings) return
    ratingSettingsSaving = true
    ratingSettingsError = ''
    ratingSettingsNotice = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorRatingSettingsUpdateUrl(), {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(ratingSettings),
      })
      const data = await readModeratorJson<RatingSettingsResponse>(response)
      if (!response.ok || !data.ok || !data.settings) {
        throw new Error(data.error || 'Не удалось сохранить настройки рейтинга')
      }
      ratingSettings = data.settings
      ratingSettingsNotice = `Сохранено. Пересчитано сообществ: ${formatNumber(data.recalculated_comuns ?? 0)}`
    } catch (err) {
      ratingSettingsError =
        err instanceof Error ? err.message : 'Не удалось сохранить настройки рейтинга'
    } finally {
      ratingSettingsSaving = false
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
    loadRatingSettings()
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
      <h1>{dashboardTitle(activeTab)}</h1>
    </div>

    {#if activeTab === 'analytics'}
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
    {/if}
  </section>

  <nav class="moderator-tabs" aria-label="Разделы модераторской">
    <button
      type="button"
      class:active={activeTab === 'analytics'}
      on:click={() => (activeTab = 'analytics')}
    >
      Аналитика
    </button>
    <button
      type="button"
      class:active={activeTab === 'views'}
      on:click={() => (activeTab = 'views')}
    >
      Просмотры
    </button>
    <button
      type="button"
      class:active={activeTab === 'rating'}
      on:click={() => (activeTab = 'rating')}
    >
      Рейтинг
    </button>
    <button
      type="button"
      class:active={activeTab === 'static-pages'}
      on:click={() => (activeTab = 'static-pages')}
    >
      Статичные страницы
    </button>
  </nav>

  {#if activeTab === 'analytics'}
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
  {/if}

  {#if activeTab === 'views'}
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
  {/if}

  {#if activeTab === 'rating'}
    <section class="rating-settings-section">
      <div class="section-header">
        <div>
          <p class="section-label">Раздел</p>
          <h2>Настройки рейтинга</h2>
        </div>
        <button
          class="primary-button"
          type="button"
          disabled={ratingSettingsSaving || ratingSettingsLoading || !ratingSettings}
          on:click={saveRatingSettings}
        >
          {ratingSettingsSaving ? 'Сохраняю' : 'Сохранить'}
        </button>
      </div>

      {#if ratingSettingsError}
        <div class="notice error">{ratingSettingsError}</div>
      {/if}
      {#if ratingSettingsNotice}
        <div class="notice success">{ratingSettingsNotice}</div>
      {/if}

      {#if ratingSettingsLoading}
        <div class="rating-settings-grid">
          {#each Array(10) as _}
            <div class="rating-setting-card skeleton"></div>
          {/each}
        </div>
      {:else if ratingSettings}
        <div class="formula-strip">
          <span>Пост = голоса + комментарии + лайки комментариев + сообщество + автор</span>
          <span>Сообщество = посты за первые {ratingSettings.community_post_rating_days} дней * {ratingSettings.community_post_rating_weight}</span>
          <span>Главная = до {ratingSettings.home_posts_per_community_per_day} постов сообщества в день</span>
          <span>Автор = посты автора + лайки его комментариев</span>
        </div>

        <div class="rating-settings-grid">
          {#each ratingFields as field}
            <label class="rating-setting-card">
              <span>{field.label}</span>
              <input
                type="number"
                min={field.min}
                max={field.max}
                step={field.step}
                bind:value={ratingSettings[field.key]}
              />
              <small>{field.description}</small>
            </label>
          {/each}
        </div>
      {:else}
        <div class="empty-state">Настройки рейтинга не загружены.</div>
      {/if}
    </section>
  {/if}

  {#if activeTab === 'static-pages'}
    <section class="static-pages-section">
      <div class="section-header">
        <div>
          <p class="section-label">Раздел</p>
          <h2>Статичные страницы</h2>
        </div>
      </div>

      <div class="static-pages-list">
        {#each staticPages as staticPage (staticPage.slug)}
          <article class="static-page-row">
            <div class="static-page-info">
              <strong>{staticPage.heading}</strong>
              <span>{staticPage.description}</span>
              <a href={staticPage.publicPath} target="_blank" rel="noopener noreferrer">
                {staticPage.publicPath}
              </a>
            </div>
            <a
              class="icon-action"
              href={staticPage.editPath}
              aria-label={`Редактировать страницу «${staticPage.heading}»`}
              title="Редактировать"
            >
              <Icon src={PencilSquare} size="18" micro />
            </a>
          </article>
        {/each}
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

  .moderator-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    border-bottom: 1px solid rgb(226 232 240);
  }

  .moderator-tabs button {
    min-height: 40px;
    border: 0;
    border-bottom: 2px solid transparent;
    background: transparent;
    padding: 0 12px;
    color: rgb(71 85 105);
    cursor: pointer;
  }

  .moderator-tabs button.active {
    border-bottom-color: rgb(37 99 235);
    color: rgb(15 23 42);
    font-weight: 600;
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
  .view-settings-section,
  .rating-settings-section,
  .static-pages-section {
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

  .static-pages-list {
    display: grid;
    gap: 10px;
  }

  .static-page-row {
    min-height: 84px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    padding: 14px;
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 14px;
    align-items: center;
    background: rgb(248 250 252);
  }

  .static-page-info {
    min-width: 0;
    display: grid;
    gap: 5px;
  }

  .static-page-info strong {
    color: rgb(15 23 42);
    font-size: 15px;
    line-height: 1.25;
  }

  .static-page-info span,
  .static-page-info a {
    color: rgb(100 116 139);
    font-size: 13px;
    line-height: 1.35;
  }

  .static-page-info a {
    width: fit-content;
    text-decoration: none;
  }

  .static-page-info a:hover {
    color: rgb(37 99 235);
  }

  .icon-action {
    width: 38px;
    height: 38px;
    border: 1px solid rgb(203 213 225);
    border-radius: 8px;
    display: grid;
    place-items: center;
    background: white;
    color: rgb(15 23 42);
  }

  .icon-action:hover {
    border-color: rgb(37 99 235);
    color: rgb(37 99 235);
  }

  .formula-strip {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 14px;
  }

  .formula-strip span {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    padding: 8px 10px;
    background: rgb(248 250 252);
    color: rgb(51 65 85);
    font-size: 13px;
  }

  .rating-settings-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 12px;
  }

  .rating-setting-card {
    min-height: 132px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: rgb(248 250 252);
    padding: 14px;
    display: grid;
    gap: 9px;
    align-content: start;
  }

  .rating-setting-card span {
    color: rgb(15 23 42);
    font-size: 14px;
    font-weight: 600;
    line-height: 1.25;
  }

  .rating-setting-card input {
    width: 100%;
    height: 38px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    padding: 0 10px;
    background: white;
    color: rgb(15 23 42);
  }

  .rating-setting-card small {
    color: rgb(100 116 139);
    font-size: 12px;
    line-height: 1.35;
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

  .notice.success {
    border: 1px solid rgb(187 247 208);
    background: rgb(240 253 244);
    color: rgb(22 101 52);
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
  :global(.dark) .moderator-tabs button,
  :global(.dark) .post-info span,
  :global(.dark) .static-page-info span,
  :global(.dark) .static-page-info a,
  :global(.dark) .view-cell span,
  :global(.dark) .display-input span,
  :global(.dark) .rating-setting-card small,
  :global(.dark) .empty-state {
    color: rgb(161 161 170);
  }

  :global(.dark) h1,
  :global(.dark) h2,
  :global(.dark) .moderator-tabs button.active,
  :global(.dark) .metric-card strong,
  :global(.dark) .period-form input,
  :global(.dark) .view-settings-search input,
  :global(.dark) .display-input input,
  :global(.dark) .rating-setting-card span,
  :global(.dark) .rating-setting-card input,
  :global(.dark) .secondary-button,
  :global(.dark) .icon-action,
  :global(.dark) .post-info strong,
  :global(.dark) .static-page-info strong,
  :global(.dark) .view-cell strong {
    color: white;
  }

  :global(.dark) .metric-card,
  :global(.dark) .analytics-section,
  :global(.dark) .view-settings-section,
  :global(.dark) .rating-settings-section,
  :global(.dark) .static-pages-section,
  :global(.dark) .view-settings-row,
  :global(.dark) .static-page-row,
  :global(.dark) .rating-setting-card,
  :global(.dark) .preset-group,
  :global(.dark) .period-form input,
  :global(.dark) .view-settings-search input,
  :global(.dark) .display-input input,
  :global(.dark) .rating-setting-card input,
  :global(.dark) .secondary-button,
  :global(.dark) .icon-action,
  :global(.dark) .empty-state {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27);
  }

  :global(.dark) .moderator-tabs {
    border-color: rgb(63 63 70);
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

  :global(.dark) .formula-strip span {
    border-color: rgb(63 63 70);
    background: rgb(39 39 42);
    color: rgb(212 212 216);
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

    .rating-settings-grid {
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

    .rating-settings-grid {
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
