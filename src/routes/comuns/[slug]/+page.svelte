<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { onDestroy, onMount } from 'svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import ComunRoadmapModal from '$lib/components/comuns/ComunRoadmapModal.svelte'
  import WelcomePostDropdown from '$lib/components/comuns/WelcomePostDropdown.svelte'
  import FeedPostsList from '$lib/components/feeds/FeedPostsList.svelte'
  import {
    buildBackendPostPath,
    buildComunGlossaryPath,
    buildComunKnowledgeBasePath,
    buildComunRoadmapPath,
    buildComunPostsUrl,
    buildComunSettingsOptionsUrl,
    buildComunUrl,
    type BackendComun,
    type BackendComunCategory,
    type BackendPost,
  } from '$lib/api/backend'
  import { createSiteChat, refreshSiteUser, siteToken, siteUser, uploadSiteImage } from '$lib/siteAuth'
  import { env } from '$env/dynamic/public'
  import { userSettings } from '$lib/settings'
  import { deserializeEditorModel } from '$lib/util'
  import { brandNameForLanguage } from '$lib/brand'
  import { locale } from '$lib/translations'
  import { ChatBubbleLeftRight, ChevronDown, GlobeAlt, Icon } from 'svelte-hero-icons'

  export let data

  const pageSize = data.pageSize ?? 10
  let comun: BackendComun | null = data.comun ?? null
  let posts: BackendPost[] = data.posts ?? []
  let selectedCategorySlug = data.selectedCategory?.slug ?? data.initialCategorySlug ?? ''
  const normalizeCategorySlugList = (values: unknown): string[] => {
    if (!Array.isArray(values)) return []
    const seen = new Set<string>()
    const result: string[] = []
    for (const value of values) {
      const slug = String(value ?? '').trim()
      if (slug && !seen.has(slug)) {
        seen.add(slug)
        result.push(slug)
      }
    }
    return result
  }
  let selectedCategorySlugs = normalizeCategorySlugList(
    data.selectedCategorySlugs ??
      (selectedCategorySlug ? [selectedCategorySlug] : [])
  )
  let categoryFilterExplicit = Boolean(data.categoryFilterExplicit ?? selectedCategorySlug)
  let lastCategoryFilterDataSignature = ''
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let loadingCategory = false
  let lastPostsRef = data.posts
  let lastComunRef = data.comun
  const scrollThreshold = 400
  let scrollRaf: number | null = null
  let settingsOpen = false
  let settingsLoading = false
  let settingsSaving = false
  let settingsLogoUploading = false
  let deleteComunOpen = false
  let deleteComunSaving = false
  let settingsError = ''
  let settingsUserSearch = ''
  let settingsDraft: BackendComun | null = null
  let settingsLogoInput: HTMLInputElement | null = null
  let autoSettingsOpenHandled = false
  let wantsSettingsOpenFromUrl = false
  let settingsCategoryOptions: BackendComunCategory[] = []
  let categoryFilterOpen = false
  let categoryFilterElement: HTMLDivElement | null = null
  let comunHeaderDetailsOpen = false
  let lastComunHeaderDetailsSlug = ''
  type ComunUserOption = { id: number; username: string; display_name?: string | null }
  let settingsUserOptions: ComunUserOption[] = []
  let settingsUserSearchTimer: ReturnType<typeof setTimeout> | null = null
  let settingsUserSearchToken = 0
  let lastSettingsUserSearch = ''
  const COMUN_SUGGESTIONS_CATEGORY_SLUGS = new Set(['feature-ideas', 'suggestions'])
  const ROADMAP_PREVIEW_LIMIT = 4
  const ROADMAP_PREVIEW_FETCH_LIMIT = 8

  const patchSettingsDraft = (patch: Partial<BackendComun>) => {
    if (!settingsDraft) return
    settingsDraft = { ...settingsDraft, ...patch }
  }

  type ComunCategoryCount = {
    category_id?: number | null
    slug?: string | null
    count?: number | null
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
    emptyState: string
  }

  type RoadmapStage = RoadmapStageDefinition & {
    category: BackendComunCategory
    count: number
  }

  type RoadmapPreviewState = {
    loading: boolean
    error: string | null
    posts: BackendPost[]
  }
  type ComunModeratorMember = {
    id?: number | null
    username?: string | null
    display_name?: string | null
    is_deleted?: boolean
    isCreator?: boolean
  }

  const ROADMAP_STAGE_DEFINITIONS: RoadmapStageDefinition[] = [
    {
      key: 'suggestions',
      label: 'Идеи от пользователей',
      shortLabel: 'Идеи',
      description: 'Сюда попадают предложения и запросы на новые возможности.',
      exactSlugs: ['feature-ideas', 'suggestions', 'ideas', 'feature-requests', 'requests'],
      slugKeywords: ['idea', 'suggest', 'request', 'feedback', 'feature'],
      nameKeywords: ['иде', 'предлож', 'запрос', 'фидбек', 'улучш'],
      emptyState: 'Пока нет новых идей. Можно пригласить пользователей написать первый запрос.',
    },
    {
      key: 'backlog',
      label: 'Беклог',
      shortLabel: 'Беклог',
      description: 'Отобранные идеи, которые команда рассматривает и приоритизирует.',
      exactSlugs: ['backlog'],
      slugKeywords: ['backlog', 'queue'],
      nameKeywords: ['беклог', 'очеред', 'очередь', 'приорит'],
      emptyState: 'Беклог пока пуст. Перенесите сюда лучшие предложения из идей.',
    },
    {
      key: 'planned',
      label: 'Запланировано',
      shortLabel: 'План',
      description: 'Функции и изменения, которые команда собирается сделать дальше.',
      exactSlugs: ['planned', 'plan', 'next', 'up-next', 'next-up'],
      slugKeywords: ['plan', 'planned', 'next', 'up-next', 'queue'],
      nameKeywords: ['план', 'заплан', 'далее', 'следующ'],
      emptyState: 'Пока нет публично запланированных задач.',
    },
    {
      key: 'in_progress',
      label: 'В работе',
      shortLabel: 'В работе',
      description: 'То, что уже взяли в разработку и над чем команда работает прямо сейчас.',
      exactSlugs: ['in-progress', 'in_progress', 'progress', 'doing', 'wip', 'active-work'],
      slugKeywords: ['progress', 'doing', 'wip', 'active', 'work', 'develop'],
      nameKeywords: ['в работе', 'делаем', 'разработ', 'работаем', 'реализ'],
      emptyState: 'Сейчас нет задач в активной разработке.',
    },
    {
      key: 'released',
      label: 'Сделано / релизы',
      shortLabel: 'Готово',
      description: 'Что уже доставлено пользователям и можно обсуждать качество реализации.',
      exactSlugs: ['done', 'completed', 'shipped', 'released', 'changelog'],
      slugKeywords: ['done', 'complete', 'ship', 'release', 'changelog', 'live'],
      nameKeywords: ['сделан', 'готов', 'релиз', 'выпущ', 'готово'],
      emptyState: 'В этом столбце пока нет завершённых изменений.',
    },
  ]

  let categoryCounts: ComunCategoryCount[] = Array.isArray(data?.categoryCounts) ? data.categoryCounts : []
  let totalPostsCount: number | null =
    typeof data?.totalCount === 'number' ? Number(data.totalCount) : null
  let uncategorizedPostsCount: number =
    typeof data?.uncategorizedCount === 'number' ? Math.max(Number(data.uncategorizedCount), 0) : 0
  let lastCategoryCountsRef = data?.categoryCounts
  let lastTotalCountRef = data?.totalCount
  let lastUncategorizedCountRef = data?.uncategorizedCount
  let roadmapPreviewStates: Partial<Record<RoadmapStageKey, RoadmapPreviewState>> = {}
  let lastRoadmapPreviewSignature = ''
  let roadmapPreviewRequestSeq = 0
  let publicRoadmapModalOpen = false
  let publicRoadmapBodyOverflowBeforeOpen: string | null = null
  let openingModeratorChatId: number | null = null
  let moderatorMenuOpen = false
  let moderatorMenuCloseTimer: ReturnType<typeof setTimeout> | null = null

  $: if (data?.posts && data.posts !== lastPostsRef) {
    lastPostsRef = data.posts
    posts = data.posts ?? []
    hasMore = posts.length === pageSize
    loadingMore = false
  }
  $: if (data?.comun && data.comun !== lastComunRef) {
    lastComunRef = data.comun
    comun = data.comun ?? null
  }
  $: if ((comun?.slug ?? '') !== lastComunHeaderDetailsSlug) {
    lastComunHeaderDetailsSlug = comun?.slug ?? ''
    comunHeaderDetailsOpen = false
  }
  $: incomingCategoryFilterSlugs = normalizeCategorySlugList(
    data?.selectedCategorySlugs ??
      (data?.selectedCategory?.slug
        ? [data.selectedCategory.slug]
        : data?.initialCategorySlug
          ? [data.initialCategorySlug]
          : [])
  )
  $: incomingCategoryFilterExplicit = Boolean(
    data?.categoryFilterExplicit ??
      data?.selectedCategory?.slug ??
      data?.initialCategorySlug
  )
  $: incomingCategoryFilterSignature = `${incomingCategoryFilterExplicit ? '1' : '0'}:${incomingCategoryFilterSlugs.join(',')}`
  $: if (incomingCategoryFilterSignature !== lastCategoryFilterDataSignature) {
    lastCategoryFilterDataSignature = incomingCategoryFilterSignature
    categoryFilterExplicit = incomingCategoryFilterExplicit
    selectedCategorySlugs = incomingCategoryFilterSlugs
    selectedCategorySlug = incomingCategoryFilterSlugs.length === 1 ? incomingCategoryFilterSlugs[0] : ''
  }
  $: if (Array.isArray(data?.categoryCounts) && data.categoryCounts !== lastCategoryCountsRef) {
    lastCategoryCountsRef = data.categoryCounts
    categoryCounts = data.categoryCounts
  }
  $: if (data && data.totalCount !== lastTotalCountRef) {
    lastTotalCountRef = data.totalCount
    totalPostsCount = typeof data.totalCount === 'number' ? Number(data.totalCount) : totalPostsCount
  }
  $: if (data && data.uncategorizedCount !== lastUncategorizedCountRef) {
    lastUncategorizedCountRef = data.uncategorizedCount
    uncategorizedPostsCount =
      typeof data.uncategorizedCount === 'number'
        ? Math.max(Number(data.uncategorizedCount), 0)
        : uncategorizedPostsCount
  }

  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  const authorKey = (backendPost: { author?: { username?: string } }) =>
    (backendPost.author?.username ?? '').trim().toLowerCase()
  const isAuthorVisible = (backendPost: { author?: { username?: string } }) => {
    const key = authorKey(backendPost)
    if (!key) return true
    return !hiddenAuthorKeys.has(key)
  }
  $: visiblePosts = posts.filter(isAuthorVisible)

  const isModerator = () => Boolean(comun?.can_moderate && $siteToken)
  const canManageComunModerators = () => Boolean(comun?.can_manage_moderators && $siteToken)
  const canDeleteComun = () => Boolean(comun?.can_manage_moderators && $siteToken)
  const isComunCreator = () =>
    Boolean($siteToken && $siteUser?.id && comun?.creator?.id && $siteUser.id === comun.creator.id)
  const applyPostCategory = (
    post: BackendPost,
    category: BackendComunCategory | null,
    categoryId: number | null
  ): BackendPost => ({
    ...post,
    comun_category: category,
    comun_category_id: categoryId,
  })
  const withCurrentComunContext = (post: BackendPost): BackendPost => ({
    ...post,
    comun_slug: post.comun_slug ?? comun?.slug ?? null,
    comun: {
      ...(post.comun ?? {
        id: comun?.id ?? 0,
        name: comun?.name ?? '',
        slug: comun?.slug ?? '',
        logo_url: comun?.logo_url ?? null,
      }),
      knowledge_base_enabled: Boolean(comun?.knowledge_base_enabled),
      can_moderate: Boolean(comun?.can_moderate),
    },
  })
  const handlePostCategoryChange = (
    event: CustomEvent<{
      postId: number
      category: BackendComunCategory | null
      categoryId: number | null
    }>
  ) => {
    const { postId, category, categoryId } = event.detail
    posts = posts
      .map((post) => (post.id === postId ? applyPostCategory(post, category, categoryId) : post))
      .filter((post) => !categoryFilterExplicit || selectedCategorySlugSet.has(post.comun_category?.slug ?? ''))
    if (comun?.welcome_post?.id === postId) {
      comun = {
        ...comun,
        welcome_post: applyPostCategory(comun.welcome_post, category, categoryId),
      }
    }
  }
  const handleWelcomePostPinned = (
    event: CustomEvent<{
      postId: number
      comunSlug: string
    }>
  ) => {
    if (!comun?.slug || event.detail.comunSlug !== comun.slug) return
    const postId = Number(event.detail.postId)
    if (!postId) return
    const sourcePost =
      posts.find((post) => post.id === postId) ??
      (comun.welcome_post?.id === postId ? comun.welcome_post : null)
    if (!sourcePost) return
    comun = {
      ...comun,
      welcome_post_id: postId,
      welcome_post_ref: String(postId),
      welcome_post: withCurrentComunContext(sourcePost),
    }
  }
  const handleWelcomePostUnpinned = (
    event: CustomEvent<{
      postId: number
      comunSlug: string
    }>
  ) => {
    if (!comun?.slug || event.detail.comunSlug !== comun.slug) return
    const postId = Number(event.detail.postId)
    if (!postId || currentWelcomePostId !== postId) return
    comun = {
      ...comun,
      welcome_post_id: null,
      welcome_post_ref: '',
      welcome_post: null,
    }
  }
  const formatRatingValue = (value?: number | null) => {
    const normalized = Math.max(Number(value ?? 0) || 0, 0)
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(normalized)
  }

  const formatComunCount = (value?: number | null) =>
    new Intl.NumberFormat('ru-RU').format(Math.max(Number(value ?? 0) || 0, 0))

  $: siteTitle = brandNameForLanguage($locale)
  $: comunName = comun?.name || 'Сообщество'
  $: minimumAuthorRatingToPost = Math.max(Number(comun?.minimum_author_rating_to_post ?? 0) || 0, 0)
  $: comunCategories = comun?.categories ?? []
  $: feedPosts = visiblePosts.map(withCurrentComunContext)
  $: welcomeFeedPosts = comun?.welcome_post ? [withCurrentComunContext(comun.welcome_post)] : []
  $: currentWelcomePostId = comun?.welcome_post_id ?? comun?.welcome_post?.id ?? null
  $: hasComunCategories = comunCategories.length > 0
  $: hasUserWritableComunCategory = comunCategories.some(
    (category) => !Boolean(category.only_moderators_can_post)
  )
  $: canShowComunPostButton = Boolean(comun?.slug && hasUserWritableComunCategory)
  $: myFeedComunSlugs = ($userSettings.myFeedComuns ?? []).map((slug) => slug.trim()).filter(Boolean)
  $: myFeedComunCategoryMap = $userSettings.myFeedComunCategories ?? {}
  $: currentComunSlug = (comun?.slug ?? '').trim()
  $: hasComunHeaderDetails = Boolean(
    (comun?.product_description ?? '').trim() ||
      (comun?.target_audience ?? '').trim() ||
      (comun?.rules_text ?? '').trim()
  )
  $: isSubscribedToComun = !!currentComunSlug && myFeedComunSlugs.includes(currentComunSlug)
  $: initialComunSubscribed = Boolean(comun?.is_subscribed)
  $: baseComunSubscribersCount = Math.max(Number(comun?.subscribers_count ?? 0) || 0, 0)
  $: comunSubscribersCount = Math.max(
    0,
    baseComunSubscribersCount +
      (isSubscribedToComun && !initialComunSubscribed ? 1 : 0) -
      (!isSubscribedToComun && initialComunSubscribed ? 1 : 0)
  )
  $: comunAuthorsCount = Math.max(Number(comun?.authors_count ?? 0) || 0, 0)
  $: comunCreator = comun?.creator ?? null
  $: comunModeratorList = (() => {
    const seen = new Set<number>()
    const result: ComunModeratorMember[] = []
    if (comunCreator?.id) {
      seen.add(comunCreator.id)
      result.push({ ...comunCreator, isCreator: true })
    } else if (comunCreator?.username || comunCreator?.display_name) {
      result.push({ ...comunCreator, isCreator: true })
    }
    for (const moderator of comun?.moderators ?? []) {
      if (moderator?.id && seen.has(moderator.id)) continue
      if (moderator?.id) seen.add(moderator.id)
      result.push({
        id: moderator.id,
        username: moderator.username,
        display_name: moderator.display_name,
        is_deleted: moderator.is_deleted,
        isCreator: comunCreator?.id === moderator.id,
      })
    }
    return result
  })()
  $: comunModeratorsCount = Math.max(
    Number(comun?.moderators_count ?? comunModeratorList.length) || 0,
    0
  )
  $: comunCategorySlugs = comunCategories.map((category) => category.slug).filter(Boolean)
  $: selectedCategorySlugSet = new Set<string>(
    categoryFilterExplicit ? selectedCategorySlugs : comunCategorySlugs
  )
  $: categoryFilterSelectedCount = categoryFilterExplicit
    ? selectedCategorySlugs.filter((slug) => comunCategorySlugs.includes(slug)).length
    : comunCategorySlugs.length
  $: categoryFilterAllSelected =
    !categoryFilterExplicit || categoryFilterSelectedCount === comunCategorySlugs.length
  $: categoryFilterLabel = categoryFilterAllSelected
    ? 'Все категории'
    : categoryFilterSelectedCount
      ? `Все категории (${categoryFilterSelectedCount}/${comunCategorySlugs.length})`
      : 'Все категории (0)'
  $: hasExplicitComunCategorySelection =
    !!currentComunSlug && Object.prototype.hasOwnProperty.call(myFeedComunCategoryMap, currentComunSlug)
  $: subscribedComunCategorySlugs = new Set<string>(
    isSubscribedToComun
      ? (
          hasExplicitComunCategorySelection
            ? myFeedComunCategoryMap[currentComunSlug] ?? []
            : comunCategorySlugs
        ).filter((slug) => comunCategorySlugs.includes(slug))
      : []
  )
  let subscriptionCategoriesOpen = false
  $: title = `${comunName} — ${siteTitle}`
  $: description =
    comun?.product_description || `Посты и обсуждения продукта «${comunName}» на ${siteTitle}.`
  $: comunWebsiteUrl = externalUrl(comun?.website_url)
  $: comunGlossaryPath = comun?.slug ? buildComunGlossaryPath(comun.slug) : '/comuns'
  $: comunKnowledgeBasePath = comun?.slug ? buildComunKnowledgeBasePath(comun.slug) : '/comuns'
  $: comunRoadmapPath = comun?.slug ? buildComunRoadmapPath(comun.slug) : '/comuns'
  $: canonicalPath = (() => {
    const params = new URLSearchParams()
    if (categoryFilterExplicit) {
      params.set('categories', selectedCategorySlugs.join(','))
    }
    const query = params.toString()
    return `${$page.url.pathname}${query ? `?${query}` : ''}`
  })()
  $: canonicalUrl = new URL(
    canonicalPath,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
  $: roadmapEnabled = Boolean(comun?.roadmap_enabled ?? false)
  $: if (browser) {
    if (publicRoadmapModalOpen) {
      if (publicRoadmapBodyOverflowBeforeOpen === null) {
        publicRoadmapBodyOverflowBeforeOpen = document.body.style.overflow
        document.body.style.overflow = 'hidden'
      }
    } else if (publicRoadmapBodyOverflowBeforeOpen !== null) {
      document.body.style.overflow = publicRoadmapBodyOverflowBeforeOpen
      publicRoadmapBodyOverflowBeforeOpen = null
    }
  }

  const cloneComun = (value: BackendComun | null): BackendComun | null =>
    value ? JSON.parse(JSON.stringify(value)) : null

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

  const externalUrl = (value?: string | null) => {
    const raw = (value ?? '').trim()
    if (!raw) return ''
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) return raw
    if (raw.startsWith('//')) return `https:${raw}`
    return `https://${raw.replace(/^\/+/, '')}`
  }

  const openPublicRoadmapModal = () => {
    if (!comun?.slug) return
    publicRoadmapModalOpen = true
  }

  const closePublicRoadmapModal = () => {
    publicRoadmapModalOpen = false
  }

  const openComunPostEditor = () => {
    if (!comun?.slug) return
    goto(`/account/new-post?comun=${encodeURIComponent(comun.slug)}`)
  }

  const onWindowKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape' && publicRoadmapModalOpen) {
      closePublicRoadmapModal()
    }
    if (event.key === 'Escape' && categoryFilterOpen) {
      categoryFilterOpen = false
    }
  }

  const normalizeIds = (values: Array<number | null | undefined>) =>
    Array.from(new Set(values.filter((value): value is number => Number.isFinite(value as number) && Number(value) > 0).map(Number))).sort((a, b) => a - b)

  const comunModeratorIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.moderator_ids as number[] | undefined) ??
        (value?.moderators ?? []).map((moderator) => moderator.id ?? 0)) as number[]
    )

  const comunCategoryIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.category_ids as number[] | undefined) ??
        (value?.categories ?? []).map((category) => category.id ?? 0)) as number[]
    )

  const settingsComparable = (value: BackendComun | null) =>
    JSON.stringify({
      name: (value?.name ?? '').trim(),
      website_url: (value?.website_url ?? '').trim(),
      logo_url: (value?.logo_url ?? '').trim(),
      product_description: (value?.product_description ?? '').trim(),
      rules_text: (value?.rules_text ?? '').trim(),
      target_audience: (value?.target_audience ?? '').trim(),
      minimum_author_rating_to_post: Math.max(
        Number(value?.minimum_author_rating_to_post ?? 0) || 0,
        0
      ),
      only_moderators_can_post: Boolean(value?.only_moderators_can_post),
      hide_from_home: Boolean(value?.hide_from_home),
      category_ids: comunCategoryIds(value),
      moderator_ids: comunModeratorIds(value),
      welcome_post_ref: String(value?.welcome_post_ref ?? value?.welcome_post_id ?? '').trim(),
    })

  const comunWelcomePostRef = (value: BackendComun | null) =>
    String(value?.welcome_post_ref ?? value?.welcome_post_id ?? '').trim()

  const userDisplayName = (user?: { username?: string | null; display_name?: string | null } | null) => {
    const displayName = (user?.display_name ?? '').trim()
    if (displayName) return displayName
    const username = (user?.username ?? '').trim()
    return username ? `@${username}` : 'Пользователь'
  }

  const openModeratorChat = async (moderator: ComunModeratorMember) => {
    const moderatorId = Number(moderator?.id ?? 0)
    if (!moderatorId || moderator.is_deleted || openingModeratorChatId) return
    if ($siteUser?.id && Number($siteUser.id) === moderatorId) return
    if (!$siteToken) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      await goto(`/account?next=${next}`)
      return
    }
    openingModeratorChatId = moderatorId
    try {
      const chat = await createSiteChat(moderatorId)
      await goto(`/chats/${chat.id}`)
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Не удалось открыть чат',
        type: 'error',
      })
    } finally {
      openingModeratorChatId = null
    }
  }

  const clearModeratorMenuCloseTimer = () => {
    if (!moderatorMenuCloseTimer) return
    clearTimeout(moderatorMenuCloseTimer)
    moderatorMenuCloseTimer = null
  }

  const openModeratorMenu = () => {
    if (!comunModeratorList.length) return
    clearModeratorMenuCloseTimer()
    moderatorMenuOpen = true
  }

  const closeModeratorMenuWithDelay = () => {
    clearModeratorMenuCloseTimer()
    moderatorMenuCloseTimer = setTimeout(() => {
      moderatorMenuOpen = false
      moderatorMenuCloseTimer = null
    }, 450)
  }

  const isSuggestionsComunCategory = (category?: BackendComunCategory | null) =>
    Boolean(category?.slug && COMUN_SUGGESTIONS_CATEGORY_SLUGS.has(category.slug))

  const normalizeRoadmapToken = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/[_\s]+/g, '-')
      .replace(/-+/g, '-')
      .trim()

  const normalizeRoadmapText = (value?: string | null) =>
    (value ?? '')
      .toLowerCase()
      .replace(/\s+/g, ' ')
      .trim()

  const scoreRoadmapCategoryCandidate = (
    stage: RoadmapStageDefinition,
    category: BackendComunCategory
  ): number => {
    const slug = normalizeRoadmapToken(category.slug)
    const name = normalizeRoadmapText(category.name)
    if (!slug && !name) return 0
    if (stage.exactSlugs.includes(slug)) return 100
    if (stage.key === 'suggestions' && COMUN_SUGGESTIONS_CATEGORY_SLUGS.has(slug)) return 95
    let score = 0
    if (stage.slugKeywords.some((keyword) => slug.includes(keyword))) score = Math.max(score, 70)
    if (stage.nameKeywords.some((keyword) => name.includes(keyword))) score = Math.max(score, 60)
    return score
  }

  const buildRoadmapStages = (
    categories: BackendComunCategory[],
    countById: Map<number, number>
  ): RoadmapStage[] => {
    const usedCategoryIds = new Set<number>()
    const nextStages: RoadmapStage[] = []
    for (const stage of ROADMAP_STAGE_DEFINITIONS) {
      const candidates = categories
        .filter((category) => !usedCategoryIds.has(category.id))
        .map((category) => ({
          category,
          score: scoreRoadmapCategoryCandidate(stage, category),
        }))
        .filter((entry) => entry.score > 0)
        .sort((a, b) => {
          if (b.score !== a.score) return b.score - a.score
          const countDiff = (countById.get(b.category.id) ?? 0) - (countById.get(a.category.id) ?? 0)
          if (countDiff !== 0) return countDiff
          const sortDiff = Number(a.category.sort_order ?? 0) - Number(b.category.sort_order ?? 0)
          if (sortDiff !== 0) return sortDiff
          return a.category.name.localeCompare(b.category.name, 'ru')
        })
      const best = candidates[0]
      if (!best) continue
      usedCategoryIds.add(best.category.id)
      nextStages.push({
        ...stage,
        category: best.category,
        count: Math.max(0, Number(countById.get(best.category.id) ?? 0)),
      })
    }
    return nextStages
  }

  const roadmapStageStyleVars = (stageKey: string) => {
    switch (stageKey as RoadmapStageKey) {
      case 'suggestions':
        return '--roadmap-stage-h: 201; --roadmap-stage-s: 88%; --roadmap-stage-l: 47%;'
      case 'backlog':
        return '--roadmap-stage-h: 262; --roadmap-stage-s: 72%; --roadmap-stage-l: 52%;'
      case 'planned':
        return '--roadmap-stage-h: 34; --roadmap-stage-s: 88%; --roadmap-stage-l: 50%;'
      case 'in_progress':
        return '--roadmap-stage-h: 153; --roadmap-stage-s: 77%; --roadmap-stage-l: 40%;'
      case 'released':
        return '--roadmap-stage-h: 340; --roadmap-stage-s: 78%; --roadmap-stage-l: 52%;'
      default:
        return '--roadmap-stage-h: 220; --roadmap-stage-s: 70%; --roadmap-stage-l: 50%;'
    }
  }

  const roadmapStagePillLabel = (stageKey: RoadmapStageKey) => {
    switch (stageKey) {
      case 'suggestions':
        return 'Собираем идеи'
      case 'backlog':
        return 'Приоритизируем'
      case 'planned':
        return 'Планируем'
      case 'in_progress':
        return 'Делаем'
      case 'released':
        return 'Доставили'
      default:
        return 'Этап'
    }
  }

  const stripRoadmapHtml = (value?: string | null) =>
    (value ?? '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/\s+/g, ' ')
      .trim()

  const normalizeSerializedRoadmapCandidate = (value?: string | null) =>
    (value ?? '').trim().replace(/^[-*•\s]+/, '').trim()

  const looksLikeSerializedRoadmapContent = (value?: string | null) => {
    const trimmed = normalizeSerializedRoadmapCandidate(value)
    if (!trimmed) return false
    if (trimmed.startsWith('{') && trimmed.includes('"blocks"')) return true
    return /^eyJ[0-9A-Za-z+/=]{20,}$/.test(trimmed)
  }

  const collectRoadmapBlockText = (block: any) => {
    const data = block?.data ?? {}
    const chunks: string[] = []
    const pushChunk = (value: unknown) => {
      if (typeof value !== 'string') return
      const normalized = stripRoadmapHtml(value)
      if (normalized) chunks.push(normalized)
    }

    pushChunk(data.text)
    pushChunk(data.caption)
    pushChunk(data.title)
    pushChunk(data.code)
    pushChunk(data.alt)

    if (Array.isArray(data.items)) {
      for (const item of data.items) {
        if (typeof item === 'string') {
          pushChunk(item)
          continue
        }
        if (item && typeof item === 'object') {
          pushChunk((item as { text?: string }).text)
        }
      }
    }

    if (Array.isArray(data.content)) {
      for (const row of data.content) {
        if (!Array.isArray(row)) continue
        for (const cell of row) {
          pushChunk(typeof cell === 'string' ? cell : '')
        }
      }
    }

    return chunks
  }

  const extractRoadmapTextFromSerializedContent = (value?: string | null) => {
    if (!looksLikeSerializedRoadmapContent(value)) return ''
    const parsed = deserializeEditorModel(normalizeSerializedRoadmapCandidate(value))
    const blocks = Array.isArray(parsed?.blocks) ? parsed.blocks : []
    const chunks: string[] = []
    for (const block of blocks) {
      chunks.push(...collectRoadmapBlockText(block))
    }
    return chunks.join(' ').trim()
  }

  const roadmapSnippet = (post: BackendPost, maxLength = 150) => {
    const serializedText = extractRoadmapTextFromSerializedContent(post.content)
    const text = serializedText || stripRoadmapHtml(post.content)
    if (!serializedText && looksLikeSerializedRoadmapContent(post.content)) return ''
    if (!text) return ''
    if (text.length <= maxLength) return text
    return `${text.slice(0, maxLength - 1).trimEnd()}…`
  }

  const roadmapPreviewScore = (post: BackendPost) =>
    Number(post.likes_count ?? 0) * 3 +
    Number(post.comments_count ?? 0) * 4 +
    Number(post.views_count ?? 0) * 0.02

  const sortRoadmapPreviewPosts = (items: BackendPost[]) =>
    [...items]
      .sort((a, b) => {
        const scoreDiff = roadmapPreviewScore(b) - roadmapPreviewScore(a)
        if (scoreDiff !== 0) return scoreDiff
        return String(b.created_at ?? '').localeCompare(String(a.created_at ?? ''))
      })
      .slice(0, ROADMAP_PREVIEW_LIMIT)

  const formatRoadmapDate = (value?: string | null) => {
    if (!value) return ''
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: 'short' }).format(parsed)
  }

  const formatRoadmapCount = (value?: number | null) => {
    const normalized = Math.max(0, Number(value ?? 0) || 0)
    return new Intl.NumberFormat('ru-RU').format(normalized)
  }

  const getRoadmapPreviewState = (stageKey: string): RoadmapPreviewState =>
    roadmapPreviewStates[stageKey as RoadmapStageKey] ?? { loading: false, error: null, posts: [] }

  const openRoadmapSubmitFlow = () => {
    if (!comun?.slug) return
    const suggestionsCategory =
      roadmapStages.find((stage) => stage.key === 'suggestions')?.category ??
      (comun?.categories ?? []).find((category) => isSuggestionsComunCategory(category))
    const target = suggestionsCategory?.slug
      ? `/comuns/${comun.slug}/new-post?category=${encodeURIComponent(suggestionsCategory.slug)}`
      : `/comuns/${comun.slug}/new-post`
    if (isModerator()) {
      goto(target)
      return
    }
    if (!$siteToken) {
      const next = encodeURIComponent(target)
      goto(`/account?next=${next}`)
      return
    }
    goto(target)
  }

  const loadRoadmapPreviews = async () => {
    const slug = (comun?.slug ?? '').trim()
    const stagesSnapshot = roadmapStages
    if (!slug || !stagesSnapshot.length) {
      roadmapPreviewStates = {}
      return
    }

    const requestId = ++roadmapPreviewRequestSeq
    const nextStates: Partial<Record<RoadmapStageKey, RoadmapPreviewState>> = {}
    for (const stage of stagesSnapshot) {
      nextStates[stage.key] = { loading: true, error: null, posts: [] }
    }
    roadmapPreviewStates = nextStates

    try {
      const headers = $siteToken ? { Authorization: `Bearer ${$siteToken}` } : undefined
      const results = await Promise.all(
        stagesSnapshot.map(async (stage) => {
          const url = new URL(
            buildComunPostsUrl(slug, { categorySlug: stage.category.slug }),
            $page.url.origin
          )
          url.searchParams.set('limit', String(ROADMAP_PREVIEW_FETCH_LIMIT))
          url.searchParams.set('offset', '0')
          const response = await fetch(url.toString(), headers ? { headers } : undefined)
          const payload = await response.json().catch(() => ({}))
          if (!response.ok) {
            throw new Error(
              typeof payload?.error === 'string' && payload.error
                ? payload.error
                : 'Не удалось загрузить превью'
            )
          }
          return {
            stageKey: stage.key,
            posts: sortRoadmapPreviewPosts((payload?.posts ?? []) as BackendPost[]),
          }
        })
      )
      if (requestId !== roadmapPreviewRequestSeq) return
      const completedStates: Partial<Record<RoadmapStageKey, RoadmapPreviewState>> = {}
      for (const stage of stagesSnapshot) {
        completedStates[stage.key] = { loading: false, error: null, posts: [] }
      }
      for (const result of results) {
        completedStates[result.stageKey] = {
          loading: false,
          error: null,
          posts: result.posts,
        }
      }
      roadmapPreviewStates = completedStates
    } catch (error) {
      if (requestId !== roadmapPreviewRequestSeq) return
      const failedStates: Partial<Record<RoadmapStageKey, RoadmapPreviewState>> = {}
      for (const stage of stagesSnapshot) {
        failedStates[stage.key] = {
          loading: false,
          error: error instanceof Error ? error.message : 'Ошибка загрузки',
          posts: [],
        }
      }
      roadmapPreviewStates = failedStates
    }
  }

  $: categoryCountById = new Map<number, number>(
    (categoryCounts ?? [])
      .map((row) => [Number(row?.category_id ?? 0), Math.max(0, Number(row?.count ?? 0) || 0)] as const)
      .filter(([categoryId]) => categoryId > 0)
  )
  $: roadmapCategoryIdSet = new Set(
    (Array.isArray(comun?.roadmap_category_ids) ? comun?.roadmap_category_ids ?? [] : [])
      .map((value) => Number(value))
      .filter((value) => Number.isFinite(value) && value > 0)
  )
  $: roadmapSourceCategories = (comun?.categories ?? []).filter((category) =>
    roadmapCategoryIdSet.has(Number(category.id))
  )
  $: roadmapStages = buildRoadmapStages(roadmapSourceCategories, categoryCountById)
  $: roadmapStageSlugSet = new Set(roadmapStages.map((stage) => stage.category.slug))
  $: roadmapHasBacklog = roadmapStages.some((stage) => stage.key === 'backlog')
  $: roadmapCanOpenModal = roadmapEnabled && (roadmapHasBacklog || roadmapStages.length >= 2)
  $: roadmapModalVisible = publicRoadmapModalOpen && roadmapCanOpenModal
  $: roadmapTrackedCount = roadmapStages.reduce((sum, stage) => sum + Math.max(stage.count, 0), 0)
  $: roadmapReleasedCount =
    roadmapStages.find((stage) => stage.key === 'released')?.count ?? 0
  $: roadmapSignature =
    (comun?.slug ?? '').trim() && roadmapStages.length
      ? `${comun?.slug}:${roadmapStages.map((stage) => `${stage.key}:${stage.category.slug}`).join('|')}`
      : ''

  const removeComunFromMyFeed = () => {
    const slug = (comun?.slug ?? '').trim()
    if (!slug) return
    const next = new Set<string>(myFeedComunSlugs)
    next.delete(slug)
    const nextCategoryMap = { ...($userSettings.myFeedComunCategories ?? {}) }
    delete nextCategoryMap[slug]
    $userSettings = {
      ...$userSettings,
      myFeedComuns: Array.from(next),
      myFeedComunCategories: nextCategoryMap,
    }
    subscriptionCategoriesOpen = false
    toast({ content: 'Сообщество убрано из "Моей ленты"' })
  }

  const toggleComunInMyFeed = async () => {
    const slug = (comun?.slug ?? '').trim()
    if (!slug) return
    if (!$siteToken) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    if (isSubscribedToComun) {
      removeComunFromMyFeed()
      return
    }
    const next = new Set<string>(myFeedComunSlugs)
    next.add(slug)
    const nextCategoryMap = { ...($userSettings.myFeedComunCategories ?? {}) }
    $userSettings = {
      ...$userSettings,
      myFeedComuns: Array.from(next),
      myFeedComunCategories: nextCategoryMap,
    }
    subscriptionCategoriesOpen = comunCategorySlugs.length > 0
    toast({ content: 'Посты этого сообщества будут попадать в "Мою ленту"' })
  }

  const toggleComunCategoryInMyFeed = (categorySlug: string) => {
    const slug = (comun?.slug ?? '').trim()
    if (!slug || !categorySlug) return
    const selected = new Set<string>(
      hasExplicitComunCategorySelection
        ? myFeedComunCategoryMap[slug] ?? []
        : comunCategorySlugs
    )
    if (selected.has(categorySlug)) selected.delete(categorySlug)
    else selected.add(categorySlug)
    if (!selected.size) {
      removeComunFromMyFeed()
      return
    }
    const nextComuns = new Set<string>(myFeedComunSlugs)
    nextComuns.add(slug)
    $userSettings = {
      ...$userSettings,
      myFeedComuns: Array.from(nextComuns),
      myFeedComunCategories: {
        ...($userSettings.myFeedComunCategories ?? {}),
        [slug]: Array.from(selected),
      },
    }
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const mergeUsersById = (current: ComunUserOption[], next: ComunUserOption[]) => {
    const byId = new Map<number, ComunUserOption>()
    for (const user of current ?? []) byId.set(user.id, user)
    for (const user of next ?? []) byId.set(user.id, user)
    return Array.from(byId.values()).sort((a, b) =>
      userDisplayName(a).localeCompare(userDisplayName(b), 'ru')
    )
  }

  const loadSettingsUserOptions = async (query: string) => {
    const normalizedQuery = query.trim()
    if (!comun?.slug || !$siteToken || normalizedQuery.length < 2) return
    const token = settingsUserSearchToken + 1
    settingsUserSearchToken = token
    try {
      const response = await fetch(
        buildComunSettingsOptionsUrl(comun.slug, 'users', { q: normalizedQuery, limit: 30 }),
        {
          headers: { Authorization: `Bearer ${$siteToken}` },
          cache: 'no-store',
        }
      )
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || settingsUserSearchToken !== token) return
      settingsUserOptions = mergeUsersById(
        settingsUserOptions,
        Array.isArray(payload?.items) ? payload.items : []
      )
    } catch (error) {
      console.error('Failed to load comun moderator options', error)
    }
  }

  const queueSettingsUserSearch = (query: string) => {
    if (!browser) return
    const normalizedQuery = query.trim()
    if (normalizedQuery.length < 2) return
    const searchKey = normalizedQuery.toLowerCase()
    if (lastSettingsUserSearch === searchKey) return
    lastSettingsUserSearch = searchKey
    if (settingsUserSearchTimer) clearTimeout(settingsUserSearchTimer)
    settingsUserSearchTimer = setTimeout(() => {
      void loadSettingsUserOptions(normalizedQuery)
    }, 250)
  }

  const buildPostsUrl = (offset: number) => {
    if (!comun?.slug) return ''
    const categoryOptions = categoryFilterExplicit
      ? { categorySlugs: selectedCategorySlugs }
      : undefined
    const url = new URL(
      buildComunPostsUrl(comun.slug, categoryOptions),
      $page.url.origin
    )
    url.searchParams.set('limit', String(pageSize))
    url.searchParams.set('offset', String(offset))
    return url.toString()
  }

  const applyPostsPayload = (payload: any, reset = false) => {
    if (payload?.comun) {
      comun = payload.comun
    }
    if (Array.isArray(payload?.category_counts)) {
      categoryCounts = payload.category_counts
    }
    if (typeof payload?.total_count === 'number') {
      totalPostsCount = Math.max(Number(payload.total_count), 0)
    }
    if (typeof payload?.uncategorized_count === 'number') {
      uncategorizedPostsCount = Math.max(Number(payload.uncategorized_count), 0)
    }
    const nextPosts = (payload?.posts ?? []) as BackendPost[]
    if (reset) {
      posts = nextPosts
    } else if (nextPosts.length) {
      posts = [...posts, ...nextPosts]
    }
    hasMore =
      typeof totalPostsCount === 'number'
        ? posts.length < totalPostsCount
        : nextPosts.length === pageSize
  }

  const loadPosts = async (reset = false) => {
    if (loadingMore || loadingCategory) return
    const url = buildPostsUrl(reset ? 0 : posts.length)
    if (!url) return
    if (reset) {
      loadingCategory = true
    } else {
      loadingMore = true
    }
    try {
      const response = await fetch(url, $siteToken ? { headers: { Authorization: `Bearer ${$siteToken}` } } : undefined)
      if (!response.ok) {
        throw new Error('Не удалось загрузить посты сообщества')
      }
      const payload = await response.json()
      applyPostsPayload(payload, reset)
    } catch (error) {
      console.error(error)
      toast({ content: error instanceof Error ? error.message : 'Ошибка загрузки', type: 'error' })
    } finally {
      loadingMore = false
      loadingCategory = false
      if (browser && hasMore) {
        window.requestAnimationFrame(maybeLoadMore)
      }
    }
  }

  const maybeLoadMore = () => {
    if (!browser || loadingMore || loadingCategory || !hasMore) return
    const viewportBottom = window.scrollY + window.innerHeight
    const pageHeight = document.documentElement.scrollHeight
    if (pageHeight - viewportBottom <= scrollThreshold) {
      void loadPosts(false)
    }
  }

  const onScroll = () => {
    if (scrollRaf !== null) return
    scrollRaf = window.requestAnimationFrame(() => {
      scrollRaf = null
      maybeLoadMore()
    })
  }

  const buildCategoryFilterPath = (explicit: boolean, slugs: string[]) => {
    const params = new URLSearchParams($page.url.search)
    params.delete('category')
    params.delete('categories')
    if (explicit) {
      params.set('categories', slugs.join(','))
    }
    const query = params.toString()
    return `${$page.url.pathname}${query ? `?${query}` : ''}`
  }

  const setCategorySelection = async (nextSlugs: string[], explicit = true) => {
    const allowedSlugs = new Set(comunCategorySlugs)
    const normalized = normalizeCategorySlugList(nextSlugs).filter((slug) => allowedSlugs.has(slug))
    const nextExplicit = explicit && normalized.length !== comunCategorySlugs.length
    const nextSelectedSlugs = nextExplicit ? normalized : []
    const nextSignature = `${nextExplicit ? '1' : '0'}:${nextSelectedSlugs.join(',')}`
    const currentSignature = `${categoryFilterExplicit ? '1' : '0'}:${selectedCategorySlugs.join(',')}`
    if (nextSignature === currentSignature) return
    categoryFilterExplicit = nextExplicit
    selectedCategorySlugs = nextSelectedSlugs
    selectedCategorySlug = nextSelectedSlugs.length === 1 ? nextSelectedSlugs[0] : ''
    hasMore = true
    await goto(buildCategoryFilterPath(nextExplicit, nextSelectedSlugs), {
      replaceState: true,
      noScroll: true,
      keepFocus: true,
    })
    await loadPosts(true)
    if (browser) window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const toggleCategoryFilter = (slug: string) => {
    if (!slug) return
    const next = new Set<string>(categoryFilterExplicit ? selectedCategorySlugs : comunCategorySlugs)
    if (next.has(slug)) next.delete(slug)
    else next.add(slug)
    void setCategorySelection(Array.from(next), true)
  }

  const resetCategoryFilter = () => {
    void setCategorySelection([], false)
  }

  const onWindowMousedown = (event: MouseEvent) => {
    if (!categoryFilterOpen) return
    if (categoryFilterElement?.contains(event.target as Node)) return
    categoryFilterOpen = false
  }

  const refreshComunManage = async () => {
    if (!comun?.slug || !$siteToken) return
    settingsLoading = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug, { includeSettings: true }), {
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить настройки сообщества')
      }
      if (payload?.comun) {
        comun = payload.comun
        settingsDraft = cloneComun(payload.comun)
        settingsCategoryOptions = payload.comun?.options?.categories ?? []
        settingsUserOptions = payload.comun?.moderators ?? []
      }
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка загрузки'
    } finally {
      settingsLoading = false
    }
  }

  const openSettings = async () => {
    if (!$siteToken) {
      const next = `${$page.url.pathname}?settings=1`
      goto(`/account?next=${encodeURIComponent(next)}`)
      return
    }
    settingsUserSearch = ''
    settingsDraft = cloneComun(comun)
    await refreshComunManage()
    if (!comun?.can_moderate) {
      toast({ content: 'Настройки доступны только модераторам сообщества', type: 'warning' })
      return
    }
    settingsOpen = true
  }

  const selectWelcomePost = (postId: number | null) => {
    patchSettingsDraft({
      welcome_post_ref: postId ? String(postId) : '',
      welcome_post_id: postId,
    } as Partial<BackendComun>)
  }

  const toggleDraftCategory = (categoryId: number) => {
    if (!settingsDraft) return
    const current = new Set((settingsDraft.category_ids ?? settingsDraft.categories ?? []).map((item: any) =>
      typeof item === 'number' ? item : item?.id
    ).filter(Boolean))
    if (current.has(categoryId)) current.delete(categoryId)
    else current.add(categoryId)
    settingsDraft = { ...settingsDraft, category_ids: Array.from(current) as number[] }
  }

  const setDraftModeratorIds = (ids: number[]) => {
    if (!settingsDraft) return
    const creatorId = Number(settingsDraft.creator?.id ?? comun?.creator?.id ?? 0)
    const normalizedIds = normalizeIds([...ids, creatorId > 0 ? creatorId : 0])
    const byId = new Map<number, ComunUserOption>()
    for (const user of settingsUserOptions) byId.set(user.id, user)
    for (const moderator of settingsDraft.moderators ?? []) {
      byId.set(moderator.id, {
        id: moderator.id,
        username: moderator.username,
        display_name: moderator.display_name ?? null,
      })
    }
    settingsDraft = {
      ...settingsDraft,
      moderator_ids: normalizedIds,
      moderators: normalizedIds.map((id) => {
        const user = byId.get(id)
        return {
          id,
          username: user?.username ?? String(id),
          display_name: user?.display_name ?? null,
        }
      }),
    }
  }

  const addDraftModerator = (userId: number) => {
    if (!settingsDraft || !canManageComunModerators()) return
    setDraftModeratorIds([...comunModeratorIds(settingsDraft), userId])
  }

  const removeDraftModerator = (userId: number) => {
    if (!settingsDraft || !canManageComunModerators()) return
    setDraftModeratorIds(comunModeratorIds(settingsDraft).filter((id) => id !== userId))
  }

  $: draftCategoryIdSet = new Set<number>(
    ((settingsDraft?.category_ids as number[] | undefined) ??
      (settingsDraft?.categories ?? []).map((item) => item.id)) as number[]
  )
  $: normalizedUserSearch = settingsUserSearch.trim().toLowerCase()
  $: queueSettingsUserSearch(settingsUserSearch)
  $: draftModeratorIdSet = new Set<number>(comunModeratorIds(settingsDraft))
  $: settingsHasChanges = settingsComparable(settingsDraft) !== settingsComparable(comun)
  $: settingsCanDismiss =
    !settingsHasChanges && !settingsSaving && !settingsLogoUploading
  $: filteredUserOptions = (settingsUserOptions ?? [])
    .filter((user) => {
      if (!normalizedUserSearch) return false
      return [user.username, user.display_name ?? '']
        .some((value) => value.toLowerCase().includes(normalizedUserSearch))
    })
    .slice(0, 50)
  $: selectedModeratorUsers = comunModeratorIds(settingsDraft).map((id) => {
    const fromOptions = settingsUserOptions.find((user) => user.id === id)
    if (fromOptions) return fromOptions
    const fromDraft = settingsDraft?.moderators?.find((moderator) => moderator.id === id)
    return {
      id,
      username: fromDraft?.username ?? String(id),
      display_name: fromDraft?.display_name ?? null,
    }
  })
  const saveSettings = async () => {
    if (!comun?.slug || !settingsDraft) return
    settingsSaving = true
    settingsError = ''
    try {
      const welcomePostRef = comunWelcomePostRef(settingsDraft)
      const currentWelcomePostRef = comunWelcomePostRef(comun)
      const response = await fetch(buildComunUrl(comun.slug, { includeSettings: true }), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          name: canManageComunModerators() ? settingsDraft.name ?? '' : undefined,
          website_url: settingsDraft.website_url ?? '',
          logo_url: settingsDraft.logo_url ?? '',
          product_description: settingsDraft.product_description ?? '',
          rules_text: settingsDraft.rules_text ?? '',
          target_audience: settingsDraft.target_audience ?? '',
          minimum_author_rating_to_post: Math.max(
            Number(settingsDraft.minimum_author_rating_to_post ?? 0) || 0,
            0
          ),
          only_moderators_can_post: Boolean(settingsDraft.only_moderators_can_post),
          hide_from_home: canManageComunModerators() ? Boolean(settingsDraft.hide_from_home) : undefined,
          moderator_ids: canManageComunModerators() ? comunModeratorIds(settingsDraft) : undefined,
          category_ids: settingsDraft.category_ids ?? (settingsDraft.categories ?? []).map((category) => category.id),
          welcome_post_ref:
            welcomePostRef !== currentWelcomePostRef ? welcomePostRef : undefined,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить настройки')
      }
      comun = payload.comun ?? comun
      settingsDraft = cloneComun(comun)
      settingsUserOptions = mergeUsersById(settingsUserOptions, payload.comun?.moderators ?? [])
      settingsOpen = false
      toast({ content: 'Настройки сообщества сохранены', type: 'success' })
      await loadPosts(true)
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка сохранения'
    } finally {
      settingsSaving = false
    }
  }

  const openDeleteComunModal = () => {
    if (!canDeleteComun() || deleteComunSaving) return
    deleteComunOpen = true
  }

  const closeDeleteComunModal = () => {
    if (deleteComunSaving) return
    deleteComunOpen = false
  }

  const deleteComun = async () => {
    if (!comun?.slug || !canDeleteComun() || deleteComunSaving) return
    deleteComunSaving = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'DELETE',
        headers: authHeaders(),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось удалить сообщество')
      }
      deleteComunOpen = false
      settingsOpen = false
      toast({ content: 'Сообщество удалено', type: 'success' })
      await goto('/comuns')
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Не удалось удалить сообщество'
    } finally {
      deleteComunSaving = false
    }
  }

  const pickSettingsLogo = () => {
    if (!isModerator()) return
    settingsLogoInput?.click()
  }

  const onSettingsLogoSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file || !settingsDraft) return

    settingsLogoUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      settingsDraft = { ...settingsDraft, logo_url: uploadedUrl }
      toast({ content: 'Логотип загружен. Нажмите «Сохранить» для применения.', type: 'success' })
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Не удалось загрузить логотип', type: 'error' })
    } finally {
      settingsLogoUploading = false
      if (input) input.value = ''
    }
  }

  $: wantsSettingsOpenFromUrl = $page.url.searchParams.get('settings') === '1'

  $: if (!$siteToken) {
    autoSettingsOpenHandled = false
  }

  $: if (!wantsSettingsOpenFromUrl) {
    autoSettingsOpenHandled = false
  }

  $: if (!roadmapSignature) {
    lastRoadmapPreviewSignature = ''
    roadmapPreviewStates = {}
  }

  $: if (
    browser &&
    roadmapSignature &&
    roadmapSignature !== lastRoadmapPreviewSignature &&
    roadmapCanOpenModal
  ) {
    lastRoadmapPreviewSignature = roadmapSignature
    void loadRoadmapPreviews()
  }

  $: if (
    browser &&
    wantsSettingsOpenFromUrl &&
    $siteToken &&
    !settingsOpen &&
    !autoSettingsOpenHandled &&
    !settingsLoading
  ) {
    autoSettingsOpenHandled = true
    void openSettings()
  }

  onMount(() => {
    if (!browser) return
    if ($siteToken && !$siteUser) {
      void refreshSiteUser().catch(() => null)
    }
    maybeLoadMore()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('keydown', onWindowKeydown)
    window.addEventListener('mousedown', onWindowMousedown)
  })

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('keydown', onWindowKeydown)
      window.removeEventListener('mousedown', onWindowMousedown)
      if (scrollRaf !== null) {
        window.cancelAnimationFrame(scrollRaf)
        scrollRaf = null
      }
      if (settingsUserSearchTimer) {
        clearTimeout(settingsUserSearchTimer)
        settingsUserSearchTimer = null
      }
      clearModeratorMenuCloseTimer()
      if (publicRoadmapBodyOverflowBeforeOpen !== null) {
        document.body.style.overflow = publicRoadmapBodyOverflowBeforeOpen
        publicRoadmapBodyOverflowBeforeOpen = null
      }
    }
  })
</script>

<div class="flex flex-col gap-6 max-w-4xl">
  <section class="relative rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 overflow-visible">
    <div class="p-5 sm:p-6 flex flex-col gap-4">
      <div class="flex flex-wrap items-start justify-between gap-4">
        <div class="flex items-start gap-4 min-w-0">
          <div class="h-16 w-16 rounded-2xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
            {#if comun?.logo_url}
              <img src={comun.logo_url} alt={comun?.name ?? 'Логотип'} class="h-full w-full object-cover" />
            {:else}
              <div
                class="comun-logo-fallback h-full w-full grid place-items-center text-2xl font-bold"
                style={comunPlaceholderStyle(comun?.name)}
              >
                {comunInitial(comun?.name)}
              </div>
            {/if}
          </div>
          <div class="min-w-0">
            <h1 class="text-2xl font-semibold tracking-tight text-slate-900 dark:text-zinc-100">
              {comun?.name ?? 'Сообщество'}
            </h1>
            <div class="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-slate-600 dark:text-zinc-400">
              <span>Подписчиков: {formatComunCount(comunSubscribersCount)}</span>
              <span>Авторов: {formatComunCount(comunAuthorsCount)}</span>
              <span
                class="relative inline-flex items-center"
                on:mouseenter={openModeratorMenu}
                on:mouseleave={closeModeratorMenuWithDelay}
                on:focusin={openModeratorMenu}
                on:focusout={closeModeratorMenuWithDelay}
                role="presentation"
              >
                <button
                  type="button"
                  class="text-sm text-slate-600 underline decoration-slate-300 decoration-dotted underline-offset-4 transition hover:text-slate-900 dark:text-zinc-400 dark:decoration-zinc-600 dark:hover:text-zinc-100"
                  aria-haspopup="menu"
                  aria-expanded={moderatorMenuOpen}
                  disabled={!comunModeratorList.length}
                >
                  Модераторов: {formatComunCount(comunModeratorsCount)}
                </button>
                {#if comunModeratorList.length && moderatorMenuOpen}
                  <div
                    class="absolute left-0 top-full z-40 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 bg-white p-2 shadow-xl dark:border-zinc-800 dark:bg-zinc-950"
                    on:mouseenter={openModeratorMenu}
                    on:mouseleave={closeModeratorMenuWithDelay}
                    role="presentation"
                  >
                    <div class="px-2 pb-2 pt-1 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-zinc-400">
                      Модераторы
                    </div>
                    <div class="flex max-h-72 flex-col gap-1 overflow-y-auto">
                      {#each comunModeratorList as moderator}
                        {@const moderatorId = Number(moderator?.id ?? 0)}
                        {@const isSelfModerator = Boolean($siteUser?.id && moderatorId === Number($siteUser.id))}
                        <div class="flex items-center gap-2 rounded-xl px-2 py-2 hover:bg-slate-50 dark:hover:bg-zinc-900">
                          <a
                            href={moderatorId && !moderator.is_deleted ? `/id${moderatorId}` : undefined}
                            class="min-w-0 flex-1 {moderatorId && !moderator.is_deleted ? 'hover:underline' : 'pointer-events-none'}"
                          >
                            <span class="block truncate text-sm font-medium text-slate-900 dark:text-zinc-100">
                              {userDisplayName(moderator)}
                            </span>
                            <span class="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                              {#if moderator.username && !moderator.is_deleted}
                                <span class="truncate">@{moderator.username}</span>
                              {/if}
                              {#if moderator.isCreator}
                                <span class="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:bg-zinc-800 dark:text-zinc-300">
                                  Создатель
                                </span>
                              {/if}
                            </span>
                          </a>
                          <button
                            type="button"
                            class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-200 text-slate-600 transition hover:bg-slate-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-900 dark:hover:text-blue-300"
                            title={isSelfModerator ? 'Это вы' : 'Написать модератору'}
                            aria-label={isSelfModerator ? 'Это вы' : 'Написать модератору'}
                            disabled={!moderatorId || moderator.is_deleted || isSelfModerator || openingModeratorChatId === moderatorId}
                            on:click={() => openModeratorChat(moderator)}
                          >
                            <Icon src={ChatBubbleLeftRight} size="16" mini />
                          </button>
                        </div>
                      {/each}
                    </div>
                  </div>
                {/if}
              </span>
            </div>
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          {#if canShowComunPostButton}
            <Button size="sm" on:click={openComunPostEditor}>
              <span slot="prefix" class="text-base leading-none">+</span>
              Добавить пост
            </Button>
          {/if}
          <div class="relative">
            <Button
              color={isSubscribedToComun ? 'ghost' : undefined}
              on:click={toggleComunInMyFeed}
              title={isSubscribedToComun ? 'Настроить категории в Моей ленте' : 'Добавить сообщество в Мою ленту'}
            >
              {isSubscribedToComun ? 'Вы подписаны' : 'Подписаться'}
            </Button>
            {#if subscriptionCategoriesOpen && isSubscribedToComun && hasComunCategories}
              <div class="absolute right-0 top-full z-30 mt-2 w-72 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
                <div class="mb-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-zinc-400">
                  Категории в моей ленте
                </div>
                <div class="flex max-h-72 flex-col gap-2 overflow-y-auto pr-1">
                  {#each comunCategories as category}
                    <label class="flex cursor-pointer items-center gap-3 rounded-xl px-2 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:text-zinc-200 dark:hover:bg-zinc-900">
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                        checked={subscribedComunCategorySlugs.has(category.slug)}
                        on:change={() => toggleComunCategoryInMyFeed(category.slug)}
                      />
                      <span class="min-w-0 flex-1 truncate">{category.name}</span>
                    </label>
                  {/each}
                </div>
                <button
                  type="button"
                  class="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-900"
                  on:click={() => {
                    subscriptionCategoriesOpen = false
                    toast({ content: 'Настройки подписки сохранены' })
                  }}
                >
                  Сохранить
                </button>
              </div>
            {/if}
          </div>
          {#if isModerator() && comun?.slug}
            <button
              type="button"
              class="inline-flex h-11 w-11 items-center justify-center rounded-xl border border-slate-200 text-slate-700 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-800/60"
              on:click={() => comun?.slug && goto(`/comuns/${comun.slug}/settings`)}
              title="Настройки сообщества"
              aria-label="Настройки сообщества"
            >
              <svg viewBox="0 0 24 24" class="h-5 w-5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <circle cx="12" cy="12" r="3.2"></circle>
                <path d="M19.4 15a1 1 0 0 0 .2 1.1l.1.1a2 2 0 0 1 0 2.8 2 2 0 0 1-2.8 0l-.1-.1a1 1 0 0 0-1.1-.2 1 1 0 0 0-.6.9V20a2 2 0 0 1-4 0v-.2a1 1 0 0 0-.7-.9 1 1 0 0 0-1 .2l-.2.1a2 2 0 0 1-2.8 0 2 2 0 0 1 0-2.8l.1-.1a1 1 0 0 0 .2-1.1 1 1 0 0 0-.9-.6H4a2 2 0 0 1 0-4h.2a1 1 0 0 0 .9-.7 1 1 0 0 0-.2-1l-.1-.2a2 2 0 0 1 0-2.8 2 2 0 0 1 2.8 0l.1.1a1 1 0 0 0 1.1.2 1 1 0 0 0 .6-.9V4a2 2 0 0 1 4 0v.2a1 1 0 0 0 .7.9 1 1 0 0 0 1-.2l.2-.1a2 2 0 0 1 2.8 0 2 2 0 0 1 0 2.8l-.1.1a1 1 0 0 0-.2 1.1 1 1 0 0 0 .9.6h.2a2 2 0 0 1 0 4h-.2a1 1 0 0 0-.9.7z"></path>
              </svg>
            </button>
          {/if}
        </div>
      </div>

      {#if hasComunHeaderDetails && comunHeaderDetailsOpen}
        <div class="border-t border-slate-200 pt-4 dark:border-zinc-800">
            <div class="flex flex-col gap-3">
              {#if comun?.product_description}
                <div class="whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
                  {comun.product_description}
                </div>
              {/if}

              {#if comun?.target_audience}
                <div class="border-t border-slate-200 pt-3 text-sm text-slate-600 dark:border-zinc-800 dark:text-zinc-400">
                  <span class="font-medium text-slate-800 dark:text-zinc-200">Для кого:</span>
                  <span class="whitespace-pre-line"> {comun.target_audience}</span>
                </div>
              {/if}

              {#if comun?.rules_text}
                <div class="border-t border-slate-200 pt-3 dark:border-zinc-800">
                  <div class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-zinc-400">
                    Правила сообщества
                  </div>
                  <div class="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
                    {comun.rules_text}
                  </div>
                </div>
              {/if}
            </div>
        </div>
      {/if}
    </div>

    {#if hasComunHeaderDetails}
      <button
        type="button"
        class="comun-header-expand-button"
        aria-expanded={comunHeaderDetailsOpen}
        aria-label={comunHeaderDetailsOpen ? 'Скрыть описание сообщества' : 'Показать описание сообщества'}
        on:click={() => {
          comunHeaderDetailsOpen = !comunHeaderDetailsOpen
        }}
      >
        <Icon
          src={ChevronDown}
          size="20"
          mini
          class="transition-transform {comunHeaderDetailsOpen ? 'rotate-180' : ''}"
        />
      </button>
    {/if}
  </section>

  {#if hasComunCategories || comunWebsiteUrl || comun?.glossary_enabled || comun?.knowledge_base_enabled || comun?.roadmap_enabled}
    <div class="flex flex-wrap items-center gap-2">
      {#if hasComunCategories}
        <div class="relative" bind:this={categoryFilterElement}>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition-colors {categoryFilterAllSelected ? 'border-blue-300 bg-blue-50 text-blue-700 dark:border-blue-700 dark:bg-blue-950/30 dark:text-blue-300' : 'border-slate-200 bg-white/95 text-slate-700 hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-200 dark:hover:bg-zinc-800/60'}"
            on:click={() => (categoryFilterOpen = !categoryFilterOpen)}
            disabled={loadingCategory}
            aria-expanded={categoryFilterOpen}
            aria-haspopup="menu"
          >
            <span>{categoryFilterLabel}</span>
            <Icon src={ChevronDown} size="16" mini class="text-slate-500 dark:text-zinc-400" />
          </button>
          {#if categoryFilterOpen}
            <div class="absolute left-0 top-full z-30 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-2xl border border-slate-200 bg-white p-3 shadow-xl dark:border-zinc-800 dark:bg-zinc-950">
              <div class="mb-2 flex items-center justify-between gap-3">
                <div class="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500 dark:text-zinc-400">
                  Категории
                </div>
                <button
                  type="button"
                  class="text-xs font-medium text-blue-700 hover:text-blue-800 dark:text-blue-300 dark:hover:text-blue-200"
                  on:click={resetCategoryFilter}
                  disabled={loadingCategory}
                >
                  Все категории
                </button>
              </div>
              <div class="flex max-h-72 flex-col gap-1 overflow-y-auto pr-1">
                {#each comunCategories as category}
                  <label
                    class="flex cursor-pointer items-center gap-3 rounded-xl px-2 py-2 text-sm text-slate-700 hover:bg-slate-50 dark:text-zinc-200 dark:hover:bg-zinc-900"
                    title={category.description || category.name}
                  >
                    <input
                      type="checkbox"
                      class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                      checked={selectedCategorySlugSet.has(category.slug)}
                      disabled={loadingCategory}
                      on:change={() => toggleCategoryFilter(category.slug)}
                    />
                    <span class="min-w-0 flex-1 truncate">{category.name}</span>
                    {#if typeof categoryCountById.get(category.id) === 'number'}
                      <span class="text-xs text-slate-400 dark:text-zinc-500">
                        {formatComunCount(categoryCountById.get(category.id))}
                      </span>
                    {/if}
                  </label>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      {/if}
      {#if comun?.knowledge_base_enabled}
        <a
          href={comunKnowledgeBasePath}
          class="inline-flex items-center justify-center rounded-full border border-slate-200 bg-white/95 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-200 dark:hover:bg-zinc-800/60"
        >
          База знаний
        </a>
      {/if}
      {#if comun?.glossary_enabled}
        <a
          href={comunGlossaryPath}
          class="inline-flex items-center justify-center rounded-full border border-slate-200 bg-white/95 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-200 dark:hover:bg-zinc-800/60"
        >
          Глоссарий
        </a>
      {/if}
      {#if comun?.roadmap_enabled}
        <a
          href={comunRoadmapPath}
          class="inline-flex items-center justify-center rounded-full border border-slate-200 bg-white/95 px-3 py-1.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-200 dark:hover:bg-zinc-800/60"
        >
          Дорожная карта
        </a>
      {/if}
      {#if comunWebsiteUrl}
        <span class="group/website relative inline-flex">
          <a
            href={comunWebsiteUrl}
            target="_blank"
            rel="nofollow noopener noreferrer"
            class="inline-flex h-8 w-8 items-center justify-center rounded-full border border-slate-200 bg-white/95 text-slate-700 transition hover:bg-slate-50 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-200 dark:hover:bg-zinc-800/60 dark:hover:text-blue-300 dark:focus:ring-offset-zinc-950"
            aria-label="Сайт сообщества"
          >
            <Icon src={GlobeAlt} size="16" mini />
          </a>
          <span
            class="pointer-events-none absolute left-1/2 top-full z-30 mt-2 -translate-x-1/2 whitespace-nowrap rounded-lg bg-slate-950 px-2.5 py-1.5 text-xs font-medium text-white opacity-0 shadow-lg transition group-hover/website:opacity-100 group-focus-within/website:opacity-100 dark:bg-zinc-100 dark:text-zinc-950"
            role="tooltip"
          >
            Сайт сообщества
          </span>
        </span>
      {/if}
    </div>
  {/if}

  <ComunRoadmapModal
    open={roadmapModalVisible}
    comunName={comun?.name ?? 'Сообщество'}
    trackedCount={roadmapTrackedCount}
    releasedCount={roadmapReleasedCount}
    stages={roadmapStages}
    getPreviewState={getRoadmapPreviewState}
    stageStyleVars={roadmapStageStyleVars}
    buildPostPath={buildBackendPostPath}
    formatCount={formatRoadmapCount}
    formatDate={formatRoadmapDate}
    snippetForPost={roadmapSnippet}
    onClose={closePublicRoadmapModal}
    onSubmit={openRoadmapSubmitFlow}
  />

  {#if comun?.welcome_post && welcomeFeedPosts.length}
    <section class="rounded-2xl border border-blue-200 dark:border-blue-900/60 bg-blue-50/60 dark:bg-blue-950/20 p-4 sm:p-5">
      <div class="mb-3 text-sm font-semibold text-blue-800 dark:text-blue-300">
        Приветственный пост
      </div>
      <FeedPostsList
        posts={welcomeFeedPosts}
        postClass="feed-shortcut-post rounded-2xl border border-slate-200/80 bg-white/95 px-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85 sm:px-5"
        hideCommunity={true}
        {comunCategories}
        {currentWelcomePostId}
        on:categorychange={handlePostCategoryChange}
        on:pinned={handleWelcomePostPinned}
        on:unpinned={handleWelcomePostUnpinned}
      />
    </section>
  {/if}

  {#if feedPosts.length}
    <FeedPostsList
      posts={feedPosts}
      {loadingMore}
      hideCommunity={true}
      {comunCategories}
      {currentWelcomePostId}
      on:categorychange={handlePostCategoryChange}
      on:pinned={handleWelcomePostPinned}
      on:unpinned={handleWelcomePostUnpinned}
    />
  {:else}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      <div class="flex flex-col gap-4">
        <div>
          {categoryFilterExplicit
            ? 'В выбранных категориях пока нет публикаций.'
            : 'В этом сообществе пока нет публикаций.'}
        </div>
      </div>
    </div>
  {/if}
</div>

<Modal bind:open={settingsOpen} dismissable={settingsCanDismiss} dismissOnBackdrop={true}>
  <div class="w-full max-w-3xl flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Настройки сообщества</div>
    {#if settingsError}
      <div class="rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/20 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
        {settingsError}
      </div>
    {/if}

    {#if settingsLoading}
      <div class="text-sm text-slate-500">Загрузка настроек...</div>
    {:else if settingsDraft}
      <div class="grid gap-4">
        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Название сообщества</span>
          <input
            bind:value={settingsDraft.name}
            type="text"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            disabled={!canManageComunModerators()}
          />
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Веб-сайт</span>
          <input bind:value={settingsDraft.website_url} type="url" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2" />
        </label>

        <div class="flex flex-col gap-2">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Логотип</span>
          <input
            bind:this={settingsLogoInput}
            type="file"
            accept="image/*"
            class="hidden"
            on:change={onSettingsLogoSelected}
          />
          <div class="flex items-center gap-3 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3">
            <div class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
              {#if settingsDraft.logo_url}
                <img src={settingsDraft.logo_url} alt="Предпросмотр логотипа" class="h-full w-full object-cover" />
              {:else}
                <div class="h-full w-full grid place-items-center text-slate-400 dark:text-zinc-500 text-xs text-center px-1">
                  Нет лого
                </div>
              {/if}
            </div>
            <div class="min-w-0 flex-1 flex flex-col gap-1">
              <div class="text-sm text-slate-700 dark:text-zinc-300">
                {#if settingsLogoUploading}
                  Загрузка логотипа...
                {:else if settingsDraft.logo_url}
                  Логотип выбран
                {:else}
                  Загрузите файл изображения
                {/if}
              </div>
              <div class="text-xs text-slate-500 dark:text-zinc-400">
                PNG, JPG, WEBP, GIF
              </div>
            </div>
            <div class="flex flex-wrap gap-2 justify-end">
              <Button size="sm" on:click={pickSettingsLogo} disabled={settingsSaving || settingsLogoUploading}>
                {settingsDraft.logo_url ? 'Заменить' : 'Выбрать файл'}
              </Button>
              {#if settingsDraft.logo_url}
                <Button
                  color="ghost"
                  size="sm"
                  on:click={() => patchSettingsDraft({ logo_url: '' })}
                  disabled={settingsSaving || settingsLogoUploading}
                >
                  Убрать
                </Button>
              {/if}
            </div>
          </div>
        </div>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Описание сообщества</span>
          <textarea bind:value={settingsDraft.product_description} rows="4" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Правила сообщества</span>
          <textarea
            bind:value={settingsDraft.rules_text}
            rows="8"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            placeholder="Правила будут показаны участникам сообщества"
          ></textarea>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Для кого</span>
          <textarea bind:value={settingsDraft.target_audience} rows="2" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">
            Минимальный рейтинг автора для публикации
          </span>
          <input
            bind:value={settingsDraft.minimum_author_rating_to_post}
            type="number"
            min="0"
            step="0.5"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          />
          <span class="text-xs text-slate-500 dark:text-zinc-400">
            `0` означает, что писать в сообщество может любой автор. Сейчас установлен порог от
            {formatRatingValue(settingsDraft.minimum_author_rating_to_post)}.
          </span>
        </label>

        <label class="flex items-start gap-2 cursor-pointer rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
          <input
            type="checkbox"
            checked={Boolean(settingsDraft.only_moderators_can_post)}
            on:change={() =>
              patchSettingsDraft({
                only_moderators_can_post: !Boolean(settingsDraft?.only_moderators_can_post),
              })}
            class="mt-0.5"
          />
          <span class="min-w-0">
            <span class="block text-sm text-slate-900 dark:text-zinc-100">
              Писать в сообщество могут только создатель и модераторы
            </span>
            <span class="block text-xs text-slate-500 dark:text-zinc-400">
              Если включить, новые записи смогут создавать только создатель сообщества и его модераторы.
            </span>
          </span>
        </label>

        {#if canManageComunModerators()}
          <div class="flex flex-col gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
            <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">Видимость постов сообщества в общих лентах</div>
            <label class="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={!settingsDraft.hide_from_home}
                on:change={() =>
                  patchSettingsDraft({
                    hide_from_home: !Boolean(settingsDraft?.hide_from_home),
                  })}
                class="mt-0.5"
              />
              <span class="min-w-0">
                <span class="block text-sm text-slate-900 dark:text-zinc-100">Показывать в Горячем</span>
                <span class="block text-xs text-slate-500 dark:text-zinc-400">
                  Если выключить, посты, созданные в этом сообществе, не попадут на главную.
                </span>
              </span>
            </label>
          </div>
        {/if}

        {#if canManageComunModerators()}
          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Модераторы сообщества</div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Только создатель сообщества может назначать и снимать модераторов. Создатель всегда остается модератором.
            </div>
            <input
              bind:value={settingsUserSearch}
              placeholder="Поиск пользователя по имени или логину..."
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
            <div class="flex flex-col gap-2">
              <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">Выбранные модераторы</div>
              <div class="flex flex-col gap-2">
                {#each selectedModeratorUsers as user}
                  <div class="flex items-center justify-between gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2">
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                        {userDisplayName(user)}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">@{user.username}</div>
                    </div>
                    <Button
                      color="ghost"
                      size="sm"
                      on:click={() => removeDraftModerator(user.id)}
                      disabled={user.id === comun?.creator?.id}
                      title={user.id === comun?.creator?.id ? 'Создателя нельзя убрать из модераторов' : 'Убрать модератора'}
                    >
                      Убрать
                    </Button>
                  </div>
                {/each}
              </div>
            </div>
            <div class="max-h-52 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
              {#if filteredUserOptions.length}
                {#each filteredUserOptions as user}
                  <div class="flex items-center justify-between gap-2 px-3 py-2">
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                        {userDisplayName(user)}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">@{user.username}</div>
                    </div>
                    <Button
                      size="sm"
                      on:click={() => addDraftModerator(user.id)}
                      disabled={draftModeratorIdSet.has(user.id)}
                    >
                      {draftModeratorIdSet.has(user.id) ? 'Добавлен' : 'Добавить'}
                    </Button>
                  </div>
                {/each}
              {:else}
                {#if normalizedUserSearch}
                  <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                    Пользователи не найдены
                  </div>
                {/if}
              {/if}
            </div>
          </div>
        {/if}

        <div class="flex flex-col gap-2">
          <div class="text-sm text-slate-700 dark:text-zinc-300">Внутренние категории</div>
          <div class="grid gap-2 sm:grid-cols-2">
            {#each settingsCategoryOptions as category}
              <label class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={draftCategoryIdSet.has(category.id)}
                  on:change={() => toggleDraftCategory(category.id)}
                  class="mt-0.5"
                />
                <span class="min-w-0">
                  <span class="block text-sm font-medium text-slate-900 dark:text-zinc-100">{category.name}</span>
                  {#if category.description}
                    <span class="block text-xs text-slate-500 dark:text-zinc-400">{category.description}</span>
                  {/if}
                </span>
              </label>
            {/each}
          </div>
        </div>

        <WelcomePostDropdown
          slug={comun?.slug ?? ''}
          token={$siteToken}
          value={settingsDraft.welcome_post_ref ?? settingsDraft.welcome_post_id ?? null}
          selectedPost={settingsDraft.welcome_post}
          disabled={settingsSaving}
          on:change={(event) => selectWelcomePost(event.detail.postId)}
        />
      </div>

      <div class="flex justify-between gap-2 pt-2">
        {#if canDeleteComun()}
          <Button
            color="ghost"
            on:click={openDeleteComunModal}
            disabled={settingsSaving || settingsLogoUploading || deleteComunSaving}
          >
            Удалить сообщество
          </Button>
        {:else}
          <span></span>
        {/if}
        <Button on:click={saveSettings} disabled={settingsSaving || settingsLogoUploading || deleteComunSaving}>
          {settingsSaving ? 'Сохраняем...' : 'Сохранить'}
        </Button>
      </div>
    {/if}
  </div>
</Modal>

<Modal bind:open={deleteComunOpen} dismissable={!deleteComunSaving} dismissOnBackdrop={!deleteComunSaving}>
  <div class="w-full max-w-lg flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Удалить сообщество?</div>
    <div class="text-sm text-slate-700 dark:text-zinc-300">
      Сообщество будет удалено без возможности восстановления.
    </div>
    <div class="rounded-2xl border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/20 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
      Посты пользователей не будут удалены. Они останутся на сайте без привязки к сообществу.
    </div>
    <div class="flex justify-end gap-2">
      <Button color="ghost" on:click={closeDeleteComunModal} disabled={deleteComunSaving}>Отмена</Button>
      <Button on:click={deleteComun} disabled={deleteComunSaving}>
        {deleteComunSaving ? 'Удаляем...' : 'Удалить сообщество'}
      </Button>
    </div>
  </div>
</Modal>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
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
  .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 60% 92%);
    color: hsl(var(--comun-h, 220) 70% 34%);
  }

  :global(.dark) .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 35% 20%);
    color: hsl(var(--comun-h, 220) 78% 72%);
  }

  .comun-header-expand-button {
    position: absolute;
    left: 50%;
    bottom: 0;
    display: inline-flex;
    width: 2.25rem;
    height: 2.25rem;
    align-items: center;
    justify-content: center;
    transform: translate(-50%, 50%);
    border-radius: 999px;
    border: 1px solid rgb(226 232 240);
    background: rgb(255 255 255 / 0.96);
    color: rgb(51 65 85);
    box-shadow: 0 6px 18px rgb(15 23 42 / 0.12);
    transition:
      transform 0.15s ease,
      box-shadow 0.15s ease,
      border-color 0.15s ease;
  }

  .comun-header-expand-button:hover {
    transform: translate(-50%, 50%) translateY(1px);
    border-color: rgb(203 213 225);
    box-shadow: 0 8px 24px rgb(15 23 42 / 0.16);
  }

  .comun-header-expand-button:focus-visible {
    outline: 2px solid rgb(59 130 246);
    outline-offset: 3px;
  }

  :global(.dark) .comun-header-expand-button {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27 / 0.96);
    color: rgb(228 228 231);
    box-shadow: 0 6px 18px rgb(0 0 0 / 0.3);
  }
</style>
