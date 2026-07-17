<script lang="ts">
  import { goto } from '$app/navigation'
  import { browser } from '$app/environment'
  import {
    buildModeratorAnalyticsUrl,
    buildModeratorChatReportUrl,
    buildModeratorChatReportsUrl,
    buildModeratorContentReportUrl,
    buildModeratorContentReportsUrl,
    buildModeratorPostViewDefaultsUrl,
    buildModeratorPostViewSettingsUrl,
    buildModeratorPostViewSettingUrl,
    buildModeratorRatingSettingsUrl,
    buildModeratorRatingSettingsUpdateUrl,
    buildModeratorTranslationSettingsUpdateUrl,
    buildModeratorTranslationSettingsUrl,
    type BackendContentReport,
    type BackendSiteChatReport,
    type BackendSiteChatReportStatus,
  } from '$lib/api/backend'
  import {
    EDITABLE_STATIC_PAGE_META,
    type EditableStaticPageSlug,
  } from '$lib/staticPageContent'
  import { brandNameForLanguage } from '$lib/brand'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import { locale } from '$lib/translations'
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
    registered_users: number
    community_subscriptions: number
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
    recent_communities?: Array<{
      id: number
      name: string
      slug: string
      url: string
      logo_url?: string | null
      description?: string | null
      created_at: string
    }>
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
    defaults?: PostViewDefaults
    posts?: PostViewSettingsItem[]
    post?: PostViewSettingsItem
  }

  type PostViewDefaults = {
    fake_views_target_min: number
    fake_views_target_max: number
    updated_at?: string | null
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

  type TranslationSettings = {
    enabled: boolean
    post_daily_limit: number
    comment_daily_limit: number
    post_object_daily_limit: number
    updated_at?: string | null
    coverage?: {
      posts?: {
        total?: number
        translated?: number
        fully_translated?: number
        translation_rows?: number
        target_translation_rows?: number
        target_languages?: number
      }
      comments?: {
        total?: number
        translated?: number
        fully_translated?: number
        translation_rows?: number
        target_translation_rows?: number
        target_languages?: number
      }
      translation_rows?: {
        posts?: number
        comments?: number
        comuns?: number
        categories?: number
        terms?: number
        static_pages?: number
      }
      summary?: {
        translated?: number
        target?: number
        percent?: number
        target_languages?: number
      }
      breakdown?: Record<
        string,
        {
          translated?: number
          target?: number
          queued?: number
          total?: number
          translated_objects?: number | null
          fully_translated?: number | null
          target_languages?: number
          percent?: number
        }
      >
    }
    queue?: {
      pending?: number
      pending_posts?: number
      pending_comments?: number
      pending_comuns?: number
      pending_static_pages?: number
      breakdown?: {
        posts?: number
        comments?: number
        comuns?: number
        categories?: number
        terms?: number
        static_pages?: number
      }
    }
    usage?: {
      day_start?: string
      post_used?: number
      comment_used?: number
      comun_used?: number
      post_remaining?: number
      comment_remaining?: number
    }
  }

  type TranslationSettingsResponse = {
    ok: boolean
    error?: string
    settings?: TranslationSettings
  }

  type ChatReportsResponse = {
    ok: boolean
    error?: string
    reports?: BackendSiteChatReport[]
    report?: BackendSiteChatReport
    total?: number
    limit?: number
    offset?: number
    open_count?: number
  }

  type ContentReportsResponse = {
    ok: boolean
    error?: string
    reports?: BackendContentReport[]
    report?: BackendContentReport
    total?: number
    limit?: number
    offset?: number
    open_count?: number
  }

  type ModeratorTab =
    | 'analytics'
    | 'views'
    | 'rating'
    | 'translations'
    | 'chat-reports'
    | 'static-pages'
  type ChatReportsFilter = 'open' | 'all'

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
  let viewDefaults: PostViewDefaults | null = null
  let viewDefaultsSaving = false
  let viewDefaultsNotice = ''
  let savingViewSettings: Record<number, boolean> = {}
  let activeTab: ModeratorTab = 'analytics'
  let ratingSettingsLoading = true
  let ratingSettingsSaving = false
  let ratingSettingsError = ''
  let ratingSettingsNotice = ''
  let ratingSettings: RatingSettings | null = null
  let translationSettingsLoading = true
  let translationSettingsSaving = false
  let translationSettingsError = ''
  let translationSettingsNotice = ''
  let translationSettings: TranslationSettings | null = null
  let chatReportsLoading = true
  let chatReportsError = ''
  let chatReportsNotice = ''
  let chatReports: BackendSiteChatReport[] = []
  let chatReportsTotal = 0
  let chatReportsOpenCount = 0
  let chatReportsFilter: ChatReportsFilter = 'open'
  let savingChatReports: Record<number, boolean> = {}
  let contentReportsLoading = true
  let contentReportsError = ''
  let contentReportsNotice = ''
  let contentReports: BackendContentReport[] = []
  let contentReportsTotal = 0
  let contentReportsOpenCount = 0
  let savingContentReports: Record<number, boolean> = {}
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
    if (tab === 'translations') return 'Лимиты перевода'
    if (tab === 'chat-reports') return 'Модерация'
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
      key: 'registered_users',
      label: 'Регистрации',
      value: totals.registered_users,
      icon: Users,
    },
    {
      key: 'community_subscriptions',
      label: 'Подписки на сообщества',
      value: totals.community_subscriptions,
      icon: UserGroup,
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
  const formatPercent = (value: number) =>
    `${new Intl.NumberFormat('ru-RU', {
      maximumFractionDigits: 1,
    }).format(Number.isFinite(value) ? value : 0)}%`

  const translationBreakdownLabels: Record<string, string> = {
    posts: 'Статьи',
    comments: 'Комментарии',
    comuns: 'Сообщества',
    categories: 'Рубрики',
    terms: 'Термины',
    static_pages: 'Статичные страницы',
  }
  const translationBreakdownOrder = [
    'posts',
    'comments',
    'comuns',
    'categories',
    'terms',
    'static_pages',
  ]

  $: translationBreakdownRows = translationBreakdownOrder.map((key) => {
    const item = translationSettings?.coverage?.breakdown?.[key] ?? {}
    return {
      key,
      label: translationBreakdownLabels[key] ?? key,
      translated: Number(item.translated ?? 0),
      target: Number(item.target ?? 0),
      percent: Number(item.percent ?? 0),
    }
  })
  const formatDate = (value: string) =>
    new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    }).format(new Date(value))
  const formatDateTime = (value?: string | null) =>
    value
      ? new Intl.DateTimeFormat('ru-RU', {
          day: '2-digit',
          month: '2-digit',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        }).format(new Date(value))
      : 'Дата неизвестна'
  const chatReportUserName = (
    user: BackendSiteChatReport['reporter'] | BackendContentReport['reporter']
  ) =>
    (user.display_name || '').trim() || (user.username ? `@${user.username}` : `ID ${user.id}`)
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
      viewDefaults = data.defaults ?? viewDefaults
      viewSettingsPosts = data.posts ?? []
    } catch (err) {
      viewSettingsError = err instanceof Error ? err.message : 'Не удалось загрузить просмотры'
      viewSettingsPosts = []
    } finally {
      viewSettingsLoading = false
    }
  }

  async function saveViewDefaults() {
    if (!viewDefaults) return
    const nextMin = Math.max(0, Math.trunc(Number(viewDefaults.fake_views_target_min) || 0))
    const nextMax = Math.max(0, Math.trunc(Number(viewDefaults.fake_views_target_max) || 0))
    viewDefaults.fake_views_target_min = nextMin
    viewDefaults.fake_views_target_max = nextMax
    viewDefaultsSaving = true
    viewSettingsError = ''
    viewDefaultsNotice = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorPostViewDefaultsUrl(), {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(viewDefaults),
      })
      const data = await readModeratorJson<PostViewSettingsResponse>(response)
      if (!response.ok || !data.ok || !data.defaults) {
        throw new Error(data.error || 'Не удалось сохранить диапазон просмотров')
      }
      viewDefaults = data.defaults
      viewDefaultsNotice = 'Диапазон для новых постов сохранен.'
    } catch (err) {
      viewSettingsError =
        err instanceof Error ? err.message : 'Не удалось сохранить диапазон просмотров'
    } finally {
      viewDefaultsSaving = false
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

  async function loadTranslationSettings() {
    if (!$siteUser?.is_staff) return
    translationSettingsLoading = true
    translationSettingsError = ''
    translationSettingsNotice = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorTranslationSettingsUrl(), {
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      const data = await readModeratorJson<TranslationSettingsResponse>(response)
      if (!response.ok || !data.ok || !data.settings) {
        throw new Error(data.error || 'Не удалось загрузить настройки перевода')
      }
      translationSettings = data.settings
    } catch (err) {
      translationSettingsError =
        err instanceof Error ? err.message : 'Не удалось загрузить настройки перевода'
      translationSettings = null
    } finally {
      translationSettingsLoading = false
    }
  }

  async function saveTranslationSettings() {
    if (!translationSettings) return
    translationSettings = {
      ...translationSettings,
      post_daily_limit: Math.max(0, Math.trunc(Number(translationSettings.post_daily_limit) || 0)),
      comment_daily_limit: Math.max(
        0,
        Math.trunc(Number(translationSettings.comment_daily_limit) || 0)
      ),
      post_object_daily_limit: Math.max(
        0,
        Math.trunc(Number(translationSettings.post_object_daily_limit) || 0)
      ),
    }
    translationSettingsSaving = true
    translationSettingsError = ''
    translationSettingsNotice = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorTranslationSettingsUpdateUrl(), {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(translationSettings),
      })
      const data = await readModeratorJson<TranslationSettingsResponse>(response)
      if (!response.ok || !data.ok || !data.settings) {
        throw new Error(data.error || 'Не удалось сохранить настройки перевода')
      }
      translationSettings = data.settings
      translationSettingsNotice = 'Настройки перевода сохранены.'
    } catch (err) {
      translationSettingsError =
        err instanceof Error ? err.message : 'Не удалось сохранить настройки перевода'
    } finally {
      translationSettingsSaving = false
    }
  }

  async function loadChatReports() {
    if (!$siteUser?.is_staff) return
    chatReportsLoading = true
    chatReportsError = ''
    chatReportsNotice = ''

    try {
      const token = $siteToken
      const response = await fetch(
        buildModeratorChatReportsUrl({ status: chatReportsFilter, limit: 50 }),
        {
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      )
      const data = await readModeratorJson<ChatReportsResponse>(response)
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Не удалось загрузить жалобы')
      }
      chatReports = data.reports ?? []
      chatReportsTotal = Number(data.total ?? chatReports.length)
      chatReportsOpenCount = Number(data.open_count ?? 0)
    } catch (err) {
      chatReportsError = err instanceof Error ? err.message : 'Не удалось загрузить жалобы'
      chatReports = []
      chatReportsTotal = 0
    } finally {
      chatReportsLoading = false
    }
  }

  async function loadContentReports() {
    if (!$siteUser?.is_staff) return
    contentReportsLoading = true
    contentReportsError = ''
    contentReportsNotice = ''

    try {
      const token = $siteToken
      const response = await fetch(
        buildModeratorContentReportsUrl({ status: chatReportsFilter, limit: 50 }),
        {
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
        }
      )
      const data = await readModeratorJson<ContentReportsResponse>(response)
      if (!response.ok || !data.ok) {
        throw new Error(data.error || 'Не удалось загрузить жалобы на контент')
      }
      contentReports = data.reports ?? []
      contentReportsTotal = Number(data.total ?? contentReports.length)
      contentReportsOpenCount = Number(data.open_count ?? 0)
    } catch (err) {
      contentReportsError =
        err instanceof Error ? err.message : 'Не удалось загрузить жалобы на контент'
      contentReports = []
      contentReportsTotal = 0
    } finally {
      contentReportsLoading = false
    }
  }

  async function updateContentReportStatus(
    report: BackendContentReport,
    status: BackendSiteChatReportStatus
  ) {
    savingContentReports = { ...savingContentReports, [report.id]: true }
    contentReportsError = ''
    contentReportsNotice = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorContentReportUrl(report.id), {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ status }),
      })
      const data = await readModeratorJson<ContentReportsResponse>(response)
      if (!response.ok || !data.ok || !data.report) {
        throw new Error(data.error || 'Не удалось обновить жалобу')
      }
      contentReportsOpenCount = Number(data.open_count ?? contentReportsOpenCount)
      if (chatReportsFilter === 'open' && status !== 'open') {
        contentReports = contentReports.filter((item) => item.id !== report.id)
        contentReportsTotal = Math.max(0, contentReportsTotal - 1)
      } else {
        contentReports = contentReports.map((item) =>
          item.id === report.id ? data.report! : item
        )
      }
      contentReportsNotice =
        status === 'reviewed' ? 'Жалоба отмечена обработанной.' : 'Жалоба отклонена.'
    } catch (err) {
      contentReportsError = err instanceof Error ? err.message : 'Не удалось обновить жалобу'
    } finally {
      savingContentReports = { ...savingContentReports, [report.id]: false }
    }
  }

  async function updateChatReportStatus(
    report: BackendSiteChatReport,
    status: BackendSiteChatReportStatus
  ) {
    savingChatReports = { ...savingChatReports, [report.id]: true }
    chatReportsError = ''
    chatReportsNotice = ''

    try {
      const token = $siteToken
      const response = await fetch(buildModeratorChatReportUrl(report.id), {
        method: 'PATCH',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ status }),
      })
      const data = await readModeratorJson<ChatReportsResponse>(response)
      if (!response.ok || !data.ok || !data.report) {
        throw new Error(data.error || 'Не удалось обновить жалобу')
      }
      chatReportsOpenCount = Number(data.open_count ?? chatReportsOpenCount)
      if (chatReportsFilter === 'open' && status !== 'open') {
        chatReports = chatReports.filter((item) => item.id !== report.id)
        chatReportsTotal = Math.max(0, chatReportsTotal - 1)
      } else {
        chatReports = chatReports.map((item) => (item.id === report.id ? data.report! : item))
      }
      chatReportsNotice = status === 'reviewed' ? 'Жалоба отмечена обработанной.' : 'Жалоба отклонена.'
    } catch (err) {
      chatReportsError = err instanceof Error ? err.message : 'Не удалось обновить жалобу'
    } finally {
      savingChatReports = { ...savingChatReports, [report.id]: false }
    }
  }

  function setChatReportsFilter(filter: ChatReportsFilter) {
    chatReportsFilter = filter
    loadChatReports()
    loadContentReports()
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
    loadTranslationSettings()
    loadChatReports()
    loadContentReports()
  })
</script>

<svelte:head>
  <title>Модераторская | {brandNameForLanguage($locale)}</title>
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
      class:active={activeTab === 'translations'}
      on:click={() => (activeTab = 'translations')}
    >
      Перевод
    </button>
    <button
      type="button"
      class:active={activeTab === 'chat-reports'}
      on:click={() => (activeTab = 'chat-reports')}
    >
      Модерация
      {#if chatReportsOpenCount + contentReportsOpenCount}
        <span class="tab-badge">{chatReportsOpenCount + contentReportsOpenCount}</span>
      {/if}
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
        {#each Array(9) as _}
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

      <section class="recent-comuns-section">
        <div class="section-header">
          <div>
            <p class="section-label">Сообщества</p>
            <h2>Последние созданные</h2>
          </div>
          <span class="recent-comuns-count">
            {formatNumber(analytics.recent_communities?.length ?? 0)}
          </span>
        </div>

        {#if analytics.recent_communities?.length}
          <div class="recent-comuns-list">
            {#each analytics.recent_communities as comun (comun.id)}
              <article class="recent-comun-row">
                <Avatar
                  url={comun.logo_url || undefined}
                  alt={comun.name}
                  width={48}
                  circle={false}
                />
                <div class="recent-comun-info">
                  <a href={comun.url}>{comun.name}</a>
                  <p>{comun.description || 'Описание не заполнено.'}</p>
                </div>
                <time datetime={comun.created_at}>{formatDateTime(comun.created_at)}</time>
              </article>
            {/each}
          </div>
        {:else}
          <div class="empty-state">Сообщества пока не созданы.</div>
        {/if}
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
    {#if viewDefaultsNotice}
      <div class="notice success">{viewDefaultsNotice}</div>
    {/if}

    {#if viewDefaults}
      <article class="view-defaults-card">
        <div class="view-defaults-info">
          <strong>Диапазон фейковых просмотров для новых постов</strong>
          <span>
            Новые посты получают случайную цель в этом диапазоне. Уже созданные посты
            меняются отдельно в списке ниже.
          </span>
        </div>
        <label class="display-input">
          <span>Минимум</span>
          <input
            type="number"
            min="0"
            max="1000000"
            step="1"
            bind:value={viewDefaults.fake_views_target_min}
          />
        </label>
        <label class="display-input">
          <span>Максимум</span>
          <input
            type="number"
            min="0"
            max="1000000"
            step="1"
            bind:value={viewDefaults.fake_views_target_max}
          />
        </label>
        <button
          class="secondary-button save-button"
          type="button"
          disabled={viewDefaultsSaving}
          on:click={saveViewDefaults}
        >
          {viewDefaultsSaving ? 'Сохраняю' : 'Сохранить'}
        </button>
      </article>
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
          <span>Сообщество = накопительный рейтинг, пост влияет только первые {ratingSettings.community_post_rating_days} дней</span>
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

  {#if activeTab === 'translations'}
    <section class="translation-settings-section">
      <div class="section-header">
        <div>
          <p class="section-label">Раздел</p>
          <h2>Лимиты перевода</h2>
        </div>
        <button
          class="primary-button"
          type="button"
          disabled={translationSettingsSaving || translationSettingsLoading || !translationSettings}
          on:click={saveTranslationSettings}
        >
          {translationSettingsSaving ? 'Сохраняю' : 'Сохранить'}
        </button>
      </div>

      {#if translationSettingsError}
        <div class="notice error">{translationSettingsError}</div>
      {/if}
      {#if translationSettingsNotice}
        <div class="notice success">{translationSettingsNotice}</div>
      {/if}

      {#if translationSettingsLoading}
        <div class="rating-settings-grid">
          {#each Array(4) as _}
            <div class="rating-setting-card skeleton"></div>
          {/each}
        </div>
      {:else if translationSettings}
        <div class="translation-summary-card">
          <div class="translation-summary-main">
            <div>
              <span>Всего</span>
              <strong>
                {formatNumber(translationSettings.coverage?.summary?.translated ?? 0)}
                / {formatNumber(translationSettings.queue?.pending ?? 0)}
              </strong>
              <small>переведено / в очереди</small>
            </div>
            <div>
              <span>Общее покрытие</span>
              <strong>{formatPercent(translationSettings.coverage?.summary?.percent ?? 0)}</strong>
              <small>
                {formatNumber(translationSettings.coverage?.summary?.translated ?? 0)}
                из {formatNumber(translationSettings.coverage?.summary?.target ?? 0)} языковых версий
              </small>
            </div>
          </div>
          <div class="translation-breakdown-list">
            {#each translationBreakdownRows as row (row.key)}
              <div class="translation-breakdown-row">
                <span>{row.label}</span>
                <strong>{formatNumber(row.translated)} / {formatNumber(row.target)}</strong>
                <small>{formatPercent(row.percent)}</small>
              </div>
            {/each}
          </div>
        </div>

        <div class="formula-strip">
          <span>
            Статьи сегодня: {formatNumber(translationSettings.usage?.post_used ?? 0)} / {formatNumber(translationSettings.post_daily_limit)}
          </span>
          <span>
            Комментарии сегодня: {formatNumber(translationSettings.usage?.comment_used ?? 0)} / {formatNumber(translationSettings.comment_daily_limit)}
          </span>
          <span>
            На одну статью: до {formatNumber(translationSettings.post_object_daily_limit)} переводов за 24 часа
          </span>
        </div>

        <div class="rating-settings-grid">
          <label class="rating-setting-card translation-toggle-card">
            <span>Осуществлять перевод</span>
            <div class="translation-toggle-row">
              <input
                id="translation-enabled"
                type="checkbox"
                bind:checked={translationSettings.enabled}
              />
              <span class:enabled={translationSettings.enabled}>
                {translationSettings.enabled ? 'Включено' : 'Выключено'}
              </span>
            </div>
            <small>
              Если выключить, очередь переводов перестанет отправлять материалы в OpenRouter.
            </small>
          </label>

          <label class="rating-setting-card">
            <span>Статей в сутки</span>
            <input
              type="number"
              min="0"
              max="100000"
              step="1"
              bind:value={translationSettings.post_daily_limit}
            />
            <small>Общий дневной лимит автоматических переводов статей.</small>
          </label>

          <label class="rating-setting-card">
            <span>Комментариев в сутки</span>
            <input
              type="number"
              min="0"
              max="100000"
              step="1"
              bind:value={translationSettings.comment_daily_limit}
            />
            <small>Общий дневной лимит автоматических переводов комментариев.</small>
          </label>

          <label class="rating-setting-card">
            <span>Повторов для одной статьи</span>
            <input
              type="number"
              min="0"
              max="100"
              step="1"
              bind:value={translationSettings.post_object_daily_limit}
            />
            <small>Защита от частых правок: одна статья не переводится чаще этого лимита в сутки.</small>
          </label>
        </div>
      {:else}
        <div class="empty-state">Настройки перевода не загружены.</div>
      {/if}
    </section>
  {/if}

  {#if activeTab === 'chat-reports'}
    <section class="chat-reports-section">
      <div class="section-header">
        <div>
          <p class="section-label">Раздел</p>
          <h2>Модерация</h2>
        </div>
        <div class="chat-reports-toolbar">
          <div class="chat-report-filters" aria-label="Фильтр жалоб">
            <button
              type="button"
              class:active={chatReportsFilter === 'open'}
              on:click={() => setChatReportsFilter('open')}
            >
              Новые
            </button>
            <button
              type="button"
              class:active={chatReportsFilter === 'all'}
              on:click={() => setChatReportsFilter('all')}
            >
              Все
            </button>
          </div>
          <button
            class="secondary-button"
            type="button"
            disabled={chatReportsLoading || contentReportsLoading}
            on:click={() => {
              loadContentReports()
              loadChatReports()
            }}
          >
            Обновить
          </button>
        </div>
      </div>

      {#if contentReportsError}
        <div class="notice error">{contentReportsError}</div>
      {/if}
      {#if chatReportsError}
        <div class="notice error">{chatReportsError}</div>
      {/if}
      {#if contentReportsNotice}
        <div class="notice success">{contentReportsNotice}</div>
      {/if}
      {#if chatReportsNotice}
        <div class="notice success">{chatReportsNotice}</div>
      {/if}

      <div class="report-group">
        <div class="report-group-heading">
          <h3>Посты и комментарии</h3>
          <span>{formatNumber(contentReportsTotal)}</span>
        </div>
        {#if contentReportsLoading}
          <div class="chat-reports-list">
            {#each Array(2) as _}
              <div class="chat-report-row skeleton"></div>
            {/each}
          </div>
        {:else if contentReports.length}
          <div class="chat-reports-list">
            {#each contentReports as report (report.id)}
              <article class="chat-report-row">
                <div class="chat-report-header">
                  <div class="chat-report-users">
                    <strong>{report.reason_label || report.reason}</strong>
                    <span>
                      {report.target_type_label || report.target_type} · жалоба от
                      {chatReportUserName(report.reporter)} · {formatDateTime(report.created_at)}
                    </span>
                  </div>
                  <span class={`chat-report-status status-${report.status}`}>
                    {report.status_label || report.status}
                  </span>
                </div>

                <div class="chat-report-message">
                  {#if report.target.title}
                    <strong class="content-report-title">{report.target.title}</strong>
                  {/if}
                  {report.target.body || 'Содержимое не найдено или пустое.'}
                </div>

                <div class="chat-report-footer">
                  <span>
                    {#if report.target.author}
                      Автор: {chatReportUserName(report.target.author)}
                    {/if}
                    {#if report.target.url}
                      · <a href={report.target.url} target="_blank" rel="noopener noreferrer">
                        Открыть {report.target_type === 'comment' ? 'комментарий' : 'пост'}
                      </a>
                    {/if}
                  </span>
                  <div class="chat-report-actions">
                    {#if report.status !== 'reviewed'}
                      <button
                        class="secondary-button"
                        type="button"
                        disabled={savingContentReports[report.id]}
                        on:click={() => updateContentReportStatus(report, 'reviewed')}
                      >
                        Обработано
                      </button>
                    {/if}
                    {#if report.status !== 'dismissed'}
                      <button
                        class="secondary-button danger-button"
                        type="button"
                        disabled={savingContentReports[report.id]}
                        on:click={() => updateContentReportStatus(report, 'dismissed')}
                      >
                        Отклонить
                      </button>
                    {/if}
                  </div>
                </div>
              </article>
            {/each}
          </div>
        {:else}
          <div class="empty-state">Новых жалоб на посты и комментарии нет.</div>
        {/if}
      </div>

      <div class="report-group">
        <div class="report-group-heading">
          <h3>Личные сообщения</h3>
          <span>{formatNumber(chatReportsTotal)}</span>
        </div>
        {#if chatReportsLoading}
          <div class="chat-reports-list">
            {#each Array(2) as _}
              <div class="chat-report-row skeleton"></div>
            {/each}
          </div>
        {:else if chatReports.length}
          <div class="chat-reports-list">
            {#each chatReports as report (report.id)}
              <article class="chat-report-row">
                <div class="chat-report-header">
                  <div class="chat-report-users">
                    <strong>{chatReportUserName(report.reported_user)}</strong>
                    <span>Жалоба от {chatReportUserName(report.reporter)} · {formatDateTime(report.created_at)}</span>
                  </div>
                  <span class={`chat-report-status status-${report.status}`}>
                    {report.status_label || report.status}
                  </span>
                </div>

                <div class="chat-report-message">
                  {report.message?.body || 'Сообщение не найдено или пустое.'}
                </div>

                <div class="chat-report-footer">
                  <span>
                    Чат #{report.chat_id}
                    {#if report.message?.id}
                      · сообщение #{report.message.id}
                    {/if}
                    {#if report.message?.created_at}
                      · {formatDateTime(report.message.created_at)}
                    {/if}
                  </span>
                  <div class="chat-report-actions">
                    {#if report.status !== 'reviewed'}
                      <button
                        class="secondary-button"
                        type="button"
                        disabled={savingChatReports[report.id]}
                        on:click={() => updateChatReportStatus(report, 'reviewed')}
                      >
                        Обработано
                      </button>
                    {/if}
                    {#if report.status !== 'dismissed'}
                      <button
                        class="secondary-button danger-button"
                        type="button"
                        disabled={savingChatReports[report.id]}
                        on:click={() => updateChatReportStatus(report, 'dismissed')}
                      >
                        Отклонить
                      </button>
                    {/if}
                  </div>
                </div>
              </article>
            {/each}
          </div>
        {:else}
          <div class="empty-state">Новых жалоб на личные сообщения нет.</div>
        {/if}
      </div>
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
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .moderator-tabs button.active {
    border-bottom-color: rgb(37 99 235);
    color: rgb(15 23 42);
    font-weight: 600;
  }

  .tab-badge {
    min-width: 20px;
    height: 20px;
    border-radius: 999px;
    display: inline-grid;
    place-items: center;
    padding: 0 6px;
    background: rgb(220 38 38);
    color: white;
    font-size: 12px;
    line-height: 1;
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
  .recent-comuns-section,
  .view-settings-section,
  .rating-settings-section,
  .translation-settings-section,
  .chat-reports-section,
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

  .recent-comuns-list {
    display: grid;
  }

  .recent-comun-row {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr) minmax(150px, auto);
    align-items: center;
    gap: 14px;
    min-height: 76px;
    padding: 13px 0;
    border-top: 1px solid rgb(226 232 240);
  }

  .recent-comun-row:first-child {
    border-top: 0;
  }

  .recent-comun-info {
    min-width: 0;
  }

  .recent-comun-info a {
    color: rgb(15 23 42);
    font-size: 15px;
    font-weight: 650;
  }

  .recent-comun-info a:hover {
    color: rgb(2 132 199);
  }

  .recent-comun-info p {
    display: -webkit-box;
    margin: 4px 0 0;
    overflow: hidden;
    color: rgb(100 116 139);
    font-size: 13px;
    line-height: 1.4;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .recent-comun-row time,
  .recent-comuns-count {
    color: rgb(100 116 139);
    font-size: 13px;
  }

  .recent-comun-row time {
    text-align: right;
    white-space: nowrap;
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

  .view-defaults-card {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: rgb(248 250 252);
    padding: 14px;
    display: grid;
    grid-template-columns: minmax(260px, 1fr) minmax(110px, 160px) minmax(110px, 160px) auto;
    gap: 12px;
    align-items: center;
    margin-bottom: 14px;
  }

  .view-defaults-info {
    min-width: 0;
    display: grid;
    gap: 5px;
  }

  .view-defaults-info strong {
    color: rgb(15 23 42);
    font-size: 15px;
    line-height: 1.25;
  }

  .view-defaults-info span {
    color: rgb(100 116 139);
    font-size: 12px;
    line-height: 1.35;
  }

  .static-pages-list {
    display: grid;
    gap: 10px;
  }

  .chat-reports-toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .chat-report-filters {
    min-height: 38px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    display: inline-flex;
    overflow: hidden;
    background: white;
  }

  .chat-report-filters button {
    border: 0;
    border-right: 1px solid rgb(226 232 240);
    background: transparent;
    padding: 0 12px;
    color: rgb(71 85 105);
    cursor: pointer;
  }

  .chat-report-filters button:last-child {
    border-right: 0;
  }

  .chat-report-filters button.active {
    background: rgb(239 246 255);
    color: rgb(37 99 235);
    font-weight: 600;
  }

  .chat-reports-list {
    display: grid;
    gap: 10px;
  }

  .report-group {
    display: grid;
    gap: 10px;
    padding-top: 18px;
    border-top: 1px solid rgb(226 232 240);
  }

  .report-group + .report-group {
    margin-top: 22px;
  }

  .report-group-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
  }

  .report-group-heading h3 {
    color: rgb(15 23 42);
    font-size: 17px;
    font-weight: 650;
  }

  .report-group-heading span {
    color: rgb(100 116 139);
    font-size: 13px;
  }

  .chat-report-row {
    min-height: 148px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    padding: 14px;
    display: grid;
    gap: 12px;
    background: rgb(248 250 252);
  }

  .chat-report-header,
  .chat-report-footer {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .chat-report-users {
    min-width: 0;
    display: grid;
    gap: 4px;
  }

  .chat-report-users strong {
    color: rgb(15 23 42);
    font-size: 15px;
    line-height: 1.25;
  }

  .chat-report-users span,
  .chat-report-footer span,
  .chat-reports-total {
    color: rgb(100 116 139);
    font-size: 13px;
    line-height: 1.35;
  }

  .chat-report-status {
    border-radius: 999px;
    padding: 5px 9px;
    color: rgb(71 85 105);
    background: white;
    font-size: 12px;
    white-space: nowrap;
  }

  .chat-report-status.status-open {
    color: rgb(153 27 27);
    background: rgb(254 226 226);
  }

  .chat-report-status.status-reviewed {
    color: rgb(22 101 52);
    background: rgb(220 252 231);
  }

  .chat-report-status.status-dismissed {
    color: rgb(71 85 105);
    background: rgb(226 232 240);
  }

  .chat-report-message {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: white;
    padding: 12px;
    color: rgb(15 23 42);
    font-size: 14px;
    line-height: 1.45;
    white-space: pre-wrap;
    word-break: break-word;
  }

  .content-report-title {
    display: block;
    margin-bottom: 6px;
  }

  .chat-report-footer a {
    color: rgb(2 132 199);
    font-weight: 600;
  }

  .chat-report-actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 8px;
  }

  .danger-button {
    border-color: rgb(254 202 202);
    color: rgb(185 28 28);
  }

  .danger-button:hover {
    background: rgb(254 242 242);
  }

  .chat-reports-total {
    padding-top: 2px;
    text-align: right;
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

  .translation-summary-card {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: rgb(248 250 252);
    padding: 16px;
    display: grid;
    gap: 14px;
    margin-bottom: 14px;
  }

  .translation-summary-main {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .translation-summary-main > div {
    display: grid;
    gap: 5px;
    min-width: 0;
  }

  .translation-summary-main span {
    color: rgb(71 85 105);
    font-size: 13px;
    font-weight: 600;
  }

  .translation-summary-main strong {
    color: rgb(15 23 42);
    font-size: 24px;
    line-height: 1.15;
  }

  .translation-summary-main small {
    color: rgb(100 116 139);
    font-size: 12px;
    line-height: 1.35;
  }

  .translation-breakdown-list {
    display: grid;
    gap: 6px;
    border-top: 1px solid rgb(226 232 240);
    padding-top: 12px;
  }

  .translation-breakdown-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto auto;
    gap: 10px;
    align-items: center;
    color: rgb(100 116 139);
    font-size: 12px;
  }

  .translation-breakdown-row span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .translation-breakdown-row strong {
    color: rgb(51 65 85);
    font-size: 12px;
    font-weight: 600;
  }

  .translation-breakdown-row small {
    color: rgb(100 116 139);
    font-size: 12px;
    min-width: 42px;
    text-align: right;
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

  .translation-toggle-card {
    min-height: 132px;
  }

  .translation-toggle-row {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .translation-toggle-row input {
    width: 44px;
    height: 24px;
    flex: 0 0 auto;
    accent-color: rgb(37 99 235);
  }

  .translation-toggle-row span {
    color: rgb(185 28 28);
    font-size: 14px;
    font-weight: 600;
  }

  .translation-toggle-row span.enabled {
    color: rgb(22 101 52);
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
  :global(.dark) .recent-comun-info p,
  :global(.dark) .recent-comun-row time,
  :global(.dark) .recent-comuns-count,
  :global(.dark) .report-group-heading span,
  :global(.dark) .chat-report-users span,
  :global(.dark) .chat-report-footer span,
  :global(.dark) .chat-reports-total,
  :global(.dark) .view-cell span,
  :global(.dark) .view-defaults-info span,
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
  :global(.dark) .view-defaults-info strong,
  :global(.dark) .chat-report-users strong,
  :global(.dark) .chat-report-message,
  :global(.dark) .static-page-info strong,
  :global(.dark) .recent-comun-info a,
  :global(.dark) .view-cell strong {
    color: white;
  }

  :global(.dark) .report-group-heading h3,
  :global(.dark) .content-report-title {
    color: white;
  }

  :global(.dark) .report-group {
    border-color: rgb(63 63 70);
  }

  :global(.dark) .metric-card,
  :global(.dark) .analytics-section,
  :global(.dark) .recent-comuns-section,
  :global(.dark) .view-settings-section,
  :global(.dark) .rating-settings-section,
  :global(.dark) .translation-settings-section,
  :global(.dark) .chat-reports-section,
  :global(.dark) .static-pages-section,
  :global(.dark) .view-defaults-card,
  :global(.dark) .view-settings-row,
  :global(.dark) .chat-report-row,
  :global(.dark) .chat-report-message,
  :global(.dark) .static-page-row,
  :global(.dark) .rating-setting-card,
  :global(.dark) .preset-group,
  :global(.dark) .chat-report-filters,
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

  :global(.dark) .recent-comun-row {
    border-color: rgb(63 63 70);
  }

  :global(.dark) .preset-group button {
    border-color: rgb(63 63 70);
    color: rgb(228 228 231);
  }

  :global(.dark) .chat-report-filters button {
    border-color: rgb(63 63 70);
    color: rgb(228 228 231);
  }

  :global(.dark) .chat-report-filters button.active {
    background: rgb(30 58 138 / 0.35);
    color: rgb(147 197 253);
  }

  :global(.dark) .chat-report-status {
    background: rgb(39 39 42);
    color: rgb(212 212 216);
  }

  :global(.dark) .chat-report-status.status-open {
    background: rgb(127 29 29 / 0.45);
    color: rgb(252 165 165);
  }

  :global(.dark) .chat-report-status.status-reviewed {
    background: rgb(20 83 45 / 0.45);
    color: rgb(134 239 172);
  }

  :global(.dark) .chat-report-status.status-dismissed {
    background: rgb(63 63 70);
    color: rgb(212 212 216);
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

  :global(.dark) .translation-summary-card {
    border-color: rgb(63 63 70);
    background: rgb(39 39 42);
  }

  :global(.dark) .translation-summary-main span,
  :global(.dark) .translation-summary-main small,
  :global(.dark) .translation-breakdown-row,
  :global(.dark) .translation-breakdown-row small {
    color: rgb(161 161 170);
  }

  :global(.dark) .translation-summary-main strong,
  :global(.dark) .translation-breakdown-row strong {
    color: rgb(244 244 245);
  }

  :global(.dark) .translation-breakdown-list {
    border-color: rgb(63 63 70);
  }

  :global(.dark) .translation-toggle-row span {
    color: rgb(252 165 165);
  }

  :global(.dark) .translation-toggle-row span.enabled {
    color: rgb(134 239 172);
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

    .chat-reports-toolbar,
    .chat-report-header,
    .chat-report-footer {
      align-items: stretch;
      flex-direction: column;
    }

    .chat-report-actions {
      justify-content: flex-start;
    }

    .view-settings-search input {
      width: 100%;
    }

    .view-settings-row {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .view-defaults-card {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .view-defaults-info,
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

    .translation-summary-main,
    .translation-breakdown-row {
      grid-template-columns: 1fr;
    }

    .translation-breakdown-row small {
      text-align: left;
    }

    .recent-comun-row {
      grid-template-columns: 48px minmax(0, 1fr);
    }

    .recent-comun-row time {
      grid-column: 2;
      text-align: left;
    }

    .view-settings-search,
    .view-settings-row {
      grid-template-columns: 1fr;
    }

    .view-settings-search,
    .chat-reports-toolbar {
      display: grid;
    }
  }
</style>
