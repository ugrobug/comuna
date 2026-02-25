<script lang="ts" context="module">
</script>

	<script lang="ts">
	  import { browser } from '$app/environment'
	  import { goto } from '$app/navigation'
	  import { page } from '$app/stores'
	  import { env } from '$env/dynamic/public'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { t } from '$lib/translations.js'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import {
    type BackendThematicFeed,
    backendPostToPostView,
    buildFavoritesFeedUrl,
    buildBackendPostPath,
    buildFreshFeedUrl,
    buildHomeFeedUrl,
    buildMyFeedUrl,
    buildThematicFeedsListUrl,
    buildThematicFeedsManageUrl,
    buildThematicFeedPostsUrl,
    buildTagsListUrl,
  } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { userSettings } from '$lib/settings'
  import { normalizeTag } from '$lib/tags'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import { Button, Modal } from 'mono-svelte'
  import { onDestroy, onMount } from 'svelte'
  import { Cog6Tooth, Icon } from 'svelte-hero-icons'

  export let data

  const pageSize = 10
  let feedType = data.feedType ?? 'hot'
  let posts = data.posts ?? []
  let filteredMyFeedPosts = posts
  let offset = posts.length
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let lastPostsRef = data.posts
  let lastFeedType = feedType
  let lastMyFeedKey = ''
  let thematicFeedSlug = data.thematicSlug ?? ''
  let thematicFeedMeta: BackendThematicFeed | null = data.thematicFeed ?? null
  type FolderManageAuthorOption = {
    id: number
    username: string
    title?: string | null
    description?: string | null
    rubric?: string | null
  }
  type FolderManageTagOption = {
    id: number
    name: string
    lemma?: string | null
  }
  let folderSettingsOpen = false
  let folderSettingsLoading = false
  let folderSettingsSaving = false
  let folderSettingsError = ''
  let folderSettingsSuccess = ''
  let folderSettingsDraft: BackendThematicFeed | null = null
  let folderSettingsAuthorOptions: FolderManageAuthorOption[] = []
  let folderSettingsTagOptions: FolderManageTagOption[] = []
  let filteredFolderAuthorOptions: FolderManageAuthorOption[] = []
  let filteredFolderExcludedAuthorOptions: FolderManageAuthorOption[] = []
  let filteredFolderTagOptions: FolderManageTagOption[] = []
  let filteredFolderExcludedTagOptions: FolderManageTagOption[] = []
  let folderSettingsAuthorSearch = ''
  let folderSettingsExcludedAuthorSearch = ''
  let folderSettingsTagSearch = ''
  let folderSettingsExcludedTagSearch = ''
  let myFeedSuggestedFolders: BackendThematicFeed[] = []
  let myFeedSuggestedFoldersLoading = false
  let myFeedSuggestedFoldersLoaded = false
  let myFeedSuggestedFoldersError = ''
	  let lastFeedKey: string | null = null
	  let myFeedSettingsOpen = false
	  let feedParam: string | null = null
	  let readParam: string | null = null
	  let readOnly = false
	  let hiddenReadCount = 0
  const moodDurationMs = 3 * 60 * 60 * 1000
  const moodOptions: Array<{ label: string; value: 'funny' | 'serious' | 'sad' }> = [
    { label: 'Веселое', value: 'funny' },
    { label: 'Серьезное', value: 'serious' },
    { label: 'Грустное', value: 'sad' },
  ]
  let myFeedMood: 'funny' | 'serious' | 'sad' | null = null
  let myFeedMoodExpiresAt: number | null = null
  let moodActive = false
  let effectiveMood: 'funny' | 'serious' | 'sad' | null = null
  let myFeedHasBaseSettings = false
  let moodTagSet = new Set<string>()
  let tagMoodMap = new Map<string, string>()
  let tagLemmaMap = new Map<string, string>()
  let tagMoodLoading = false
  let moodExpiryTimer: ReturnType<typeof setTimeout> | null = null

  const cloneFolderSettingsDraft = (folder: BackendThematicFeed | null): BackendThematicFeed | null =>
    folder ? JSON.parse(JSON.stringify(folder)) : null

  const normalizeFolderSearch = (value: string) => value.trim().toLowerCase()

  const matchesFolderAuthorSearch = (author: FolderManageAuthorOption, query: string) => {
    if (!query) return true
    const haystack = [
      author.username,
      author.title ?? '',
      author.description ?? '',
      author.rubric ?? '',
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(query)
  }

  const matchesFolderTagSearch = (tag: FolderManageTagOption, query: string) => {
    if (!query) return true
    return [tag.name, tag.lemma ?? '']
      .join(' ')
      .toLowerCase()
      .includes(query)
  }

  const formatFolderAuthorOptionLabel = (author: FolderManageAuthorOption) => {
    const title = (author.title ?? '').trim()
    const description = (author.description ?? '').trim()
    const rubric = (author.rubric ?? '').trim()
    const parts = [`@${author.username}`]
    if (title) parts.push(title)
    if (rubric) parts.push(`Рубрика: ${rubric}`)
    if (description) parts.push(description)
    return parts.join(' · ')
  }

  const formatFolderTagOptionLabel = (tag: FolderManageTagOption) => {
    const lemma = (tag.lemma ?? '').trim()
    return lemma && lemma.toLowerCase() !== tag.name.toLowerCase()
      ? `${tag.name} · лемма: ${lemma}`
      : tag.name
  }

  const canManageCurrentFolder = () => {
    if (!$siteUser || !thematicFeedMeta) return false
    if ($siteUser.is_staff) return true
    const currentUsername = ($siteUser.username ?? '').trim().toLowerCase()
    if (!currentUsername) return false
    return (thematicFeedMeta.moderators ?? []).some(
      (moderator) => (moderator?.username ?? '').trim().toLowerCase() === currentUsername
    )
  }

  type FolderAuthorSelectionKey = 'author_ids' | 'excluded_author_ids'

  const getFolderAuthorOptionById = (id: number): FolderManageAuthorOption | null =>
    folderSettingsAuthorOptions.find((author) => author.id === id) ?? null

  const getFolderSelectedAuthorIds = (key: FolderAuthorSelectionKey): number[] => {
    if (!folderSettingsDraft) return []
    const values = (folderSettingsDraft as any)[key]
    return Array.isArray(values) ? values.filter((value) => Number.isFinite(value)) : []
  }

  const getFolderSelectedAuthors = (key: FolderAuthorSelectionKey): FolderManageAuthorOption[] =>
    getFolderSelectedAuthorIds(key)
      .map((id) => getFolderAuthorOptionById(id))
      .filter(Boolean) as FolderManageAuthorOption[]

  const isFolderAuthorSelected = (key: FolderAuthorSelectionKey, authorId: number) =>
    getFolderSelectedAuthorIds(key).includes(authorId)

  const addFolderAuthorToSelection = (key: FolderAuthorSelectionKey, authorId: number) => {
    if (!folderSettingsDraft) return
    if (!Number.isFinite(authorId) || authorId <= 0) return
    const next = new Set(getFolderSelectedAuthorIds(key))
    next.add(authorId)
    ;(folderSettingsDraft as any)[key] = Array.from(next)
    touchFolderSettingsDraft()
  }

  const removeFolderAuthorFromSelection = (key: FolderAuthorSelectionKey, authorId: number) => {
    if (!folderSettingsDraft) return
    ;(folderSettingsDraft as any)[key] = getFolderSelectedAuthorIds(key).filter((id) => id !== authorId)
    touchFolderSettingsDraft()
  }

  const getFolderAvailableAuthors = (
    key: FolderAuthorSelectionKey,
    candidates: FolderManageAuthorOption[]
  ): FolderManageAuthorOption[] => candidates.filter((author) => !isFolderAuthorSelected(key, author.id))

  const touchFolderSettingsDraft = () => {
    if (!folderSettingsDraft) return
    folderSettingsDraft = { ...folderSettingsDraft }
  }

  const readMultiSelectIds = (event: Event): number[] => {
    const target = event.currentTarget as HTMLSelectElement
    return Array.from(target.selectedOptions)
      .map((option) => Number(option.value))
      .filter((value) => Number.isFinite(value) && value > 0)
  }

  const updateFolderSettingsSelection = (
    event: Event,
    key: 'author_ids' | 'excluded_author_ids' | 'tag_ids' | 'excluded_tag_ids'
  ) => {
    if (!folderSettingsDraft) return
    ;(folderSettingsDraft as any)[key] = readMultiSelectIds(event)
    touchFolderSettingsDraft()
  }

  const loadCurrentFolderSettings = async () => {
    if (!browser || !$siteToken) return
    if (!thematicFeedSlug) return
    folderSettingsLoading = true
    folderSettingsError = ''
    folderSettingsSuccess = ''
    try {
      const response = await fetch(buildThematicFeedsManageUrl(), {
        headers: {
          Authorization: `Bearer ${$siteToken}`,
        },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить настройки папки')
      }
      folderSettingsAuthorOptions = payload.options?.authors ?? []
      folderSettingsTagOptions = payload.options?.tags ?? []
      folderSettingsAuthorSearch = ''
      folderSettingsExcludedAuthorSearch = ''
      folderSettingsTagSearch = ''
      folderSettingsExcludedTagSearch = ''
      const currentFolder =
        (payload.folders ?? []).find(
          (folder: BackendThematicFeed) => folder.slug === thematicFeedSlug
        ) ?? null
      if (!currentFolder) {
        throw new Error('Папка недоступна для редактирования')
      }
      folderSettingsDraft = cloneFolderSettingsDraft(currentFolder)
    } catch (error) {
      folderSettingsError =
        error instanceof Error ? error.message : 'Ошибка загрузки настроек папки'
    } finally {
      folderSettingsLoading = false
    }
  }

  const loadMyFeedSuggestedFolders = async () => {
    if (!browser || myFeedSuggestedFoldersLoading) return
    myFeedSuggestedFoldersLoading = true
    myFeedSuggestedFoldersError = ''
    try {
      const response = await fetch(buildThematicFeedsListUrl())
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить список папок')
      }
      myFeedSuggestedFolders = payload.folders ?? payload.feeds ?? []
      myFeedSuggestedFoldersLoaded = true
    } catch (error) {
      myFeedSuggestedFoldersError =
        error instanceof Error ? error.message : 'Ошибка загрузки папок'
      myFeedSuggestedFoldersLoaded = true
    } finally {
      myFeedSuggestedFoldersLoading = false
    }
  }

  const openCurrentFolderSettings = async () => {
    if (!thematicFeedSlug) return
    if (!$siteUser) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    folderSettingsOpen = true
    await loadCurrentFolderSettings()
  }

  const closeCurrentFolderSettings = () => {
    folderSettingsOpen = false
    folderSettingsError = ''
    folderSettingsSuccess = ''
  }

  $: filteredFolderAuthorOptions = folderSettingsAuthorOptions.filter((author) =>
    matchesFolderAuthorSearch(author, normalizeFolderSearch(folderSettingsAuthorSearch))
  )
  $: filteredFolderExcludedAuthorOptions = folderSettingsAuthorOptions.filter((author) =>
    matchesFolderAuthorSearch(author, normalizeFolderSearch(folderSettingsExcludedAuthorSearch))
  )
  $: filteredFolderTagOptions = folderSettingsTagOptions.filter((tag) =>
    matchesFolderTagSearch(tag, normalizeFolderSearch(folderSettingsTagSearch))
  )
  $: filteredFolderExcludedTagOptions = folderSettingsTagOptions.filter((tag) =>
    matchesFolderTagSearch(tag, normalizeFolderSearch(folderSettingsExcludedTagSearch))
  )

  const saveCurrentFolderSettings = async () => {
    if (!folderSettingsDraft || !thematicFeedSlug || !$siteToken) return
    folderSettingsSaving = true
    folderSettingsError = ''
    folderSettingsSuccess = ''
    try {
      const response = await fetch(buildThematicFeedsManageUrl(thematicFeedSlug), {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${$siteToken}`,
        },
        body: JSON.stringify({
          author_ids: folderSettingsDraft.author_ids ?? [],
          excluded_author_ids: folderSettingsDraft.excluded_author_ids ?? [],
          tag_ids: folderSettingsDraft.tag_ids ?? [],
          excluded_tag_ids: folderSettingsDraft.excluded_tag_ids ?? [],
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить настройки папки')
      }
      const updatedFolder = (payload.folder ?? null) as BackendThematicFeed | null
      if (updatedFolder) {
        thematicFeedMeta = updatedFolder
        folderSettingsDraft = cloneFolderSettingsDraft(updatedFolder)
      }
      folderSettingsSuccess = 'Настройки папки сохранены'
      posts = []
      offset = 0
      hasMore = true
      loadingMore = false
      hiddenReadCount = 0
      if (browser) {
        await loadMore()
      }
    } catch (error) {
      folderSettingsError =
        error instanceof Error ? error.message : 'Ошибка сохранения настроек папки'
    } finally {
      folderSettingsSaving = false
    }
  }
  $: if (data?.posts) {
    if (
      data.posts !== lastPostsRef &&
      data.feedType === feedType &&
      data.feedType !== 'mine' &&
      data.feedType !== 'favorites'
    ) {
      lastPostsRef = data.posts
      posts = data.posts ?? []
      if (data.feedType === 'thematic') {
        thematicFeedMeta = data.thematicFeed ?? null
      }
      offset = posts.length
      hasMore = posts.length === pageSize
      loadingMore = false
    }
  }
	  $: feedParam = $page.url.searchParams.get('feed')
	  $: thematicFeedSlug = ($page.url.searchParams.get('theme') ?? '').trim()
	  $: readParam = $page.url.searchParams.get('read')
	  $: readOnly = readParam === '1' || readParam === 'true' || readParam === 'yes'
	  $: if (data?.feedType && data.feedType !== lastFeedType && feedParam) {
	    lastFeedType = data.feedType
	    feedType = data.feedType ?? 'hot'
	    thematicFeedMeta = feedType === 'thematic' ? null : thematicFeedMeta
	    if (feedType === 'mine' || feedType === 'favorites') {
	      posts = []
	      offset = 0
	      hasMore = false
	      loadingMore = false
	      hiddenReadCount = 0
	      thematicFeedMeta = null
	      lastMyFeedKey = ''
	    } else {
	      posts = data.posts ?? []
	      thematicFeedMeta = feedType === 'thematic' ? (data.thematicFeed ?? null) : thematicFeedMeta
	      offset = posts.length
	      hasMore = posts.length === pageSize
	      loadingMore = false
	      hiddenReadCount = 0
	      if (feedType !== 'thematic') {
	        thematicFeedMeta = null
	      }
	    }
	  }
	  $: if (!feedParam) {
	    const preferredFeed = $userSettings.homeFeed ?? 'hot'
	    if (preferredFeed !== feedType) {
	      feedType = preferredFeed
	      lastFeedType = preferredFeed
	      thematicFeedMeta = feedType === 'thematic' ? null : thematicFeedMeta
	      if (feedType === 'mine' || feedType === 'favorites') {
	        posts = []
	        offset = 0
	        hasMore = false
	        loadingMore = false
	        hiddenReadCount = 0
	        thematicFeedMeta = null
	        lastMyFeedKey = ''
	      } else {
	        posts = []
	        offset = 0
	        hasMore = true
	        loadingMore = false
	        hiddenReadCount = 0
	        if (feedType !== 'thematic') {
	          thematicFeedMeta = null
	        }
	        if (browser) {
	          loadMore()
	        }
	      }
	    }
	  }
  const scrollThreshold = 400
  let scrollRaf: number | null = null

  $: selectedRubrics = $userSettings.myFeedRubrics ?? []
  $: selectedAuthors = $userSettings.myFeedAuthors ?? []
  $: selectedMyFeedTags = $userSettings.myFeedTags ?? []
  $: myFeedHasBaseSettings =
    selectedRubrics.length > 0 || selectedAuthors.length > 0 || selectedMyFeedTags.length > 0
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: canLoadMyFeed =
    feedType === 'mine' &&
    $siteUser &&
    myFeedHasBaseSettings
	  $: hideNegativeMyFeed = $userSettings.myFeedHideNegative ?? true
	  $: hideReadPosts = ($userSettings.hideReadPosts ?? false) && !!$siteUser
	  $: effectiveHideRead = hideReadPosts && !readOnly
	  $: myFeedMood = $userSettings.myFeedMood ?? null
  $: myFeedMoodExpiresAt = $userSettings.myFeedMoodExpiresAt ?? null
  $: moodActive =
    !!myFeedMood &&
    !!myFeedMoodExpiresAt &&
    Date.now() < myFeedMoodExpiresAt
  $: effectiveMood = moodActive ? myFeedMood : null
  // Определяем канонический URL для главной страницы
  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = `${siteBaseUrl}/`

	  const buildPageUrl = (offset: number) => {
	    let baseUrl = buildHomeFeedUrl({
	      hideRead: effectiveHideRead,
	      onlyRead: readOnly,
	    })
	    if (feedType === 'fresh') {
	      baseUrl = buildFreshFeedUrl({
	        hideRead: effectiveHideRead,
	        onlyRead: readOnly,
	      })
	    } else if (feedType === 'favorites') {
	      baseUrl = buildFavoritesFeedUrl()
	    } else if (feedType === 'thematic') {
	      baseUrl = buildThematicFeedPostsUrl(thematicFeedSlug, {
	        hideRead: effectiveHideRead,
	        onlyRead: readOnly,
	      })
	    } else if (feedType === 'mine') {
	      baseUrl = buildMyFeedUrl(
	        selectedRubrics,
	        selectedAuthors,
	        selectedMyFeedTags,
	        hideNegativeMyFeed,
	        effectiveHideRead,
	        readOnly
	      )
	    }
	    const url = new URL(baseUrl)
	    url.searchParams.set('limit', String(pageSize))
	    url.searchParams.set('offset', String(offset))
	    return url.toString()
	  }

  const authorKey = (backendPost: { author?: { username?: string } }) =>
    (backendPost.author?.username ?? '').trim().toLowerCase()

  const isAuthorVisible = (backendPost: { author?: { username?: string } }) => {
    const key = authorKey(backendPost)
    if (!key) return true
    return !hiddenAuthorKeys.has(key)
  }

	  $: if (feedType !== 'mine' && feedType !== 'favorites') {
	    const feedKey = [
	      feedType,
	      feedType === 'thematic' ? thematicFeedSlug || '(none)' : '',
	      readOnly ? 'only-read' : effectiveHideRead ? 'hide-read' : 'all',
	      hideNegativeMyFeed ? 'hide-neg' : 'show-neg',
	    ].join('|')
	    if (lastFeedKey === null) {
	      lastFeedKey = feedKey
	      if ((effectiveHideRead || readOnly) && browser) {
	        posts = []
	        offset = 0
	        hasMore = true
	        loadingMore = false
	        hiddenReadCount = 0
	        loadMore()
	      }
	    } else if (feedKey !== lastFeedKey) {
	      lastFeedKey = feedKey
	      posts = []
	      offset = 0
	      hasMore = true
	      loadingMore = false
	      hiddenReadCount = 0
	      if (browser) {
	        loadMore()
	      }
	    }
	  }

	  const loadMore = async () => {
	    if (!browser || loadingMore || !hasMore) return
	    if (feedType === 'mine' && !canLoadMyFeed) return
	    if (feedType === 'favorites' && !$siteUser) return
	    if (feedType === 'thematic' && !thematicFeedSlug) return
	    if (readOnly && !$siteUser) return
	    loadingMore = true
	    try {
	      const token = $siteToken
	      const headers = token ? { Authorization: `Bearer ${token}` } : undefined
	      const response = await fetch(buildPageUrl(offset), {
	        headers,
	      })
      if (!response.ok) {
        hasMore = false
        return
	      }
	      const payload = await response.json()
	      if (payload?.thematic_feed && feedType === 'thematic') {
	        thematicFeedMeta = payload.thematic_feed
	      }
	      if (typeof payload.hidden_read_count === 'number') {
	        hiddenReadCount = payload.hidden_read_count
	      }
	      const nextPosts = payload.posts ?? []
	      if (nextPosts.length) {
	        posts = [...posts, ...nextPosts]
	        offset += nextPosts.length
      }
      if (nextPosts.length < pageSize) {
        hasMore = false
      }
    } catch (error) {
      console.error('Failed to load more posts:', error)
    } finally {
      loadingMore = false
    }
  }

  const openMyFeedSettings = () => {
    myFeedSettingsOpen = true
  }

  const toggleMyFeedSettings = () => {
    if (myFeedSettingsOpen) {
      myFeedSettingsOpen = false
    } else {
      openMyFeedSettings()
    }
  }

	  const resetMyFeed = () => {
	    posts = []
	    offset = 0
	    hasMore = false
	    loadingMore = false
	    hiddenReadCount = 0
	    if (canLoadMyFeed) {
	      hasMore = true
	      loadMore()
	    }
	  }

  const loadTagMoods = async () => {
    if (!browser || tagMoodLoading || tagMoodMap.size) return
    tagMoodLoading = true
    try {
      const response = await fetch(buildTagsListUrl())
      if (response.ok) {
        const payload = await response.json()
        const entries =
          payload.tags?.map((tag: { name: string; lemma?: string; mood: string }) => [
            normalizeTag(tag.lemma ?? tag.name),
            tag.mood,
          ]) ?? []
        const lemmaEntries =
          payload.tags?.map((tag: { name: string; lemma?: string }) => [
            normalizeTag(tag.name),
            normalizeTag(tag.lemma ?? tag.name),
          ]) ?? []
        tagMoodMap = new Map(entries)
        tagLemmaMap = new Map(lemmaEntries)
      }
    } catch (error) {
      console.error('Failed to load tag moods:', error)
    } finally {
      tagMoodLoading = false
    }
  }

  const selectMood = (value: 'funny' | 'serious' | 'sad') => {
    if (moodActive && myFeedMood === value) {
      clearMood()
      return
    }
    const expiresAt = Date.now() + moodDurationMs
    $userSettings = {
      ...$userSettings,
      myFeedMood: value,
      myFeedMoodExpiresAt: expiresAt,
    }
  }

  const clearMood = () => {
    $userSettings = {
      ...$userSettings,
      myFeedMood: null,
      myFeedMoodExpiresAt: null,
    }
  }

  const scheduleMoodClear = (expiresAt: number | null) => {
    if (!browser) return
    if (moodExpiryTimer) {
      window.clearTimeout(moodExpiryTimer)
      moodExpiryTimer = null
    }
    if (!expiresAt) return
    const delay = expiresAt - Date.now()
    if (delay <= 0) {
      userSettings.update((settings) => ({
        ...settings,
        myFeedMood: null,
        myFeedMoodExpiresAt: null,
      }))
      return
    }
    moodExpiryTimer = window.setTimeout(() => {
      userSettings.update((settings) => ({
        ...settings,
        myFeedMood: null,
        myFeedMoodExpiresAt: null,
      }))
    }, delay)
  }


  $: moodTagSet =
    effectiveMood && tagMoodMap.size
      ? new Set(
          Array.from(tagMoodMap.entries())
            .filter(([, mood]) => mood === effectiveMood)
            .map(([name]) => name)
        )
      : new Set<string>()

	  $: filteredMyFeedPosts =
	    effectiveMood && tagMoodMap.size
	      ? posts.filter((post) =>
	          (post.tags ?? []).some((tag) => {
	            const rawName = typeof tag === 'string' ? tag : tag.name
	            const normalized = normalizeTag(rawName)
	            const lemma =
	              typeof tag === 'string'
	                ? tagLemmaMap.get(normalized) ?? normalized
	                : normalizeTag(tag.lemma ?? tag.name)
	            return moodTagSet.has(lemma)
	          })
	        ).filter(isAuthorVisible)
	      : effectiveMood
	        ? []
	        : posts.filter(isAuthorVisible)

  $: visiblePosts = posts.filter(isAuthorVisible)

  $: if (feedType === 'mine') {
    const authKey = $siteUser ? 'auth' : 'anon'
	    const key = `${authKey}:${selectedRubrics.join(',')}:${selectedAuthors.join(',')}:${selectedMyFeedTags.join(',')}:${hideNegativeMyFeed ? 'no-negative' : 'all'}:${readOnly ? 'only-read' : effectiveHideRead ? 'hide-read' : 'all-read'}`
    if (key !== lastMyFeedKey) {
      lastMyFeedKey = key
      resetMyFeed()
    }
    if (effectiveMood) {
      loadTagMoods()
    }
  }

  $: if (browser && feedType === 'mine' && !!$siteUser && !myFeedHasBaseSettings && !myFeedSuggestedFoldersLoaded) {
    loadMyFeedSuggestedFolders()
  }

  $: if (!$siteUser) {
    myFeedSuggestedFolders = []
    myFeedSuggestedFoldersLoaded = false
    myFeedSuggestedFoldersLoading = false
    myFeedSuggestedFoldersError = ''
  }

  $: if (feedType === 'favorites') {
    const authKey = $siteUser ? 'auth' : 'anon'
    const key = `favorites:${authKey}`
    if (key !== lastMyFeedKey) {
      lastMyFeedKey = key
      posts = []
      offset = 0
      hasMore = !!$siteUser
      loadingMore = false
      hiddenReadCount = 0
      if ($siteUser && browser) {
        loadMore()
      }
    }
  }

  const maybeLoadMore = () => {
    if (!browser || loadingMore || !hasMore) return
    const viewportBottom = window.scrollY + window.innerHeight
    const pageHeight = document.documentElement.scrollHeight
    if (pageHeight - viewportBottom <= scrollThreshold) {
      loadMore()
    }
  }

  const onScroll = () => {
    if (scrollRaf !== null) return
    scrollRaf = window.requestAnimationFrame(() => {
      scrollRaf = null
      maybeLoadMore()
    })
  }

  onMount(() => {
    if (!browser) return
    maybeLoadMore()
    const unsubscribe = userSettings.subscribe((settings) => {
      scheduleMoodClear(settings.myFeedMoodExpiresAt ?? null)
    })
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      unsubscribe()
    }
  })

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('scroll', onScroll)
      if (scrollRaf !== null) {
        window.cancelAnimationFrame(scrollRaf)
        scrollRaf = null
      }
      if (moodExpiryTimer) {
        window.clearTimeout(moodExpiryTimer)
        moodExpiryTimer = null
      }
    }
  })

  const openReadPosts = () => {
    const url = new URL($page.url)
    url.searchParams.set('read', '1')
    url.searchParams.set('feed', feedType)
    goto(`${url.pathname}?${url.searchParams.toString()}`)
  }

  const closeReadPosts = () => {
    const url = new URL($page.url)
    url.searchParams.delete('read')
    url.searchParams.set('feed', feedType)
    goto(`${url.pathname}?${url.searchParams.toString()}`)
  }

  const hasMyFeedCustomizations = () => {
    const rubrics = $userSettings.myFeedRubrics ?? []
    const authors = $userSettings.myFeedAuthors ?? []
    const tags = $userSettings.myFeedTags ?? []
    const hiddenAuthors = $userSettings.hiddenAuthors ?? []
    const tagRules = $userSettings.tagRules ?? {}
    return (
      rubrics.length > 0 ||
      authors.length > 0 ||
      tags.length > 0 ||
      hiddenAuthors.length > 0 ||
      Object.keys(tagRules).length > 0
    )
  }

  const applyFolderPresetToMyFeed = async (folderPreset: BackendThematicFeed | null) => {
    if (!folderPreset) return
    if (!$siteUser) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    if (browser && hasMyFeedCustomizations()) {
      const confirmed = window.confirm(
        'У вас уже настроена "Моя лента". Нажатие на кнопку заменит текущие настройки настройками папки. После этого вы сможете дополнительно настроить свою ленту. Продолжить?'
      )
      if (!confirmed) return
    }
    const authors = Array.from(
      new Set(
        (folderPreset.authors ?? [])
          .map((author) => (author?.username ?? '').trim())
          .filter(Boolean)
      )
    )
    const excludedAuthors = Array.from(
      new Set(
        (folderPreset.excluded_authors ?? [])
          .map((author) => (author?.username ?? '').trim())
          .filter(Boolean)
      )
    )
    const includedTags = Array.from(
      new Set(
        (folderPreset.tags ?? [])
          .map((tag) => normalizeTag(tag?.lemma ?? tag?.name ?? ''))
          .filter(Boolean)
      )
    )
    const nextTagRules: Record<string, 'hide' | 'blur'> = {
      ...($userSettings.tagRules ?? {}),
    }
    for (const [key, value] of Object.entries(nextTagRules)) {
      if (value === 'hide') {
        delete nextTagRules[key]
      }
    }
    for (const tag of folderPreset.blocked_tags ?? []) {
      const normalized = normalizeTag(tag?.lemma ?? tag?.name ?? '')
      if (!normalized) continue
      nextTagRules[normalized] = 'hide'
    }
    $userSettings = {
      ...$userSettings,
      myFeedRubrics: [],
      myFeedAuthors: authors,
      myFeedTags: includedTags,
      hiddenAuthors: excludedAuthors,
      tagRules: nextTagRules,
    }
    goto('/?feed=mine')
  }

  const applyThematicFeedToMyFeed = async () => {
    await applyFolderPresetToMyFeed(thematicFeedMeta)
  }
</script>
<div class="flex flex-col gap-2 max-w-full w-full min-w-0">
  <header class="flex flex-col gap-2 relative">
    {#if feedType === 'mine'}
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">
        Моя лента
      </h1>
      {#if $siteUser}
        <button
          type="button"
          class="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200"
          on:click={toggleMyFeedSettings}
          aria-expanded={myFeedSettingsOpen}
        >
          <Icon src={Cog6Tooth} size="16" mini />
          <span>Настроить</span>
        </button>
      {/if}
    {:else if feedType === 'favorites'}
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">
        Избранное
      </h1>
    {:else if feedType === 'thematic'}
      <div class="flex flex-col gap-2">
        <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">
          {#if thematicFeedMeta?.name}
            Папка: {thematicFeedMeta.name}
          {:else}
            Папка
          {/if}
        </h1>
        {#if thematicFeedMeta?.description}
          <div class="text-sm text-slate-600 dark:text-zinc-300">
            {thematicFeedMeta.description}
          </div>
        {/if}
        {#if thematicFeedMeta}
          <div class="pt-1 flex flex-wrap gap-2">
            <Button on:click={applyThematicFeedToMyFeed}>
              Сделать моей лентой
            </Button>
            {#if canManageCurrentFolder()}
              <Button color="ghost" on:click={openCurrentFolderSettings}>
                <span class="inline-flex items-center gap-2">
                  <Icon src={Cog6Tooth} size="16" mini />
                  <span>Настройки</span>
                </span>
              </Button>
            {/if}
          </div>
        {/if}
      </div>
    {:else}
      <Header pageHeader>
        {$t('routes.frontpage.title')}
      </Header>
    {/if}
  </header>
  <Modal bind:open={folderSettingsOpen} on:close={closeCurrentFolderSettings}>
    <div class="w-full max-w-[48rem] flex flex-col gap-4">
      <div>
        <h2 class="text-xl font-semibold text-slate-900 dark:text-zinc-100">
          Настройки папки
        </h2>
        <p class="mt-1 text-sm text-slate-500 dark:text-zinc-400">
          Добавляйте и исключайте авторов и теги для текущей папки.
        </p>
      </div>

      {#if folderSettingsError}
        <div class="rounded-xl border border-rose-200 dark:border-rose-900 bg-rose-50/70 dark:bg-rose-950/20 p-3 text-sm text-rose-700 dark:text-rose-300">
          {folderSettingsError}
        </div>
      {/if}
      {#if folderSettingsSuccess}
        <div class="rounded-xl border border-emerald-200 dark:border-emerald-900 bg-emerald-50/70 dark:bg-emerald-950/20 p-3 text-sm text-emerald-700 dark:text-emerald-300">
          {folderSettingsSuccess}
        </div>
      {/if}

      {#if folderSettingsLoading}
        <div class="text-sm text-slate-500 dark:text-zinc-400">Загружаем настройки папки...</div>
      {:else if folderSettingsDraft}
        <div class="flex flex-col gap-4">
          <label class="flex flex-col gap-1 text-sm min-w-0">
            <span>Авторы</span>
            <input
              type="text"
              bind:value={folderSettingsAuthorSearch}
              placeholder="Поиск по нику, названию канала, описанию"
              class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
            />
            <div class="rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 max-h-72 overflow-y-auto">
              {#each getFolderAvailableAuthors('author_ids', filteredFolderAuthorOptions).slice(0, 30) as author}
                <div class="flex items-start justify-between gap-3 px-3 py-2 border-b last:border-b-0 border-slate-100 dark:border-zinc-800">
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                      @{author.username}
                    </div>
                    {#if author.title}
                      <div class="text-xs text-slate-700 dark:text-zinc-300 line-clamp-2">
                        {author.title}
                      </div>
                    {/if}
                    <div class="text-xs text-slate-500 dark:text-zinc-400">
                      {author.rubric ? `Рубрика: ${author.rubric}` : 'Без рубрики'}
                    </div>
                    {#if author.description}
                      <div class="text-xs text-slate-500 dark:text-zinc-400 line-clamp-2">
                        {author.description}
                      </div>
                    {/if}
                  </div>
                  <button
                    type="button"
                    class="shrink-0 px-2 py-1 rounded-md border border-slate-200 dark:border-zinc-700 text-xs font-medium hover:bg-slate-50 dark:hover:bg-zinc-800"
                    on:click={() => addFolderAuthorToSelection('author_ids', author.id)}
                  >
                    Добавить
                  </button>
                </div>
              {:else}
                <div class="px-3 py-3 text-xs text-slate-500 dark:text-zinc-400">
                  Ничего не найдено
                </div>
              {/each}
            </div>
            <div class="mt-2 flex flex-col gap-2">
              <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                Добавленные авторы
              </div>
              {#each getFolderSelectedAuthors('author_ids') as author}
                <div class="flex items-start justify-between gap-3 rounded-lg border border-slate-200 dark:border-zinc-700 bg-slate-50/70 dark:bg-zinc-900/60 px-3 py-2">
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                      @{author.username}
                    </div>
                    {#if author.title}
                      <div class="text-xs text-slate-700 dark:text-zinc-300 line-clamp-2">
                        {author.title}
                      </div>
                    {/if}
                    {#if author.description}
                      <div class="text-xs text-slate-500 dark:text-zinc-400 line-clamp-2">
                        {author.description}
                      </div>
                    {/if}
                  </div>
                  <button
                    type="button"
                    class="shrink-0 px-2 py-1 rounded-md border border-slate-200 dark:border-zinc-700 text-xs hover:bg-white dark:hover:bg-zinc-800"
                    on:click={() => removeFolderAuthorFromSelection('author_ids', author.id)}
                  >
                    Убрать
                  </button>
                </div>
              {:else}
                <div class="text-xs text-slate-500 dark:text-zinc-400">
                  Пока никто не добавлен
                </div>
              {/each}
            </div>
          </label>

          <label class="flex flex-col gap-1 text-sm min-w-0">
            <span>Исключенные авторы</span>
            <input
              type="text"
              bind:value={folderSettingsExcludedAuthorSearch}
              placeholder="Поиск по нику, названию канала, описанию"
              class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
            />
            <div class="rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950 max-h-72 overflow-y-auto">
              {#each getFolderAvailableAuthors('excluded_author_ids', filteredFolderExcludedAuthorOptions).slice(0, 30) as author}
                <div class="flex items-start justify-between gap-3 px-3 py-2 border-b last:border-b-0 border-slate-100 dark:border-zinc-800">
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                      @{author.username}
                    </div>
                    {#if author.title}
                      <div class="text-xs text-slate-700 dark:text-zinc-300 line-clamp-2">
                        {author.title}
                      </div>
                    {/if}
                    <div class="text-xs text-slate-500 dark:text-zinc-400">
                      {author.rubric ? `Рубрика: ${author.rubric}` : 'Без рубрики'}
                    </div>
                    {#if author.description}
                      <div class="text-xs text-slate-500 dark:text-zinc-400 line-clamp-2">
                        {author.description}
                      </div>
                    {/if}
                  </div>
                  <button
                    type="button"
                    class="shrink-0 px-2 py-1 rounded-md border border-slate-200 dark:border-zinc-700 text-xs font-medium hover:bg-slate-50 dark:hover:bg-zinc-800"
                    on:click={() => addFolderAuthorToSelection('excluded_author_ids', author.id)}
                  >
                    Добавить
                  </button>
                </div>
              {:else}
                <div class="px-3 py-3 text-xs text-slate-500 dark:text-zinc-400">
                  Ничего не найдено
                </div>
              {/each}
            </div>
            <div class="mt-2 flex flex-col gap-2">
              <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                Исключенные авторы
              </div>
              {#each getFolderSelectedAuthors('excluded_author_ids') as author}
                <div class="flex items-start justify-between gap-3 rounded-lg border border-slate-200 dark:border-zinc-700 bg-slate-50/70 dark:bg-zinc-900/60 px-3 py-2">
                  <div class="min-w-0">
                    <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                      @{author.username}
                    </div>
                    {#if author.title}
                      <div class="text-xs text-slate-700 dark:text-zinc-300 line-clamp-2">
                        {author.title}
                      </div>
                    {/if}
                    {#if author.description}
                      <div class="text-xs text-slate-500 dark:text-zinc-400 line-clamp-2">
                        {author.description}
                      </div>
                    {/if}
                  </div>
                  <button
                    type="button"
                    class="shrink-0 px-2 py-1 rounded-md border border-slate-200 dark:border-zinc-700 text-xs hover:bg-white dark:hover:bg-zinc-800"
                    on:click={() => removeFolderAuthorFromSelection('excluded_author_ids', author.id)}
                  >
                    Убрать
                  </button>
                </div>
              {:else}
                <div class="text-xs text-slate-500 dark:text-zinc-400">
                  Пока никого нет в исключениях
                </div>
              {/each}
            </div>
          </label>

          <label class="flex flex-col gap-1 text-sm min-w-0">
            <span>Теги</span>
            <input
              type="text"
              bind:value={folderSettingsTagSearch}
              placeholder="Поиск по тегу или лемме"
              class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
            />
            <select
              multiple
              size="12"
              class="px-2 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
              on:change={(e) => updateFolderSettingsSelection(e, 'tag_ids')}
            >
              {#each filteredFolderTagOptions as tag}
                <option value={tag.id} selected={(folderSettingsDraft.tag_ids ?? []).includes(tag.id)}>
                  {formatFolderTagOptionLabel(tag)}
                </option>
              {/each}
            </select>
          </label>

          <label class="flex flex-col gap-1 text-sm min-w-0">
            <span>Исключенные теги</span>
            <input
              type="text"
              bind:value={folderSettingsExcludedTagSearch}
              placeholder="Поиск по тегу или лемме"
              class="px-3 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
            />
            <select
              multiple
              size="12"
              class="px-2 py-2 rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-950"
              on:change={(e) => updateFolderSettingsSelection(e, 'excluded_tag_ids')}
            >
              {#each filteredFolderExcludedTagOptions as tag}
                <option value={tag.id} selected={(folderSettingsDraft.excluded_tag_ids ?? []).includes(tag.id)}>
                  {formatFolderTagOptionLabel(tag)}
                </option>
              {/each}
            </select>
          </label>
        </div>
      {:else}
        <div class="text-sm text-slate-500 dark:text-zinc-400">
          Не удалось открыть настройки текущей папки.
        </div>
      {/if}

      <div class="flex justify-end gap-2">
        <Button color="ghost" on:click={closeCurrentFolderSettings}>Закрыть</Button>
        <Button
          disabled={folderSettingsLoading || folderSettingsSaving || !folderSettingsDraft}
          on:click={saveCurrentFolderSettings}
        >
          {folderSettingsSaving ? 'Сохраняем...' : 'Сохранить'}
        </Button>
      </div>
    </div>
  </Modal>
  {#if $siteUser && readOnly && feedType !== 'favorites'}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-3 flex items-center justify-between gap-3">
      <div class="text-sm text-slate-600 dark:text-zinc-300">
        Показываем только прочитанные посты
      </div>
      <button
        type="button"
        class="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
        on:click={closeReadPosts}
      >
        Вернуться
      </button>
    </div>
  {:else if $siteUser && feedType !== 'favorites' && effectiveHideRead && hiddenReadCount > 0}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-3 flex items-center justify-between gap-3">
      <div class="text-sm text-slate-600 dark:text-zinc-300">
        {hiddenReadCount} прочитанных постов скрыто
      </div>
      <button
        type="button"
        class="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline"
        on:click={openReadPosts}
      >
        Показать
      </button>
    </div>
  {/if}
  {#if feedType === 'mine' && !$siteUser}
    <div class="text-base text-slate-500">
      После регистрации вы получите доступ к персонализируемой ленте, которую сможете настроить и видеть только интересные вам посты.
    </div>
  {:else if feedType === 'favorites' && !$siteUser}
    <div class="text-base text-slate-500">
      После регистрации вы сможете добавлять посты в избранное и видеть их в отдельной ленте.
    </div>
  {:else if feedType === 'thematic' && !thematicFeedSlug}
    <div class="text-base text-slate-500">
      Выберите папку в левом меню, чтобы посмотреть готовую подборку авторов и фильтров по тегам.
    </div>
  {:else if feedType === 'mine' && $siteUser}
    <div class="flex flex-col gap-4">
      {#if myFeedSettingsOpen}
        <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 flex flex-col gap-4">
          <div class="flex flex-wrap gap-2">
            {#each moodOptions as mood}
              <Button
                color={effectiveMood === mood.value ? 'primary' : 'ghost'}
                on:click={() => selectMood(mood.value)}
              >
                {mood.label}
              </Button>
            {/each}
          </div>
          <div class="text-xs text-slate-500 dark:text-zinc-400">
            Можно быстро настроить ленту под настроение на 3 часа — действует в текущей сессии.
          </div>
          <div class="text-sm text-slate-600 dark:text-zinc-300">
            Выбор рубрик и составление черного списка доступны в настройках сайта.
          </div>
          <a href="/settings" class="text-sm text-blue-600 dark:text-blue-400 hover:underline">
            Перейти в настройки
          </a>
        </div>
      {:else}
        {#if !myFeedHasBaseSettings}
          <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 flex flex-col gap-4">
            <div class="flex flex-col gap-2">
              <div class="text-sm text-slate-700 dark:text-zinc-200">
                Ваша лента пока не настроена.
              </div>
              <div class="text-sm text-slate-500 dark:text-zinc-400">
                Вы можете настроить ее вручную или выбрать готовую папку, которая станет вашей лентой, чтобы не начинать с нуля.
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <Button color="ghost" on:click={openMyFeedSettings}>
                Настроить мою ленту
              </Button>
              <a href="/settings" class="inline-flex items-center text-sm text-blue-600 dark:text-blue-400 hover:underline">
                Открыть настройки сайта
              </a>
            </div>
            <div class="flex flex-col gap-3">
              <div class="text-sm font-medium text-slate-800 dark:text-zinc-200">
                Или выберите готовую папку
              </div>
              {#if myFeedSuggestedFoldersLoading}
                <div class="text-sm text-slate-500 dark:text-zinc-400">Загружаем папки...</div>
              {:else if myFeedSuggestedFoldersError}
                <div class="text-sm text-rose-600 dark:text-rose-300">{myFeedSuggestedFoldersError}</div>
              {:else if myFeedSuggestedFolders.length}
                <div class="grid gap-2 md:grid-cols-2">
                  {#each myFeedSuggestedFolders as folder}
                    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-3 flex flex-col gap-2 min-w-0">
                      <div class="min-w-0">
                        <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                          {folder.name}
                        </div>
                        {#if folder.description}
                          <div class="text-xs text-slate-500 dark:text-zinc-400 line-clamp-2">
                            {folder.description}
                          </div>
                        {/if}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400">
                        {folder.authors_count ?? 0} авторов · {folder.tags_count ?? 0} тегов · {folder.blocked_tags_count ?? 0} искл. тегов
                      </div>
                      <div class="flex flex-wrap gap-2">
                        <Button on:click={() => applyFolderPresetToMyFeed(folder)}>
                          Сделать моей лентой
                        </Button>
                        <a
                          href={`/?feed=thematic&theme=${encodeURIComponent(folder.slug)}`}
                          class="inline-flex items-center text-sm text-blue-600 dark:text-blue-400 hover:underline"
                        >
                          Открыть папку
                        </a>
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <div class="text-sm text-slate-500 dark:text-zinc-400">
                  Пока нет готовых папок. Можно настроить ленту вручную.
                </div>
              {/if}
            </div>
          </div>
        {/if}
      {/if}
      {#if effectiveMood && tagMoodLoading}
        <div class="text-sm text-slate-500">Загружаем теги настроения...</div>
      {/if}
      {#if filteredMyFeedPosts?.length}
        <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
          {#each filteredMyFeedPosts as backendPost (backendPost.id)}
            {@const postView = backendPostToPostView(backendPost, backendPost.author)}
            <Post
              post={postView}
              class="feed-shortcut-post"
              view="cozy"
              actions={true}
              showReadMore={false}
              showFullBody={false}
              linkOverride={buildBackendPostPath(backendPost)}
              userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
              communityUrlOverride={backendPost.rubric_slug ? `/rubrics/${backendPost.rubric_slug}/posts` : undefined}
              subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
              subscribeLabel="Подписаться"
            />
          {/each}
        </div>
        {#if loadingMore}
          <div class="text-sm text-slate-500">Загрузка...</div>
        {/if}
      {:else if !myFeedHasBaseSettings}
        <div class="text-base text-slate-500">Выберите настройки или папку, чтобы запустить “Мою ленту”.</div>
      {:else}
        <div class="text-base text-slate-500">Пока нет публикаций.</div>
      {/if}
    </div>
  {:else if visiblePosts?.length}
    <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
      {#each visiblePosts as backendPost (backendPost.id)}
        {@const postView = backendPostToPostView(backendPost, backendPost.author)}
        <Post
          post={postView}
          class="feed-shortcut-post"
          view="cozy"
          actions={true}
          showReadMore={false}
          showFullBody={false}
          linkOverride={buildBackendPostPath(backendPost)}
          userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
          communityUrlOverride={backendPost.rubric_slug ? `/rubrics/${backendPost.rubric_slug}/posts` : undefined}
          subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
          subscribeLabel="Подписаться"
        />
      {/each}
    </div>
    {#if loadingMore}
      <div class="text-sm text-slate-500">Загрузка...</div>
    {/if}
  {:else}
    <div class="text-base text-slate-500">Пока нет публикаций.</div>
  {/if}
</div>

<svelte:head>
  <title>Самые новые и обсуждаемые посты лучших telegram каналов</title>
  <meta name="description" content={env.PUBLIC_SITE_DESCRIPTION} />
  
  <!-- Open Graph теги -->
  <meta property="og:title" content={env.PUBLIC_OG_TITLE} />
  <meta property="og:description" content={env.PUBLIC_OG_DESCRIPTION} />
  <meta property="og:image" content={env.PUBLIC_OG_IMAGE} />
  <meta property="og:url" content={env.PUBLIC_OG_URL} />
  <meta property="og:type" content="website" />
  
  <!-- Twitter теги -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={env.PUBLIC_TWITTER_TITLE} />
  <meta name="twitter:description" content={env.PUBLIC_TWITTER_DESCRIPTION} />
  
  <!-- Дополнительные мета-теги -->
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
