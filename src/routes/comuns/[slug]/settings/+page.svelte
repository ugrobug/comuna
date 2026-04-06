<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { onMount } from 'svelte'
  import { Button, Modal, toast } from 'mono-svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import TemplateTypeDropdown from '$lib/components/comuns/TemplateTypeDropdown.svelte'
  import {
    buildComunUrl,
    buildTagsEnsureUrl,
    type BackendComun,
    type BackendComunCategory,
    type BackendComunGlossaryTerm,
    type BackendTag,
  } from '$lib/api/backend'
  import { siteToken, uploadSiteImage } from '$lib/siteAuth'
  import {
    normalizeAllowedPostTemplateTypeOverrides,
    normalizeAllowedPostTemplateTypes,
    type PostTemplateCode,
  } from '$lib/postTemplates'
  import { env } from '$env/dynamic/public'

  export let data

  const slug = String(data?.slug ?? '')

  let comun: BackendComun | null = null
  let settingsDraft: BackendComun | null = null
  let settingsLoading = true
  let settingsSaving = false
  let settingsLogoUploading = false
  let settingsTagCreating = false
  let settingsCategoryCreating = false
  let deleteComunOpen = false
  let deleteComunSaving = false
  let settingsError = ''
  let lastAuthRefreshToken: string | null = null

  let settingsTagSearch = ''
  let settingsBlockedTagSearch = ''
  let settingsCategorySearch = ''
  let settingsGlossarySearch = ''
  let settingsUserSearch = ''
  let settingsAuthorSearch = ''
  let settingsCategoryOptions: BackendComunCategory[] = []
  type ComunTagOption = BackendTag & { id: number }
  type ComunUserOption = { id: number; username: string; display_name?: string | null }
  type ComunAuthorOption = {
    id: number
    username: string
    title?: string | null
    avatar_url?: string | null
  }
  type ComunTelegramChannelOption = {
    id: number
    username: string
    title?: string | null
    channel_url?: string | null
    avatar_url?: string | null
  }
  type TemplateTypeOption = { value: PostTemplateCode; label: string }
  type GlossaryDraftTerm = BackendComunGlossaryTerm & { localId: string }
  type ComunSettingsTabKey = 'description' | 'availability' | 'moderation' | 'categories' | 'rules'
  const fallbackTemplateTypeOptions: TemplateTypeOption[] = [
    { value: 'basic', label: 'Пост' },
    { value: 'movie_review', label: 'Кинообзор' },
    { value: 'post_vote_poll', label: 'Голосование за посты' },
    { value: 'music_release', label: 'Музыкальный релиз' },
  ]
  const comunSettingsTabs: Array<{ value: ComunSettingsTabKey; label: string }> = [
    { value: 'description', label: 'Описание' },
    { value: 'availability', label: 'Доступность' },
    { value: 'moderation', label: 'Модерирование' },
    { value: 'categories', label: 'Категории и шаблоны' },
    { value: 'rules', label: 'Правила' },
  ]
  const allowedTemplateCodes = new Set<PostTemplateCode>([
    'basic',
    'movie_review',
    'post_vote_poll',
    'music_release',
  ])
  let settingsTagOptions: ComunTagOption[] = []
  let settingsUserOptions: ComunUserOption[] = []
  let settingsAuthorOptions: ComunAuthorOption[] = []
  let settingsTemplateTypeOptions: TemplateTypeOption[] = fallbackTemplateTypeOptions
  let settingsTelegramChannelOptions: ComunTelegramChannelOption[] = []
  let settingsGlossaryTerms: GlossaryDraftTerm[] = []
  let settingsLogoInput: HTMLInputElement | null = null
  let settingsTab: ComunSettingsTabKey = 'description'

  const settingsTabClass = (activeTab: ComunSettingsTabKey, tab: ComunSettingsTabKey) =>
    `rounded-full px-3 py-2 text-sm font-medium transition-colors ${
      activeTab === tab
        ? 'bg-slate-900 text-white dark:bg-white dark:text-zinc-900'
        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700'
    }`

  const cloneComun = (value: BackendComun | null): BackendComun | null =>
    value ? JSON.parse(JSON.stringify(value)) : null

  const createGlossaryLocalId = () =>
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

  const normalizeGlossaryTerms = (
    terms: Array<BackendComunGlossaryTerm | GlossaryDraftTerm> | null | undefined
  ): GlossaryDraftTerm[] =>
    (terms ?? [])
      .map((term) => ({
        id: Number(term?.id ?? 0) || 0,
        localId: (term as GlossaryDraftTerm)?.localId || createGlossaryLocalId(),
        term: String(term?.term ?? '').trim(),
        slug: String(term?.slug ?? '').trim(),
        definition: String(term?.definition ?? '').trim(),
        sort_order: Number(term?.sort_order ?? 0) || 0,
      }))
      .filter((term) => term.term || term.definition)

  const normalizeIds = (values: Array<number | null | undefined>) =>
    Array.from(
      new Set(
        values
          .filter((value): value is number => Number.isFinite(value as number) && Number(value) > 0)
          .map(Number)
      )
    ).sort((a, b) => a - b)

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

  const comunExcludedAuthorIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.excluded_author_ids as number[] | undefined) ??
        (value?.excluded_authors ?? []).map((author) => author.id ?? 0)) as number[]
    )

  const comunBlockedTagIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.blocked_tag_ids as number[] | undefined) ??
        (value?.excluded_tag_ids as number[] | undefined) ??
        (value?.blocked_tags ?? value?.excluded_tags ?? []).map((tag) => tag.id ?? 0)) as number[]
    )

  const comunSourceTagIds = (value: BackendComun | null) =>
    normalizeIds(
      ((value?.source_tag_ids as number[] | undefined) ??
        (value?.source_tags ?? (value?.product_tag ? [value.product_tag] : [])).map((tag) => tag.id ?? 0)) as number[]
    )

  const comunAllowedTemplateTypes = (value: BackendComun | null) =>
    normalizeAllowedPostTemplateTypes(
      value?.allowed_template_types ?? value?.allowed_post_templates
    )

  const comunCategoryTemplateTypes = (category?: BackendComunCategory | null) =>
    normalizeAllowedPostTemplateTypeOverrides(category?.category_allowed_template_types)

  const comunCategoryTemplateTypesById = (value: BackendComun | null) => {
    const entries = (value?.categories ?? [])
      .filter((category) => Number(category?.id) > 0)
      .map((category) => [String(category.id), comunCategoryTemplateTypes(category)] as const)
      .sort((a, b) => Number(a[0]) - Number(b[0]))
    return Object.fromEntries(entries)
  }

  const comunCategoryOnlyModeratorIds = (value: BackendComun | null) =>
    normalizeIds(
      (value?.categories ?? [])
        .filter((category) => Boolean(category?.only_moderators_can_post))
        .map((category) => category.id ?? 0)
    )

  const normalizeTemplateTypeOptions = (value: unknown): TemplateTypeOption[] => {
    const source = Array.isArray(value) ? value : []
    const normalized: TemplateTypeOption[] = []
    const seen = new Set<PostTemplateCode>()
    for (const item of source) {
      const templateValueRaw = String((item as any)?.value ?? '')
        .trim()
        .toLowerCase()
      const templateLabel = String((item as any)?.label ?? '').trim()
      const templateValue = allowedTemplateCodes.has(templateValueRaw as PostTemplateCode)
        ? (templateValueRaw as PostTemplateCode)
        : null
      if (!templateValue || !templateLabel || seen.has(templateValue)) continue
      seen.add(templateValue)
      normalized.push({ value: templateValue, label: templateLabel })
    }
    return normalized.length ? normalized : fallbackTemplateTypeOptions
  }

  const settingsComparable = (value: BackendComun | null) =>
    JSON.stringify({
      name: (value?.name ?? '').trim(),
      website_url: (value?.website_url ?? '').trim(),
      logo_url: (value?.logo_url ?? '').trim(),
      product_description: (value?.product_description ?? '').trim(),
      rules_text: (value?.rules_text ?? '').trim(),
      target_audience: (value?.target_audience ?? '').trim(),
      glossary_enabled: Boolean(value?.glossary_enabled),
      minimum_author_rating_to_post: Math.max(
        Number(value?.minimum_author_rating_to_post ?? 0) || 0,
        0
      ),
      only_moderators_can_post: Boolean(value?.only_moderators_can_post),
      forbid_external_links: Boolean(value?.forbid_external_links),
      hide_from_home: Boolean(value?.hide_from_home),
      hide_from_fresh: Boolean(value?.hide_from_fresh),
      source_tag_ids: comunSourceTagIds(value),
      allowed_template_types: comunAllowedTemplateTypes(value),
      category_template_types_by_id: comunCategoryTemplateTypesById(value),
      category_only_moderators_can_post_ids: comunCategoryOnlyModeratorIds(value),
      category_ids: comunCategoryIds(value),
      moderator_ids: comunModeratorIds(value),
      excluded_author_ids: comunExcludedAuthorIds(value),
      blocked_tag_ids: comunBlockedTagIds(value),
      telegram_source_author_id: Number(
        value?.telegram_source_author_id ?? value?.telegram_source_author?.id ?? 0
      ),
      telegram_channel_username: String(value?.telegram_channel_username ?? '').trim().toLowerCase(),
      welcome_post_ref: String(value?.welcome_post_ref ?? value?.welcome_post_id ?? '').trim(),
    })

  const comunWelcomePostRef = (value: BackendComun | null) =>
    String(value?.welcome_post_ref ?? value?.welcome_post_id ?? '').trim()

  const canModerate = () => Boolean(comun?.can_moderate && $siteToken)
  const canManageComunModerators = () => Boolean(comun?.can_manage_moderators && $siteToken)
  const canDeleteComun = () => Boolean(comun?.can_manage_moderators && $siteToken)

  const userDisplayName = (
    user?: { username?: string | null; display_name?: string | null } | null
  ) => {
    const displayName = (user?.display_name ?? '').trim()
    if (displayName) return displayName
    const username = (user?.username ?? '').trim()
    return username ? `@${username}` : 'Пользователь'
  }

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const refreshComunManage = async () => {
    if (!slug) return
    if (!$siteToken) {
      settingsLoading = false
      settingsError = 'Нужна авторизация'
      comun = null
      settingsDraft = null
      return
    }
    settingsLoading = true
    settingsError = ''
    try {
      const comunUrl = new URL(buildComunUrl(slug), window.location.origin)
      comunUrl.searchParams.set('_', String(Date.now()))
      const response = await fetch(comunUrl.toString(), {
        headers: { Authorization: `Bearer ${$siteToken}` },
        cache: 'no-store',
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        if (response.status === 401) throw new Error('Нужна авторизация')
        if (response.status === 404) throw new Error('Сообщество не найдено')
        throw new Error(payload?.error || 'Не удалось загрузить настройки сообщества')
      }
      if (!payload?.comun) {
        throw new Error('Сообщество не найдено')
      }
      comun = payload.comun
      settingsDraft = cloneComun(payload.comun)
      settingsGlossaryTerms = normalizeGlossaryTerms(payload.comun?.glossary_terms)
      settingsCategoryOptions = payload.comun?.options?.categories ?? []
      settingsTagOptions = payload.comun?.options?.tags ?? []
      settingsUserOptions = payload.comun?.options?.users ?? []
      settingsAuthorOptions = payload.comun?.options?.authors ?? []
      settingsTelegramChannelOptions = payload.comun?.options?.telegram_channels ?? []
      settingsTemplateTypeOptions = normalizeTemplateTypeOptions(payload.comun?.options?.template_types)
      if (!payload.comun?.can_moderate) {
        settingsError = 'Настройки доступны только модераторам сообщества'
      }
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Ошибка загрузки'
      comun = comun ?? null
      settingsDraft = settingsDraft ?? null
    } finally {
      settingsLoading = false
    }
  }

  const removeDraftCategory = (categoryId: number) => {
    if (!settingsDraft) return
    settingsDraft = {
      ...settingsDraft,
      category_ids: comunCategoryIds(settingsDraft).filter((id) => id !== categoryId),
      categories: (settingsDraft.categories ?? []).filter((category) => category.id !== categoryId),
    }
    settingsCategoryOptions = (settingsCategoryOptions ?? []).filter(
      (category) => category.id !== categoryId
    )
  }

  const setDraftCategoryOnlyModeratorIds = (ids: number[]) => {
    if (!settingsDraft) return
    const restrictedIds = new Set(normalizeIds(ids))
    settingsDraft = {
      ...settingsDraft,
      categories: (settingsDraft.categories ?? []).map((category) => ({
        ...category,
        only_moderators_can_post: restrictedIds.has(Number(category.id)),
      })),
    }
  }

  const toggleDraftCategoryOnlyModerators = (categoryId: number) => {
    if (!settingsDraft) return
    const current = new Set(comunCategoryOnlyModeratorIds(settingsDraft))
    if (current.has(categoryId)) current.delete(categoryId)
    else current.add(categoryId)
    setDraftCategoryOnlyModeratorIds(Array.from(current))
  }

  const setDraftTelegramChannel = (
    channelUsername: string,
    telegramSourceAuthor?: ComunTelegramChannelOption | null
  ) => {
    if (!settingsDraft) return
    settingsDraft = {
      ...settingsDraft,
      telegram_channel_username: channelUsername,
      telegram_source_author_id: telegramSourceAuthor?.id ?? null,
      telegram_source_author: telegramSourceAuthor
        ? {
            id: telegramSourceAuthor.id,
            username: telegramSourceAuthor.username,
            title: telegramSourceAuthor.title ?? null,
            channel_url: telegramSourceAuthor.channel_url ?? null,
            avatar_url: telegramSourceAuthor.avatar_url ?? null,
          }
        : null,
    }
  }

  const addDraftGlossaryTerm = () => {
    settingsDraft = {
      ...(settingsDraft ?? {}),
      glossary_enabled: true,
    } as BackendComun
    settingsGlossaryTerms = [
      ...settingsGlossaryTerms,
      {
        id: 0,
        localId: createGlossaryLocalId(),
        term: '',
        slug: '',
        definition: '',
        sort_order: settingsGlossaryTerms.length,
      },
    ]
  }

  const updateDraftGlossaryTerm = (
    localId: string,
    field: 'term' | 'definition',
    value: string
  ) => {
    settingsGlossaryTerms = settingsGlossaryTerms.map((term, index) =>
      term.localId === localId
        ? {
            ...term,
            [field]: value,
            sort_order: index,
          }
        : { ...term, sort_order: index }
    )
  }

  const removeDraftGlossaryTerm = (localId: string) => {
    settingsGlossaryTerms = settingsGlossaryTerms
      .filter((term) => term.localId !== localId)
      .map((term, index) => ({ ...term, sort_order: index }))
  }

  const onGlossaryTermTitleInput = (localId: string, event: Event) => {
    const target = event.currentTarget as HTMLInputElement | null
    updateDraftGlossaryTerm(localId, 'term', target?.value ?? '')
  }

  const onGlossaryTermDefinitionInput = (localId: string, event: Event) => {
    const target = event.currentTarget as HTMLTextAreaElement | null
    updateDraftGlossaryTerm(localId, 'definition', target?.value ?? '')
  }

  const onTelegramChannelInput = (event: Event) => {
    const target = event.currentTarget as HTMLInputElement | null
    const nextValue = target?.value ?? ''
    setDraftTelegramChannel(nextValue, null)
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

  const setDraftExcludedAuthorIds = (ids: number[]) => {
    if (!settingsDraft) return
    const normalizedIds = normalizeIds(ids)
    const byId = new Map<number, ComunAuthorOption>()
    for (const author of settingsAuthorOptions) byId.set(author.id, author)
    for (const author of settingsDraft.excluded_authors ?? []) {
      byId.set(author.id, author)
    }
    settingsDraft = {
      ...settingsDraft,
      excluded_author_ids: normalizedIds,
      excluded_authors: normalizedIds.map((id) => {
        const author = byId.get(id)
        return {
          id,
          username: author?.username ?? String(id),
          title: author?.title ?? null,
          avatar_url: author?.avatar_url ?? null,
        }
      }),
    }
  }

  const addDraftExcludedAuthor = (authorId: number) => {
    if (!settingsDraft) return
    setDraftExcludedAuthorIds([...comunExcludedAuthorIds(settingsDraft), authorId])
  }

  const removeDraftExcludedAuthor = (authorId: number) => {
    if (!settingsDraft) return
    setDraftExcludedAuthorIds(comunExcludedAuthorIds(settingsDraft).filter((id) => id !== authorId))
  }

  const setDraftBlockedTagIds = (ids: number[]) => {
    if (!settingsDraft) return
    const normalizedIds = normalizeIds(ids)
    const byId = new Map<number, ComunTagOption>()
    for (const tag of settingsTagOptions) byId.set(tag.id, tag)
    for (const tag of settingsDraft.blocked_tags ?? settingsDraft.excluded_tags ?? []) {
      byId.set(tag.id, tag)
    }
    const selectedTags = normalizedIds
      .map((id) => byId.get(id))
      .filter(Boolean)
      .map((tag) => ({ id: tag!.id, name: tag!.name, lemma: tag!.lemma ?? null }))
    settingsDraft = {
      ...settingsDraft,
      blocked_tag_ids: normalizedIds,
      excluded_tag_ids: normalizedIds,
      blocked_tags: selectedTags,
      excluded_tags: selectedTags,
    }
  }

  const addDraftBlockedTag = (tagId: number) => {
    if (!settingsDraft) return
    setDraftBlockedTagIds([...comunBlockedTagIds(settingsDraft), tagId])
  }

  const removeDraftBlockedTag = (tagId: number) => {
    if (!settingsDraft) return
    setDraftBlockedTagIds(comunBlockedTagIds(settingsDraft).filter((id) => id !== tagId))
  }

  const setDraftSourceTagIds = (ids: number[]) => {
    if (!settingsDraft) return
    const normalizedIds = normalizeIds(ids).slice(0, 5)
    const byId = new Map<number, ComunTagOption>()
    for (const tag of settingsTagOptions) byId.set(tag.id, tag)
    for (const tag of settingsDraft.source_tags ?? (settingsDraft.product_tag ? [settingsDraft.product_tag] : [])) {
      byId.set(tag.id, tag)
    }
    const selectedTags = normalizedIds
      .map((id) => byId.get(id))
      .filter(Boolean)
      .map((tag) => ({ id: tag!.id, name: tag!.name, lemma: tag!.lemma ?? null }))
    settingsDraft = {
      ...settingsDraft,
      source_tag_ids: normalizedIds,
      source_tags: selectedTags,
      product_tag_id: selectedTags[0]?.id ?? null,
      product_tag: selectedTags[0] ?? null,
    }
  }

  const addDraftSourceTag = (tagId: number) => {
    if (!settingsDraft) return
    setDraftSourceTagIds([...comunSourceTagIds(settingsDraft), tagId])
  }

  const removeDraftSourceTag = (tagId: number) => {
    if (!settingsDraft) return
    setDraftSourceTagIds(comunSourceTagIds(settingsDraft).filter((id) => id !== tagId))
  }

  const setDraftAllowedTemplateTypes = (values: PostTemplateCode[]) => {
    if (!settingsDraft) return
    const normalizedValues = normalizeAllowedPostTemplateTypes(values)
    settingsDraft = {
      ...settingsDraft,
      allowed_template_types: normalizedValues,
      categories: (settingsDraft.categories ?? []).map((category) =>
        comunCategoryTemplateTypes(category).length
          ? category
          : {
              ...category,
              allowed_template_types: normalizedValues,
              inherits_comun_template_types: true,
            }
      ),
    }
  }

  const setDraftCategoryTemplateTypes = (categoryId: number, values: PostTemplateCode[]) => {
    if (!settingsDraft) return
    const normalizedValues = normalizeAllowedPostTemplateTypeOverrides(values)
    settingsDraft = {
      ...settingsDraft,
      categories: (settingsDraft.categories ?? []).map((category) =>
        category.id === categoryId
          ? {
              ...category,
              category_allowed_template_types: normalizedValues,
              allowed_template_types: normalizedValues.length
                ? normalizedValues
                : comunAllowedTemplateTypes(settingsDraft),
              inherits_comun_template_types: normalizedValues.length === 0,
            }
          : category
      ),
    }
    settingsCategoryOptions = (settingsCategoryOptions ?? []).map((category) =>
      category.id === categoryId
        ? {
            ...category,
            category_allowed_template_types: normalizedValues,
            allowed_template_types: normalizedValues.length
              ? normalizedValues
              : comunAllowedTemplateTypes(settingsDraft),
            inherits_comun_template_types: normalizedValues.length === 0,
          }
        : category
    )
  }

  const clearDraftLogo = () => {
    if (!settingsDraft) return
    settingsDraft = { ...settingsDraft, logo_url: '' }
  }

  const toggleDraftHideFromHome = () => {
    if (!settingsDraft) return
    settingsDraft = {
      ...settingsDraft,
      hide_from_home: !Boolean(settingsDraft.hide_from_home),
    }
  }

  const toggleDraftHideFromFresh = () => {
    if (!settingsDraft) return
    settingsDraft = {
      ...settingsDraft,
      hide_from_fresh: !Boolean(settingsDraft.hide_from_fresh),
    }
  }

  const normalizeTagInput = (value: string) =>
    value.trim().replace(/^#+/, '').replace(/\s+/g, ' ').trim()

  const normalizeCategoryInput = (value: string) =>
    value.trim().replace(/\s+/g, ' ').trim()

  const formatRatingValue = (value?: number | null) => {
    const normalized = Math.max(Number(value ?? 0) || 0, 0)
    return new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(normalized)
  }

  $: normalizedTagSearch = settingsTagSearch.trim().toLowerCase()
  $: sourceTagIdSet = new Set<number>(comunSourceTagIds(settingsDraft))
  $: normalizedTagCreateValue = normalizeTagInput(settingsTagSearch)
  $: hasExactTagMatch = (settingsTagOptions ?? []).some((tag) => {
    const needle = normalizedTagCreateValue.toLowerCase()
    if (!needle) return false
    return [tag.name, tag.lemma ?? '']
      .map((value) => normalizeTagInput(value).toLowerCase())
      .some((value) => value === needle)
  })
  $: normalizedCategorySearch = settingsCategorySearch.trim().toLowerCase()
  $: normalizedCategoryCreateValue = normalizeCategoryInput(settingsCategorySearch)
  $: hasExactCategoryMatch = (settingsCategoryOptions ?? []).some((category) => {
    const needle = normalizedCategoryCreateValue.toLowerCase()
    if (!needle) return false
    return normalizeCategoryInput(category.name).toLowerCase() === needle
  })
  $: filteredCategoryOptions = (settingsCategoryOptions ?? [])
    .filter((category) => {
      if (!normalizedCategorySearch) return true
      return [category.name, category.description ?? ''].some((value) =>
        value.toLowerCase().includes(normalizedCategorySearch)
      )
    })
    .slice(0, 40)
  $: normalizedGlossarySearch = settingsGlossarySearch.trim().toLowerCase()
  $: filteredGlossaryTerms = settingsGlossaryTerms.filter((term) => {
    if (!normalizedGlossarySearch) return true
    return [term.term, term.definition].some((value) =>
      value.toLowerCase().includes(normalizedGlossarySearch)
    )
  })
  $: filteredTagOptions = (settingsTagOptions ?? [])
    .filter((tag) => {
      if (!normalizedTagSearch) return false
      return [tag.name, tag.lemma ?? ''].some((value) =>
        value.toLowerCase().includes(normalizedTagSearch)
      )
    })
    .slice(0, 30)
  $: normalizedBlockedTagSearch = settingsBlockedTagSearch.trim().toLowerCase()
  $: blockedTagIdSet = new Set<number>(comunBlockedTagIds(settingsDraft))
  $: filteredBlockedTagOptions = (settingsTagOptions ?? [])
    .filter((tag) => {
      if (!normalizedBlockedTagSearch) return false
      return [tag.name, tag.lemma ?? ''].some((value) =>
        value.toLowerCase().includes(normalizedBlockedTagSearch)
      )
    })
    .slice(0, 30)
  $: normalizedUserSearch = settingsUserSearch.trim().toLowerCase()
  $: draftModeratorIdSet = new Set<number>(comunModeratorIds(settingsDraft))
  $: draftExcludedAuthorIdSet = new Set<number>(comunExcludedAuthorIds(settingsDraft))
  $: draftGlossaryTermsComparable = JSON.stringify(
    settingsGlossaryTerms.map((term) => ({
      id: Number(term.id) || 0,
      term: term.term.trim(),
      definition: term.definition.trim(),
    }))
  )
  $: comunGlossaryTermsComparable = JSON.stringify(
    normalizeGlossaryTerms(comun?.glossary_terms).map((term) => ({
      id: Number(term.id) || 0,
      term: term.term.trim(),
      definition: term.definition.trim(),
    }))
  )
  $: settingsHasChanges =
    settingsComparable(settingsDraft) !== settingsComparable(comun) ||
    draftGlossaryTermsComparable !== comunGlossaryTermsComparable
  $: filteredUserOptions = (settingsUserOptions ?? [])
    .filter((user) => {
      if (!normalizedUserSearch) return false
      return [user.username, user.display_name ?? ''].some((value) =>
        value.toLowerCase().includes(normalizedUserSearch)
      )
    })
    .slice(0, 50)
  $: normalizedAuthorSearch = settingsAuthorSearch.trim().toLowerCase()
  $: filteredAuthorOptions = (settingsAuthorOptions ?? [])
    .filter((author) => {
      if (!normalizedAuthorSearch) return false
      return [author.username, author.title ?? ''].some((value) =>
        value.toLowerCase().includes(normalizedAuthorSearch)
      )
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
  $: selectedSourceTags =
    (settingsDraft?.source_tags?.length ? settingsDraft.source_tags : settingsDraft?.product_tag ? [settingsDraft.product_tag] : []) ?? []
  $: selectedBlockedTags =
    (settingsDraft?.blocked_tags?.length ? settingsDraft.blocked_tags : settingsDraft?.excluded_tags) ?? []
  $: selectedExcludedAuthors = comunExcludedAuthorIds(settingsDraft).map((id) => {
    const fromOptions = settingsAuthorOptions.find((author) => author.id === id)
    if (fromOptions) return fromOptions
    const fromDraft = settingsDraft?.excluded_authors?.find((author) => author.id === id)
    return {
      id,
      username: fromDraft?.username ?? String(id),
      title: fromDraft?.title ?? null,
      avatar_url: fromDraft?.avatar_url ?? null,
    }
  })
  $: selectedTelegramSourceAuthor =
    settingsDraft?.telegram_source_author ??
    (settingsTelegramChannelOptions.find(
      (author) => author.id === Number(settingsDraft?.telegram_source_author_id ?? 0)
    ) ??
      null)
  $: normalizedTelegramChannelUsername = String(
    settingsDraft?.telegram_channel_username ??
      selectedTelegramSourceAuthor?.username ??
      ''
  ).trim()
  $: pendingTelegramChannelUsername =
    normalizedTelegramChannelUsername && !selectedTelegramSourceAuthor
      ? normalizedTelegramChannelUsername
      : ''

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
      if (existingIndex >= 0) nextOptions[existingIndex] = nextTag
      else nextOptions.push(nextTag)
      settingsTagOptions = nextOptions.sort((a, b) => a.name.localeCompare(b.name, 'ru'))
      addDraftSourceTag(nextTag.id)
      settingsTagSearch = ''
      toast({
        content: payload.created ? 'Тег добавлен в сообщество' : 'Тег добавлен в сообщество',
        type: 'success',
      })
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Не удалось добавить тег',
        type: 'error',
      })
    } finally {
      settingsTagCreating = false
    }
  }

  const createCategoryAndSelectDraft = async () => {
    const categoryName = normalizeCategoryInput(settingsCategorySearch)
    if (!slug || !settingsDraft || !categoryName || settingsCategoryCreating) return
    settingsCategoryCreating = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          category_ids:
            settingsDraft.category_ids ??
            (settingsDraft.categories ?? []).map((category) => category.id),
          category_names: [categoryName],
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось добавить категорию')
      }
      const nextComun = payload.comun ?? comun
      comun = nextComun
      settingsDraft = cloneComun(nextComun)
      settingsCategoryOptions =
        payload.comun?.options?.categories ?? payload.comun?.categories ?? settingsCategoryOptions
      await refreshComunManage()
      const createdCategory = (settingsCategoryOptions ?? []).find(
        (category) =>
          normalizeCategoryInput(category.name).toLowerCase() === categoryName.toLowerCase()
      )
      if (!createdCategory) {
        throw new Error('Категория не появилась после сохранения. Попробуйте еще раз.')
      }
      if (settingsDraft) {
        settingsDraft = {
          ...settingsDraft,
          category_ids: normalizeIds([...comunCategoryIds(settingsDraft), createdCategory.id]),
        }
      }
      settingsCategorySearch = ''
      toast({ content: 'Категория создана внутри сообщества', type: 'success' })
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Не удалось добавить категорию'
    } finally {
      settingsCategoryCreating = false
    }
  }

  const saveSettings = async () => {
    if (!slug || !settingsDraft) return
    settingsSaving = true
    settingsError = ''
    try {
      const welcomePostRef = comunWelcomePostRef(settingsDraft)
      const currentWelcomePostRef = comunWelcomePostRef(comun)
      const response = await fetch(buildComunUrl(slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          name: canManageComunModerators() ? settingsDraft.name ?? '' : undefined,
          website_url: settingsDraft.website_url ?? '',
          logo_url: settingsDraft.logo_url ?? '',
          product_description: settingsDraft.product_description ?? '',
          rules_text: settingsDraft.rules_text ?? '',
          target_audience: settingsDraft.target_audience ?? '',
          glossary_enabled: Boolean(settingsDraft.glossary_enabled),
          glossary_terms: settingsGlossaryTerms.map((term, index) => ({
            id: Number(term.id) || undefined,
            term: term.term.trim(),
            definition: term.definition.trim(),
            sort_order: index,
          })),
          minimum_author_rating_to_post: Math.max(
            Number(settingsDraft.minimum_author_rating_to_post ?? 0) || 0,
            0
          ),
          only_moderators_can_post: Boolean(settingsDraft.only_moderators_can_post),
          forbid_external_links: Boolean(settingsDraft.forbid_external_links),
          allowed_template_types: comunAllowedTemplateTypes(settingsDraft),
          category_template_types_by_id: comunCategoryTemplateTypesById(settingsDraft),
          category_only_moderators_can_post_ids: comunCategoryOnlyModeratorIds(settingsDraft),
          hide_from_home: canManageComunModerators() ? Boolean(settingsDraft.hide_from_home) : undefined,
          hide_from_fresh: canManageComunModerators() ? Boolean(settingsDraft.hide_from_fresh) : undefined,
          moderator_ids: canManageComunModerators() ? comunModeratorIds(settingsDraft) : undefined,
          excluded_author_ids: comunExcludedAuthorIds(settingsDraft),
          source_tag_ids: comunSourceTagIds(settingsDraft),
          blocked_tag_ids: comunBlockedTagIds(settingsDraft),
          telegram_source_author_id:
            Number(
              settingsDraft.telegram_source_author_id ?? settingsDraft.telegram_source_author?.id ?? 0
            ) || undefined,
          telegram_channel_username: settingsDraft.telegram_channel_username ?? '',
          category_ids:
            settingsDraft.category_ids ??
            (settingsDraft.categories ?? []).map((category) => category.id),
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
      settingsGlossaryTerms = normalizeGlossaryTerms(comun?.glossary_terms)
      settingsCategoryOptions =
        payload.comun?.options?.categories ?? payload.comun?.categories ?? settingsCategoryOptions
      settingsTagOptions = payload.comun?.options?.tags ?? settingsTagOptions
      settingsUserOptions = payload.comun?.options?.users ?? settingsUserOptions
      settingsAuthorOptions = payload.comun?.options?.authors ?? settingsAuthorOptions
      settingsTelegramChannelOptions =
        payload.comun?.options?.telegram_channels ?? settingsTelegramChannelOptions
      settingsTemplateTypeOptions = normalizeTemplateTypeOptions(
        payload.comun?.options?.template_types
      )
      toast({ content: 'Настройки сообщества сохранены', type: 'success' })
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
    if (!slug || !canDeleteComun() || deleteComunSaving) return
    deleteComunSaving = true
    settingsError = ''
    try {
      const response = await fetch(buildComunUrl(slug), {
        method: 'DELETE',
        headers: authHeaders(),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось удалить сообщество')
      }
      deleteComunOpen = false
      toast({ content: 'Сообщество удалено', type: 'success' })
      await goto('/comuns')
    } catch (error) {
      settingsError = error instanceof Error ? error.message : 'Не удалось удалить сообщество'
    } finally {
      deleteComunSaving = false
    }
  }

  const pickSettingsLogo = () => {
    if (!canModerate()) return
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
      toast({
        content: 'Логотип загружен. Сохраните настройки для применения.',
        type: 'success',
      })
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Не удалось загрузить логотип',
        type: 'error',
      })
    } finally {
      settingsLogoUploading = false
      if (input) input.value = ''
    }
  }

  const openLogin = () => {
    const next = encodeURIComponent($page.url.pathname + $page.url.search)
    goto(`/account?next=${next}`)
  }

  $: if (browser && $siteToken && $siteToken !== lastAuthRefreshToken) {
    lastAuthRefreshToken = $siteToken
    void refreshComunManage()
  }

  $: if (!$siteToken) {
    lastAuthRefreshToken = null
  }

  onMount(() => {
    if (!$siteToken) {
      settingsLoading = false
      settingsError = 'Нужна авторизация'
      return
    }
    void refreshComunManage()
  })

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: pageTitle = comun?.name
    ? `Настройки сообщества ${comun.name} — ${siteTitle}`
    : `Настройки сообщества — ${siteTitle}`
</script>

<div class="flex w-full max-w-none flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="min-w-0">
      <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
        Сообщество
      </div>
      <Header noMargin>Настройки сообщества</Header>
      {#if comun?.name}
        <div class="text-sm text-slate-600 dark:text-zinc-400 truncate">{comun.name}</div>
      {/if}
    </div>
    <a
      href={slug ? `/comuns/${encodeURIComponent(slug)}` : '/comuns/'}
      class="inline-flex items-center rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-zinc-800/60"
    >
      Назад к сообществу
    </a>
  </div>

  {#if settingsError}
    <div class="rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50 dark:bg-rose-950/20 px-3 py-2 text-sm text-rose-700 dark:text-rose-300">
      {settingsError}
    </div>
  {/if}

  {#if settingsLoading}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-sm text-slate-500 dark:text-zinc-400">
      Загрузка настроек...
    </div>
  {:else if !$siteToken}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 flex flex-col gap-3">
      <div class="text-sm text-slate-700 dark:text-zinc-300">
        Чтобы открыть настройки сообщества, нужно войти в аккаунт.
      </div>
      <div>
        <Button on:click={openLogin}>Войти</Button>
      </div>
    </div>
  {:else if !canModerate()}
    <div class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-6 text-sm text-slate-700 dark:text-zinc-300">
      Настройки доступны только создателю или назначенным модераторам этого сообщества.
    </div>
  {:else if settingsDraft}
    <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-5 sm:p-6">
      <div class="mb-5 flex flex-wrap gap-2">
        {#each comunSettingsTabs as tab}
          <button
            type="button"
            class={settingsTabClass(settingsTab, tab.value)}
            on:click={() => (settingsTab = tab.value)}
          >
            {tab.label}
          </button>
        {/each}
      </div>

      <div class="grid gap-4">
        {#if settingsTab === 'description'}
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
            <input
              bind:value={settingsDraft.website_url}
              type="url"
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
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
                <div class="text-xs text-slate-500 dark:text-zinc-400">PNG, JPG, WEBP, GIF</div>
              </div>
              <div class="flex flex-wrap gap-2 justify-end">
                <Button size="sm" on:click={pickSettingsLogo} disabled={settingsSaving || settingsLogoUploading}>
                  {settingsDraft.logo_url ? 'Заменить' : 'Выбрать файл'}
                </Button>
                {#if settingsDraft.logo_url}
                  <Button
                    color="ghost"
                    size="sm"
                    on:click={clearDraftLogo}
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
            <textarea
              bind:value={settingsDraft.product_description}
              rows="4"
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            ></textarea>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-700 dark:text-zinc-300">Для кого</span>
            <textarea
              bind:value={settingsDraft.target_audience}
              rows="2"
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            ></textarea>
          </label>

          <label class="flex flex-col gap-1">
            <span class="text-sm text-slate-700 dark:text-zinc-300">Приветственный пост (ID или ссылка на пост)</span>
            <input
              bind:value={settingsDraft.welcome_post_ref}
              placeholder="/b/post/123... или 123"
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
          </label>
        {:else if settingsTab === 'availability'}
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

          {#if !(settingsDraft.categories ?? []).length}
            <label class="flex items-start gap-2 cursor-pointer rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
              <input
                type="checkbox"
                class="mt-0.5"
                checked={Boolean(settingsDraft.only_moderators_can_post)}
                on:change={() =>
                  (settingsDraft = {
                    ...settingsDraft,
                    only_moderators_can_post: !Boolean(settingsDraft.only_moderators_can_post),
                  })}
              />
              <span class="min-w-0">
                <span class="block text-sm text-slate-900 dark:text-zinc-100">
                  Писать в сообщество могут только администраторы и модераторы
                </span>
              </span>
            </label>
          {/if}

          {#if (settingsDraft.categories ?? []).length}
            <div class="flex flex-col gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
              <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                Категории, где писать могут только администраторы и модераторы
              </div>
              {#each settingsDraft.categories ?? [] as category (category.id)}
                <label class="flex items-start gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    class="mt-0.5"
                    checked={Boolean(category.only_moderators_can_post)}
                    on:change={() => toggleDraftCategoryOnlyModerators(category.id)}
                  />
                  <span class="min-w-0">
                    <span class="block text-sm text-slate-900 dark:text-zinc-100">
                      {category.name}
                    </span>
                  </span>
                </label>
              {/each}
            </div>
          {/if}

          {#if canManageComunModerators()}
            <div class="flex flex-col gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
              <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                Видимость постов сообщества в общих лентах
              </div>
              <label class="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  class="mt-0.5"
                  checked={!settingsDraft.hide_from_home}
                  on:change={toggleDraftHideFromHome}
                />
                <span class="min-w-0">
                  <span class="block text-sm text-slate-900 dark:text-zinc-100">Показывать в Горячем</span>
                </span>
              </label>
              <label class="flex items-start gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  class="mt-0.5"
                  checked={!settingsDraft.hide_from_fresh}
                  on:change={toggleDraftHideFromFresh}
                />
                <span class="min-w-0">
                  <span class="block text-sm text-slate-900 dark:text-zinc-100">Показывать в Свежее</span>
                </span>
              </label>
            </div>
          {/if}

        {:else if settingsTab === 'moderation'}
          <div class="flex flex-col gap-3 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
            <label class="flex items-start gap-2 cursor-pointer">
              <input
                type="checkbox"
                class="mt-0.5"
                checked={Boolean(settingsDraft.glossary_enabled)}
                on:change={() =>
                  (settingsDraft = {
                    ...settingsDraft,
                    glossary_enabled: !Boolean(settingsDraft.glossary_enabled),
                  })}
              />
              <span class="min-w-0">
                <span class="block text-sm text-slate-900 dark:text-zinc-100">
                  Глоссарий
                </span>
                <span class="block text-xs text-slate-500 dark:text-zinc-400">
                  Включает публичную страницу терминов сообщества и вставку терминов в публикации.
                </span>
              </span>
            </label>

            {#if settingsDraft.glossary_enabled}
              <div class="flex flex-col gap-3 rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-900/40 p-3">
                <div class="flex flex-wrap items-center justify-between gap-2">
                  <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                    Термины глоссария
                  </div>
                  <Button size="sm" on:click={addDraftGlossaryTerm} disabled={settingsSaving}>
                    Добавить термин
                  </Button>
                </div>
                <input
                  bind:value={settingsGlossarySearch}
                  placeholder="Поиск по термину или расшифровке..."
                  class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
                />
                <div class="grid gap-3">
                  {#if filteredGlossaryTerms.length}
                    {#each filteredGlossaryTerms as glossaryTerm (glossaryTerm.localId)}
                      <div class="rounded-xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-3 py-3">
                        <div class="flex items-start justify-between gap-3">
                          <div class="flex-1 grid gap-3">
                            <label class="flex flex-col gap-1">
                              <span class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                                Термин
                              </span>
                              <input
                                value={glossaryTerm.term}
                                on:input={(event) => onGlossaryTermTitleInput(glossaryTerm.localId, event)}
                                class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
                                placeholder="Например: Шот-лист"
                              />
                            </label>
                            <label class="flex flex-col gap-1">
                              <span class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                                Расшифровка
                              </span>
                              <textarea
                                rows="3"
                                on:input={(event) =>
                                  onGlossaryTermDefinitionInput(glossaryTerm.localId, event)}
                                class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
                                placeholder="Короткое объяснение термина, которое будет показано при наведении"
                              >{glossaryTerm.definition}</textarea>
                            </label>
                          </div>
                          <button
                            type="button"
                            class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-rose-900/60 dark:hover:bg-rose-950/30 dark:hover:text-rose-300"
                            title="Удалить термин"
                            aria-label="Удалить термин"
                            on:click={() => removeDraftGlossaryTerm(glossaryTerm.localId)}
                          >
                            <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                              <path d="M3 6h18"></path>
                              <path d="M8 6V4.8c0-.9.7-1.6 1.6-1.6h4.8c.9 0 1.6.7 1.6 1.6V6"></path>
                              <path d="M18 6v12.2c0 .9-.7 1.6-1.6 1.6H7.6c-.9 0-1.6-.7-1.6-1.6V6"></path>
                              <path d="M10 10.5v5"></path>
                              <path d="M14 10.5v5"></path>
                            </svg>
                          </button>
                        </div>
                      </div>
                    {/each}
                  {:else}
                    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3 text-sm text-slate-500 dark:text-zinc-400">
                      {normalizedGlossarySearch
                        ? 'Термины не найдены'
                        : 'Добавьте термины, чтобы участники могли ссылаться на них в публикациях.'}
                    </div>
                  {/if}
                </div>
              </div>
            {/if}
          </div>

          <div class="flex flex-col gap-3 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
            <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
              Telegram-канал сообщества
            </div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Укажите публичный `@username` канала. Если канал уже подтвержден у вас на сайте, его можно выбрать сразу. Если нет, сохраните username здесь и завершите подключение в боте.
            </div>
            <input
              value={settingsDraft.telegram_channel_username ?? ''}
              on:input={onTelegramChannelInput}
              placeholder="@mychannel или https://t.me/mychannel"
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />

            {#if settingsTelegramChannelOptions.length}
              <div class="flex flex-col gap-2">
                <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                  Ваши подтвержденные каналы
                </div>
                <div class="flex flex-wrap gap-2">
                  {#each settingsTelegramChannelOptions as author}
                    <button
                      type="button"
                      class={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-sm transition ${
                        Number(selectedTelegramSourceAuthor?.id) === Number(author.id)
                          ? 'border-slate-900 bg-slate-900 text-white dark:border-white dark:bg-white dark:text-zinc-900'
                          : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800'
                      }`}
                      on:click={() => setDraftTelegramChannel(author.username, author)}
                    >
                      <span>@{author.username}</span>
                      {#if author.title}
                        <span class="text-xs opacity-70">{author.title}</span>
                      {/if}
                    </button>
                  {/each}
                </div>
              </div>
            {/if}

            {#if selectedTelegramSourceAuthor}
              <div class="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/20 dark:text-emerald-200">
                Канал уже связан с сообществом: @{selectedTelegramSourceAuthor.username}
              </div>
            {:else if pendingTelegramChannelUsername}
              <div class="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/20 dark:text-amber-200">
                Канал сохранен в ожидании: {pendingTelegramChannelUsername.startsWith('@') ? pendingTelegramChannelUsername : `@${pendingTelegramChannelUsername}`}. После сохранения завершите подключение в боте и отправьте код подтверждения.
              </div>
            {/if}
          </div>

          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Теги сообщества</div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Посты с этими тегами автоматически попадают в сообщество, если не отфильтрованы правилами ниже.
            </div>
            <input
              bind:value={settingsTagSearch}
              placeholder="Поиск тега для добавления..."
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
            <div class="flex flex-wrap items-center gap-2">
              {#if selectedSourceTags.length}
                {#each selectedSourceTags as tag}
                  <span class="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-sm">
                    #{tag.name}
                    <button type="button" class="text-slate-500 hover:text-slate-900 dark:hover:text-white" on:click={() => removeDraftSourceTag(tag.id)}>×</button>
                  </span>
                {/each}
              {:else}
                <span class="text-sm text-slate-500 dark:text-zinc-400">Теги пока не выбраны</span>
              {/if}
            </div>
            <div class="max-h-48 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
              {#if normalizedTagCreateValue && !hasExactTagMatch}
                <div class="flex items-center justify-between gap-2 px-3 py-2 bg-slate-50 dark:bg-zinc-900/60">
                  <div class="min-w-0 text-sm">
                    <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">
                      Добавить тег #{normalizedTagCreateValue}
                    </div>
                    <div class="text-xs text-slate-500 dark:text-zinc-400">
                      Создаст тег в системе и добавит его в теги сообщества
                    </div>
                  </div>
                  <Button size="sm" on:click={createTagAndChooseDraft} disabled={settingsTagCreating || settingsSaving}>
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
                    <Button size="sm" on:click={() => addDraftSourceTag(tag.id)} disabled={settingsTagCreating || settingsSaving || sourceTagIdSet.has(tag.id)}>
                      {sourceTagIdSet.has(tag.id) ? 'Добавлен' : 'Добавить'}
                    </Button>
                  </div>
                {/each}
              {:else}
                {#if normalizedTagCreateValue && !hasExactTagMatch}
                  <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                    Можно добавить новый тег выше
                  </div>
                {:else if normalizedTagSearch}
                  <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                    Ничего не найдено
                  </div>
                {/if}
              {/if}
            </div>
          </div>

          <label class="flex items-start gap-2 cursor-pointer rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3">
            <input
              type="checkbox"
              class="mt-0.5"
              checked={Boolean(settingsDraft.forbid_external_links)}
              on:change={() =>
                (settingsDraft = {
                  ...settingsDraft,
                  forbid_external_links: !Boolean(settingsDraft.forbid_external_links),
                })}
            />
            <span class="min-w-0">
              <span class="block text-sm text-slate-900 dark:text-zinc-100">
                Запретить внешние ссылки
              </span>
              <span class="block text-xs text-slate-500 dark:text-zinc-400">
                Посты с внешними ссылками не будут попадать в это сообщество, а новые публикации с такими ссылками будут отклоняться.
              </span>
            </span>
          </label>

          {#if canManageComunModerators()}
            <div class="flex flex-col gap-2">
              <div class="text-sm text-slate-700 dark:text-zinc-300">Модераторы сообщества</div>
              <input
                bind:value={settingsUserSearch}
                placeholder="Поиск пользователя по имени или логину..."
                class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
              />
              <div class="flex flex-col gap-2">
                <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                  Выбранные модераторы
                </div>
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
                      <Button size="sm" on:click={() => addDraftModerator(user.id)} disabled={draftModeratorIdSet.has(user.id)}>
                        {draftModeratorIdSet.has(user.id) ? 'Добавлен' : 'Добавить'}
                      </Button>
                    </div>
                  {/each}
                {:else if normalizedUserSearch}
                  <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                    Пользователи не найдены
                  </div>
                {/if}
              </div>
            </div>
          {/if}

          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Черный список авторов</div>
            <input
              bind:value={settingsAuthorSearch}
              placeholder="Поиск автора по логину или названию..."
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
            <div class="flex flex-col gap-2">
              <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
                Исключенные авторы
              </div>
              {#if selectedExcludedAuthors.length}
                <div class="flex flex-col gap-2">
                  {#each selectedExcludedAuthors as author}
                    <div class="flex items-center justify-between gap-2 rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2">
                      <div class="min-w-0">
                        <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                          {author.title || author.username}
                        </div>
                        <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">@{author.username}</div>
                      </div>
                      <Button color="ghost" size="sm" on:click={() => removeDraftExcludedAuthor(author.id)}>
                        Убрать
                      </Button>
                    </div>
                  {/each}
                </div>
              {:else}
                <div class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                  Пока никого не исключили
                </div>
              {/if}
            </div>
            <div class="max-h-52 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
              {#if filteredAuthorOptions.length}
                {#each filteredAuthorOptions as author}
                  <div class="flex items-center justify-between gap-2 px-3 py-2">
                    <div class="min-w-0">
                      <div class="text-sm font-medium text-slate-900 dark:text-zinc-100 truncate">
                        {author.title || author.username}
                      </div>
                      <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">@{author.username}</div>
                    </div>
                    <Button size="sm" on:click={() => addDraftExcludedAuthor(author.id)} disabled={draftExcludedAuthorIdSet.has(author.id)}>
                      {draftExcludedAuthorIdSet.has(author.id) ? 'Добавлен' : 'Добавить'}
                    </Button>
                  </div>
                {/each}
              {:else if normalizedAuthorSearch}
                <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                  Авторы не найдены
                </div>
              {/if}
            </div>
          </div>

          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Черный список тегов</div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Посты с этими тегами будут исключаться из сообщества.
            </div>
            <input
              bind:value={settingsBlockedTagSearch}
              placeholder="Поиск тега..."
              class="rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
            />
            <div class="flex flex-wrap gap-2">
              {#if selectedBlockedTags.length}
                {#each selectedBlockedTags as tag}
                  <span class="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-sm">
                    #{tag.name}
                    <button type="button" class="text-slate-500 hover:text-slate-900 dark:hover:text-white" on:click={() => removeDraftBlockedTag(tag.id)}>×</button>
                  </span>
                {/each}
              {:else}
                <span class="text-sm text-slate-500 dark:text-zinc-400">Черный список тегов пуст</span>
              {/if}
            </div>
            <div class="max-h-48 overflow-auto rounded-xl border border-slate-200 dark:border-zinc-800 divide-y divide-slate-100 dark:divide-zinc-800">
              {#if filteredBlockedTagOptions.length}
                {#each filteredBlockedTagOptions as tag}
                  <div class="flex items-center justify-between gap-2 px-3 py-2 text-sm">
                    <div class="min-w-0">
                      <div class="font-medium text-slate-900 dark:text-zinc-100 truncate">{tag.name}</div>
                      {#if tag.lemma}
                        <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">{tag.lemma}</div>
                      {/if}
                    </div>
                    <Button size="sm" on:click={() => addDraftBlockedTag(tag.id)} disabled={blockedTagIdSet.has(tag.id)}>
                      {blockedTagIdSet.has(tag.id) ? 'Добавлен' : 'Добавить'}
                    </Button>
                  </div>
                {/each}
              {:else if normalizedBlockedTagSearch}
                <div class="px-3 py-2 text-sm text-slate-500 dark:text-zinc-400">
                  Теги не найдены
                </div>
              {/if}
            </div>
          </div>
        {:else if settingsTab === 'categories'}
          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Доступные шаблоны публикаций</div>
            <TemplateTypeDropdown
              options={settingsTemplateTypeOptions}
              selectedValues={comunAllowedTemplateTypes(settingsDraft)}
              disabled={settingsSaving}
              on:change={(event) => setDraftAllowedTemplateTypes(event.detail)}
            />
          </div>

          <div class="flex flex-col gap-2">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Внутренние категории</div>
            <div class="flex gap-2">
              <input
                bind:value={settingsCategorySearch}
                placeholder="Например: Релизы, Баги, Исследования"
                class="flex-1 rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-2"
              />
              <Button
                size="sm"
                on:click={createCategoryAndSelectDraft}
                disabled={settingsCategoryCreating || !normalizedCategoryCreateValue}
              >
                {settingsCategoryCreating ? '...' : 'Добавить'}
              </Button>
            </div>
            {#if normalizedCategoryCreateValue && !hasExactCategoryMatch}
              <div class="rounded-xl border border-slate-200 dark:border-zinc-800 bg-slate-50 dark:bg-zinc-900/60 px-3 py-2 text-sm text-slate-700 dark:text-zinc-300">
                Новой категории пока нет. Нажмите `Добавить`, чтобы создать ее только для этого сообщества и сразу подключить.
              </div>
            {/if}
            <div class="grid gap-2 sm:grid-cols-2">
              {#if filteredCategoryOptions.length}
                {#each filteredCategoryOptions as category}
                  <div class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-3 flex flex-col gap-3">
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0">
                        <div class="block text-sm font-medium text-slate-900 dark:text-zinc-100">{category.name}</div>
                      </div>
                      <button
                        type="button"
                        class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-rose-900/60 dark:hover:bg-rose-950/30 dark:hover:text-rose-300"
                        title="Удалить категорию"
                        aria-label="Удалить категорию"
                        on:click={() => removeDraftCategory(category.id)}
                      >
                        <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                          <path d="M3 6h18"></path>
                          <path d="M8 6V4.8c0-.9.7-1.6 1.6-1.6h4.8c.9 0 1.6.7 1.6 1.6V6"></path>
                          <path d="M18 6v12.2c0 .9-.7 1.6-1.6 1.6H7.6c-.9 0-1.6-.7-1.6-1.6V6"></path>
                          <path d="M10 10.5v5"></path>
                          <path d="M14 10.5v5"></path>
                        </svg>
                      </button>
                    </div>
                    <div class="flex flex-col gap-2">
                      <TemplateTypeDropdown
                        options={settingsTemplateTypeOptions}
                        selectedValues={comunCategoryTemplateTypes(category)}
                        disabled={settingsSaving}
                        allowEmpty={true}
                        placeholder="Шаблоны категории"
                        on:change={(event) => setDraftCategoryTemplateTypes(category.id, event.detail)}
                      />
                    </div>
                  </div>
                {/each}
              {:else}
                <div class="rounded-xl border border-slate-200 dark:border-zinc-800 px-3 py-2 text-sm text-slate-500 dark:text-zinc-400 sm:col-span-2">
                  {normalizedCategorySearch ? 'Категории не найдены' : 'Категории пока не добавлены'}
                </div>
              {/if}
            </div>
          </div>
        {:else}
          <div class="flex flex-col gap-3">
            <div class="text-sm text-slate-700 dark:text-zinc-300">Правила сообщества</div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Эти правила будут публично показаны всем участникам сообщества, при публикациях и общении они должны соотсветствовать вашим правилам, а модераторы будут отслеживать их исполнение. Правила не должны противоречить общим правилам сайта
            </div>
            <textarea
              bind:value={settingsDraft.rules_text}
              rows="12"
              class="min-h-[18rem] rounded-xl border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 px-3 py-3"
              placeholder="Опишите правила сообщества"
            ></textarea>
          </div>
        {/if}
      </div>

      <div class="flex items-center justify-between gap-3 pt-5">
        <div class="flex items-center gap-3">
          {#if canDeleteComun()}
            <Button
              color="ghost"
              on:click={openDeleteComunModal}
              disabled={settingsSaving || settingsLogoUploading || deleteComunSaving}
            >
              Удалить сообщество
            </Button>
          {/if}
          <div class="text-xs text-slate-500 dark:text-zinc-400">
          {#if settingsHasChanges}
            Есть несохранённые изменения
          {:else}
            Все изменения сохранены
          {/if}
          </div>
        </div>
        <Button on:click={saveSettings} disabled={!settingsHasChanges || settingsSaving || settingsLogoUploading || deleteComunSaving}>
          {settingsSaving ? 'Сохраняем...' : 'Сохранить'}
        </Button>
      </div>
    </section>
  {/if}
</div>

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
  <title>{pageTitle}</title>
</svelte:head>
