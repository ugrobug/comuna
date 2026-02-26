<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { onDestroy, onMount } from 'svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import {
    backendPostToPostView,
    buildBackendPostPath,
    buildComunPostCategoryUrl,
    buildComunPostsUrl,
    buildComunUrl,
    buildTagsEnsureUrl,
    type BackendComun,
    type BackendComunCategory,
    type BackendPost,
    type BackendTag,
  } from '$lib/api/backend'
  import { siteToken, uploadSiteImage } from '$lib/siteAuth'
  import { env } from '$env/dynamic/public'
  import { userSettings } from '$lib/settings'

  export let data

  const pageSize = data.pageSize ?? 10
  let comun: BackendComun | null = data.comun ?? null
  let posts: BackendPost[] = data.posts ?? []
  let selectedCategorySlug = data.selectedCategory?.slug ?? data.initialCategorySlug ?? ''
  let hasMore = posts.length === pageSize
  let loadingMore = false
  let loadingCategory = false
  let lastPostsRef = data.posts
  let lastComunRef = data.comun
  const scrollThreshold = 400
  let scrollRaf: number | null = null
  let categorySavingPostIds = new Set<number>()

  let settingsOpen = false
  let settingsLoading = false
  let settingsSaving = false
  let settingsLogoUploading = false
  let settingsError = ''
  let settingsTagSearch = ''
  let settingsTagCreating = false
  let settingsUserSearch = ''
  let settingsDraft: BackendComun | null = null
  let settingsLogoInput: HTMLInputElement | null = null
  let lastAuthRefreshToken: string | null = null
  let autoSettingsOpenHandled = false
  let wantsSettingsOpenFromUrl = false
  let settingsCategoryOptions: BackendComunCategory[] = []
  type ComunTagOption = BackendTag & { id: number }
  type ComunUserOption = { id: number; username: string; display_name?: string | null }
  let settingsTagOptions: ComunTagOption[] = []
  let settingsUserOptions: ComunUserOption[] = []

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

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: comunName = comun?.name || 'Комуна'
  $: welcomePostView = comun?.welcome_post ? backendPostToPostView(comun.welcome_post) : null
  $: comunTopMembers = comun?.activity?.top_members ?? []
  $: comunParticipantsCount = comun?.activity?.participants_count ?? comunTopMembers.length
  $: myFeedComunSlugs = ($userSettings.myFeedComuns ?? []).map((slug) => slug.trim()).filter(Boolean)
  $: currentComunSlug = (comun?.slug ?? '').trim()
  $: isSubscribedToComun = !!currentComunSlug && myFeedComunSlugs.includes(currentComunSlug)
  $: title = `${comunName} — ${siteTitle}`
  $: description =
    comun?.product_description || `Посты и обсуждения продукта «${comunName}» на ${siteTitle}.`
  $: canonicalUrl = new URL(
    $page.url.pathname + (selectedCategorySlug ? `?category=${encodeURIComponent(selectedCategorySlug)}` : ''),
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

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
      website_url: (value?.website_url ?? '').trim(),
      logo_url: (value?.logo_url ?? '').trim(),
      product_description: (value?.product_description ?? '').trim(),
      target_audience: (value?.target_audience ?? '').trim(),
      include_in_public_feeds: value?.include_in_public_feeds ?? true,
      product_tag_id: value?.product_tag_id ?? value?.product_tag?.id ?? null,
      category_ids: comunCategoryIds(value),
      moderator_ids: comunModeratorIds(value),
      welcome_post_ref: String(value?.welcome_post_ref ?? value?.welcome_post_id ?? '').trim(),
    })

  const userInitials = (username?: string | null) =>
    (username || '?').trim().slice(0, 1).toUpperCase() || '?'

  const userDisplayName = (user?: { username?: string | null; display_name?: string | null } | null) => {
    const displayName = (user?.display_name ?? '').trim()
    if (displayName) return displayName
    const username = (user?.username ?? '').trim()
    return username ? `@${username}` : 'Пользователь'
  }

  const toggleComunInMyFeed = async () => {
    const slug = (comun?.slug ?? '').trim()
    if (!slug) return
    if (!$siteToken) {
      const next = encodeURIComponent(`${$page.url.pathname}${$page.url.search}`)
      goto(`/account?next=${next}`)
      return
    }
    const next = new Set<string>(myFeedComunSlugs)
    if (next.has(slug)) {
      next.delete(slug)
      $userSettings = {
        ...$userSettings,
        myFeedComuns: Array.from(next),
      }
      toast({ content: 'Комуна убрана из "Моей ленты"' })
      return
    }
    next.add(slug)
    $userSettings = {
      ...$userSettings,
      myFeedComuns: Array.from(next),
    }
    toast({ content: 'Посты этой комуны будут попадать в "Мою ленту"' })
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const buildPostsUrl = (offset: number) => {
    if (!comun?.slug) return ''
    const url = new URL(buildComunPostsUrl(comun.slug, { categorySlug: selectedCategorySlug || undefined }))
    url.searchParams.set('limit', String(pageSize))
    url.searchParams.set('offset', String(offset))
    return url.toString()
  }

  const applyPostsPayload = (payload: any, reset = false) => {
    if (payload?.comun) {
      comun = payload.comun
    }
    const nextPosts = (payload?.posts ?? []) as BackendPost[]
    if (reset) {
      posts = nextPosts
    } else if (nextPosts.length) {
      posts = [...posts, ...nextPosts]
    }
    hasMore = nextPosts.length === pageSize
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
        throw new Error('Не удалось загрузить посты комуны')
      }
      const payload = await response.json()
      applyPostsPayload(payload, reset)
    } catch (error) {
      console.error(error)
      toast({ content: error instanceof Error ? error.message : 'Ошибка загрузки', type: 'error' })
    } finally {
      loadingMore = false
      loadingCategory = false
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

  const setCategoryFilter = async (slug: string) => {
    if (slug === selectedCategorySlug) return
    selectedCategorySlug = slug
    hasMore = true
    await goto(
      slug ? `${$page.url.pathname}?category=${encodeURIComponent(slug)}` : $page.url.pathname,
      { replaceState: true, noScroll: true, keepFocus: true }
    )
    await loadPosts(true)
    if (browser) window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const refreshComunManage = async () => {
    if (!comun?.slug || !$siteToken) return
    settingsLoading = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        headers: { Authorization: `Bearer ${$siteToken}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось загрузить настройки комуны')
      }
      if (payload?.comun) {
        comun = payload.comun
        settingsDraft = cloneComun(payload.comun)
        settingsCategoryOptions = payload.comun?.options?.categories ?? []
        settingsTagOptions = payload.comun?.options?.tags ?? []
        settingsUserOptions = payload.comun?.options?.users ?? []
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
    settingsTagSearch = ''
    settingsUserSearch = ''
    settingsDraft = cloneComun(comun)
    await refreshComunManage()
    if (!comun?.can_moderate) {
      toast({ content: 'Настройки доступны только модераторам комуны', type: 'warning' })
      return
    }
    settingsOpen = true
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

  const chooseDraftTag = (tag: ComunTagOption) => {
    if (!settingsDraft) return
    settingsDraft = {
      ...settingsDraft,
      product_tag_id: tag.id,
      product_tag: { id: tag.id, name: tag.name, lemma: tag.lemma ?? null },
    }
  }

  const clearDraftTag = () => {
    if (!settingsDraft) return
    settingsDraft = { ...settingsDraft, product_tag_id: null, product_tag: null }
  }

  const onIncludeInPublicFeedsChange = (event: Event) => {
    if (!settingsDraft) return
    const input = event.currentTarget as HTMLInputElement | null
    settingsDraft = {
      ...settingsDraft,
      include_in_public_feeds: input?.checked ?? true,
    }
  }

  const normalizeTagInput = (value: string) =>
    value.trim().replace(/^#+/, '').replace(/\s+/g, ' ').trim()

  $: normalizedTagSearch = settingsTagSearch.trim().toLowerCase()
  $: normalizedTagCreateValue = normalizeTagInput(settingsTagSearch)
  $: hasExactTagMatch = (settingsTagOptions ?? []).some((tag) => {
    const needle = normalizedTagCreateValue.toLowerCase()
    if (!needle) return false
    return [tag.name, tag.lemma ?? '']
      .map((value) => normalizeTagInput(value).toLowerCase())
      .some((value) => value === needle)
  })
  $: draftCategoryIdSet = new Set<number>(
    ((settingsDraft?.category_ids as number[] | undefined) ??
      (settingsDraft?.categories ?? []).map((item) => item.id)) as number[]
  )
  $: filteredTagOptions = (settingsTagOptions ?? []).filter((tag) => {
    if (!normalizedTagSearch) return true
    return [tag.name, tag.lemma ?? ''].some((value) => value.toLowerCase().includes(normalizedTagSearch))
  }).slice(0, 30)
  $: normalizedUserSearch = settingsUserSearch.trim().toLowerCase()
  $: draftModeratorIdSet = new Set<number>(comunModeratorIds(settingsDraft))
  $: settingsHasChanges = settingsComparable(settingsDraft) !== settingsComparable(comun)
  $: settingsCanDismiss =
    !settingsHasChanges && !settingsSaving && !settingsLogoUploading && !settingsTagCreating
  $: filteredUserOptions = (settingsUserOptions ?? [])
    .filter((user) => {
      if (!normalizedUserSearch) return true
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

  const createTagAndChooseDraft = async () => {
    const tagName = normalizeTagInput(settingsTagSearch)
    if (!tagName || settingsTagCreating) return
    settingsTagCreating = true
    try {
      const response = await fetch(buildTagsEnsureUrl(), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ name: tagName }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.tag?.id) {
        throw new Error(payload?.error || 'Не удалось добавить тег')
      }
      const nextTag: ComunTagOption = {
        id: Number(payload.tag.id),
        name: String(payload.tag.name ?? tagName),
        lemma: payload.tag.lemma ? String(payload.tag.lemma) : null,
      }
      const nextOptions = [...(settingsTagOptions ?? [])]
      const existingIndex = nextOptions.findIndex((tag) => tag.id === nextTag.id)
      if (existingIndex >= 0) {
        nextOptions[existingIndex] = nextTag
      } else {
        nextOptions.push(nextTag)
      }
      settingsTagOptions = nextOptions.sort((a, b) => a.name.localeCompare(b.name, 'ru'))
      chooseDraftTag(nextTag)
      settingsTagSearch = nextTag.name
      toast({
        content: payload.created ? 'Тег добавлен и выбран' : 'Тег найден и выбран',
        type: 'success',
      })
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Не удалось добавить тег', type: 'error' })
    } finally {
      settingsTagCreating = false
    }
  }

  const saveSettings = async () => {
    if (!comun?.slug || !settingsDraft) return
    settingsSaving = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          website_url: settingsDraft.website_url ?? '',
          logo_url: settingsDraft.logo_url ?? '',
          product_description: settingsDraft.product_description ?? '',
          target_audience: settingsDraft.target_audience ?? '',
          include_in_public_feeds: canManageComunModerators()
            ? (settingsDraft.include_in_public_feeds ?? true)
            : undefined,
          moderator_ids: canManageComunModerators() ? comunModeratorIds(settingsDraft) : undefined,
          product_tag_id: settingsDraft.product_tag_id ?? null,
          category_ids: settingsDraft.category_ids ?? (settingsDraft.categories ?? []).map((category) => category.id),
          welcome_post_ref: settingsDraft.welcome_post_ref ?? '',
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить настройки')
      }
      comun = payload.comun ?? comun
      settingsDraft = cloneComun(comun)
      settingsOpen = false
      toast({ content: 'Настройки комуны сохранены', type: 'success' })
      await loadPosts(true)
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка сохранения'
    } finally {
      settingsSaving = false
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

  const setWelcomePost = async (postId: number) => {
    if (!comun?.slug || !isModerator()) return
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ welcome_post_id: postId }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload?.error || 'Не удалось выбрать приветственный пост')
      comun = payload.comun ?? comun
      toast({ content: 'Приветственный пост обновлен', type: 'success' })
      await loadPosts(true)
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Ошибка обновления', type: 'error' })
    }
  }

  const updatePostCategory = async (postId: number, categoryId: number | null) => {
    if (!comun?.slug || !isModerator()) return
    categorySavingPostIds = new Set([...categorySavingPostIds, postId])
    try {
      const response = await fetch(buildComunPostCategoryUrl(comun.slug, postId), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({ category_id: categoryId }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось обновить категорию')
      }
      const assignment = payload?.assignment
      posts = posts.map((post) => {
        if (post.id !== postId) return post
        return {
          ...post,
          comun_category_id: assignment?.category_id ?? null,
          comun_category: assignment?.category ?? null,
        }
      })
    } catch (error) {
      toast({ content: error instanceof Error ? error.message : 'Ошибка обновления категории', type: 'error' })
    } finally {
      const next = new Set(categorySavingPostIds)
      next.delete(postId)
      categorySavingPostIds = next
    }
  }

  const onPostCategoryChange = (event: Event, postId: number) => {
    const target = event.currentTarget as HTMLSelectElement | null
    if (!target) return
    const value = target.value ? Number(target.value) : null
    void updatePostCategory(postId, value)
  }

  $: wantsSettingsOpenFromUrl = $page.url.searchParams.get('settings') === '1'

  $: if (browser && comun?.slug && $siteToken && $siteToken !== lastAuthRefreshToken) {
    lastAuthRefreshToken = $siteToken
    void refreshComunManage()
  }

  $: if (!$siteToken) {
    lastAuthRefreshToken = null
    autoSettingsOpenHandled = false
  }

  $: if (!wantsSettingsOpenFromUrl) {
    autoSettingsOpenHandled = false
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
    maybeLoadMore()
    window.addEventListener('scroll', onScroll, { passive: true })
  })

  onDestroy(() => {
    if (browser) {
      window.removeEventListener('scroll', onScroll)
      if (scrollRaf !== null) {
        window.cancelAnimationFrame(scrollRaf)
        scrollRaf = null
      }
    }
  })
</script>

<div class="flex flex-col gap-6 max-w-4xl">
  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 overflow-hidden">
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
            <Header noMargin>{comun?.name ?? 'Комуна'}</Header>
            {#if comun?.product_tag}
              <div
                class="mt-1 text-sm text-slate-600 dark:text-zinc-400"
                title="Записи опубликованные с данным тегом на всем сайте будут отображаться в этой комуне"
              >
                Тег продукта: <span class="font-medium">#{comun.product_tag.name}</span>
              </div>
            {:else}
              <div class="mt-1 text-sm text-amber-700 dark:text-amber-300">
                Тег продукта пока не выбран. Посты в ленте не появятся, пока модератор не задаст тег.
              </div>
            {/if}
            {#if comun?.creator?.username}
              <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                Создатель:
                {#if comun?.creator?.id}
                  <a
                    href={`/id${comun.creator.id}`}
                    class="ml-1 text-slate-700 dark:text-zinc-300 hover:underline"
                    title={comun.creator.username ? `Профиль @${comun.creator.username}` : 'Профиль пользователя'}
                  >
                    {userDisplayName(comun.creator)}
                  </a>
                {:else}
                  <span class="ml-1 text-slate-700 dark:text-zinc-300">{userDisplayName(comun.creator)}</span>
                {/if}
              </div>
            {/if}
          </div>
        </div>
        <div class="flex flex-wrap items-center gap-2">
          <Button
            color={isSubscribedToComun ? 'ghost' : undefined}
            on:click={toggleComunInMyFeed}
            title={isSubscribedToComun ? 'Убрать коммуну из Моей ленты' : 'Добавить коммуну в Мою ленту'}
          >
            {isSubscribedToComun ? 'В моей ленте' : 'В мою ленту'}
          </Button>
          {#if comun?.website_url}
            <a
              href={comun.website_url}
              target="_blank"
              rel="nofollow noopener"
              class="inline-flex items-center rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-zinc-800/60"
            >
              Сайт
            </a>
          {/if}
          {#if isModerator() && comun?.slug}
            <Button color="ghost" on:click={() => goto(`/comuns/${encodeURIComponent(comun.slug)}/settings`)}>
              Настройки комуны
            </Button>
          {/if}
        </div>
      </div>

      {#if comun?.product_description}
        <div class="text-sm leading-relaxed text-slate-700 dark:text-zinc-300 whitespace-pre-line">
          {comun.product_description}
        </div>
      {/if}

      {#if comun?.target_audience}
        <div class="text-sm text-slate-600 dark:text-zinc-400">
          <span class="font-medium text-slate-800 dark:text-zinc-200">Целевая аудитория:</span>
          {comun.target_audience}
        </div>
      {/if}

      {#if comunTopMembers.length}
        <div class="flex flex-col gap-2 pt-1">
          <div class="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
            <span class="uppercase tracking-wide">Рейтинг активности</span>
            <span>•</span>
            <span>{comunParticipantsCount} участников</span>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            {#each comunTopMembers as member}
              <div
                class="inline-flex items-center justify-center h-9 w-9 rounded-full overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 text-xs font-semibold text-slate-700 dark:text-zinc-200"
                title={`#${member.rank} @${member.username} — ${member.points} баллов`}
                aria-label={`#${member.rank} ${member.username}, ${member.points} баллов`}
              >
                {#if member.avatar_url}
                  <img
                    src={member.avatar_url}
                    alt={`Аватар @${member.username}`}
                    class="h-full w-full object-cover"
                    loading="lazy"
                  />
                {:else}
                  {userInitials(member.username)}
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}

      <div class="flex flex-wrap gap-2 pt-1">
        <button
          type="button"
          class="rounded-full px-3 py-1.5 text-sm border transition-colors {selectedCategorySlug ? 'border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800/60' : 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300'}"
          on:click={() => setCategoryFilter('')}
          disabled={loadingCategory}
        >
          Все
        </button>
        {#each comun?.categories ?? [] as category}
          <button
            type="button"
            class="rounded-full px-3 py-1.5 text-sm border transition-colors {selectedCategorySlug === category.slug ? 'border-blue-300 dark:border-blue-700 bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300' : 'border-slate-200 dark:border-zinc-800 hover:bg-slate-50 dark:hover:bg-zinc-800/60'}"
            on:click={() => setCategoryFilter(category.slug)}
            disabled={loadingCategory}
            title={category.description || category.name}
          >
            {category.name}
          </button>
        {/each}
      </div>
    </div>
  </section>

  {#if isModerator() && comun?.slug}
    <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 sm:p-5">
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="text-sm text-slate-600 dark:text-zinc-400">
          Опубликуйте запись прямо в коммуну. Тег продукта будет подставлен автоматически.
        </div>
        <Button on:click={() => goto(`/comuns/${comun.slug}/new-post`)}>
          Добавить
        </Button>
      </div>
    </section>
  {/if}

  {#if comun?.welcome_post}
    <section class="rounded-2xl border border-blue-200 dark:border-blue-900/60 bg-blue-50/60 dark:bg-blue-950/20 p-4 sm:p-5">
      <div class="mb-3 text-sm font-semibold text-blue-800 dark:text-blue-300">
        Приветственный пост
      </div>
      <Post
        post={welcomePostView}
        class="rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 shadow-sm px-4 sm:px-5"
        view="cozy"
        actions={true}
        showReadMore={false}
        showFullBody={false}
        linkOverride={buildBackendPostPath(comun.welcome_post)}
        userUrlOverride={comun.welcome_post.author?.username ? `/${comun.welcome_post.author.username}` : undefined}
        communityUrlOverride={comun.welcome_post.rubric_slug ? `/rubrics/${comun.welcome_post.rubric_slug}/posts` : undefined}
        subscribeUrl={comun.welcome_post.channel_url ?? comun.welcome_post.author?.channel_url}
        subscribeLabel="Подписаться"
      />
    </section>
  {/if}

  {#if visiblePosts.length}
    <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
      {#each visiblePosts as backendPost (backendPost.id)}
        <div class="flex flex-col gap-3">
          <Post
            post={backendPostToPostView(backendPost)}
            class="feed-shortcut-post rounded-2xl border border-slate-200/80 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 shadow-sm px-4 sm:px-5"
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

          {#if isModerator()}
            <div class="rounded-xl border border-slate-200 dark:border-zinc-800 bg-white/80 dark:bg-zinc-900/60 p-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div class="flex flex-col gap-1 min-w-0">
                <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">Категория внутри комуны</div>
                <div class="flex flex-wrap items-center gap-2">
                  <select
                    class="rounded-lg border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-2 py-1 text-sm"
                    value={backendPost.comun_category_id ?? ''}
                    on:change={(event) => onPostCategoryChange(event, backendPost.id)}
                    disabled={categorySavingPostIds.has(backendPost.id)}
                  >
                    <option value="">Без категории</option>
                    {#each comun?.categories ?? [] as category}
                      <option value={category.id}>{category.name}</option>
                    {/each}
                  </select>
                  {#if backendPost.comun_category}
                    <span class="text-xs rounded-full bg-slate-100 dark:bg-zinc-800 px-2 py-1">
                      {backendPost.comun_category.name}
                    </span>
                  {/if}
                </div>
              </div>
              <div class="flex flex-wrap gap-2">
                <Button
                  color="ghost"
                  size="sm"
                  on:click={() => setWelcomePost(backendPost.id)}
                >
                  Сделать приветственным
                </Button>
              </div>
            </div>
          {/if}
        </div>
      {/each}
    </div>
    {#if loadingMore}
      <div class="text-sm text-slate-500">Загрузка...</div>
    {/if}
  {:else}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-slate-600 dark:text-zinc-400">
      {#if comun?.product_tag}
        В этой комуне пока нет публикаций по тегу #{comun.product_tag.name}.
      {:else}
        Модератору нужно выбрать тег продукта в настройках комуны, чтобы сюда начали попадать посты.
      {/if}
    </div>
  {/if}
</div>

<Modal bind:open={settingsOpen} dismissable={settingsCanDismiss} dismissOnBackdrop={true}>
  <div class="w-full max-w-3xl flex flex-col gap-4">
    <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Настройки комуны</div>
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
                  on:click={() => (settingsDraft = { ...settingsDraft, logo_url: '' })}
                  disabled={settingsSaving || settingsLogoUploading}
                >
                  Убрать
                </Button>
              {/if}
            </div>
          </div>
        </div>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Описание продукта</span>
          <textarea bind:value={settingsDraft.product_description} rows="4" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
        </label>

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Целевая аудитория</span>
          <textarea bind:value={settingsDraft.target_audience} rows="2" class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"></textarea>
        </label>

        {#if canManageComunModerators()}
          <label class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3 flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              class="mt-1"
              checked={settingsDraft.include_in_public_feeds ?? true}
              on:change={onIncludeInPublicFeedsChange}
            />
            <span class="min-w-0">
              <span class="block text-sm font-medium text-slate-900 dark:text-zinc-100">
                Показывать посты этой комуны в Горячем и Свежее
              </span>
              <span class="block text-xs text-slate-500 dark:text-zinc-400">
                Если выключить, посты, созданные внутри комуны, останутся только в ленте комуны и персональных лентах пользователей.
              </span>
            </span>
          </label>
        {/if}

        {#if canManageComunModerators()}
          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Модераторы комуны</div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Только создатель комуны может назначать и снимать модераторов. Создатель всегда остается модератором.
            </div>
            <input
              bind:value={settingsUserSearch}
              placeholder="Поиск пользователя по имени или логину..."
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
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
                <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">Пользователи не найдены</div>
              {/if}
            </div>
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
          </div>
        {/if}

        <div class="flex flex-col gap-2">
          <div class="text-sm text-slate-700 dark:text-zinc-300">Тег продукта (посты с этим тегом попадут в коммуну)</div>
          <div class="flex flex-wrap items-center gap-2">
            {#if settingsDraft.product_tag}
              <span class="rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-sm">
                #{settingsDraft.product_tag.name}
              </span>
              <Button color="ghost" size="sm" on:click={clearDraftTag}>Сбросить</Button>
            {:else}
              <span class="text-sm text-slate-500 dark:text-zinc-400">Тег не выбран</span>
            {/if}
          </div>
          <input
            bind:value={settingsTagSearch}
            placeholder="Поиск тега..."
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          />
          <div class="max-h-48 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
            {#if normalizedTagCreateValue && !hasExactTagMatch}
              <div class="flex items-center justify-between gap-2 px-3 py-2 bg-slate-50 dark:bg-zinc-900/60">
                <div class="min-w-0 text-sm">
                  <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">
                    Добавить тег #{normalizedTagCreateValue}
                  </div>
                  <div class="text-xs text-slate-500 dark:text-zinc-400">
                    Создаст тег в системе и выберет его для комуны
                  </div>
                </div>
                <Button
                  size="sm"
                  on:click={createTagAndChooseDraft}
                  disabled={settingsTagCreating || settingsSaving}
                >
                  {settingsTagCreating ? '...' : 'Добавить'}
                </Button>
              </div>
            {/if}
            {#if filteredTagOptions.length}
              {#each filteredTagOptions as tag}
                <div class="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                  <div class="min-w-0">
                    <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">{tag.name}</div>
                    {#if tag.lemma}
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">{tag.lemma}</div>
                    {/if}
                  </div>
                  <Button size="sm" on:click={() => chooseDraftTag(tag)} disabled={settingsTagCreating || settingsSaving}>Выбрать</Button>
                </div>
              {/each}
            {:else}
              <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                {normalizedTagCreateValue && !hasExactTagMatch ? 'Можно добавить новый тег выше' : 'Ничего не найдено'}
              </div>
            {/if}
          </div>
        </div>

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

        <label class="flex flex-col gap-1">
          <span class="text-sm text-slate-700 dark:text-zinc-300">Приветственный пост (ID или ссылка на пост)</span>
          <input
            bind:value={settingsDraft.welcome_post_ref}
            placeholder="/b/post/123... или 123"
            class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
          />
        </label>
      </div>

      <div class="flex justify-end gap-2 pt-2">
        <Button on:click={saveSettings} disabled={settingsSaving || settingsLogoUploading}>
          {settingsSaving ? 'Сохраняем...' : 'Сохранить'}
        </Button>
      </div>
    {/if}
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
</style>
