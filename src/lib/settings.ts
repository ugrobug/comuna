import type { CommentSortType, SortType } from 'lemmy-js-client'
import { get, writable } from 'svelte/store'
import { env } from '$env/dynamic/public'
import { locale } from './translations'
import { browser } from '$app/environment'
import type { Link } from './components/ui/navbar/link'
import { buildAuthFeedSettingsUrl } from './api/backend'

console.log('Using the following default settings from the environment:')
console.log(env)
console.log('PUBLIC_DEFAULT_FEED:', env.PUBLIC_DEFAULT_FEED)
console.log('Default feed type:', (env.PUBLIC_DEFAULT_FEED as 'All' | 'Subscribed' | 'Local') ?? 'Local')

export type View = 'card' | 'cozy' | 'list' | 'compact'

export const SSR_ENABLED = env.PUBLIC_SSR_ENABLED?.toLowerCase() == 'true'

// Returns a proper boolean or null.  Used to set boolean values from env var strings while allowing nullish coalescing to set default values.
const toBool = (str: string | undefined) => {
  if (!str) {
    return null
  }
  return str.toLowerCase() === 'true'
}

interface Preset {
  title?: string
  content: string
}

export interface Settings {
  settingsVer: number
  expandableImages: boolean
  // should have been named "fade" read posts
  markReadPosts: boolean
  showInstances: {
    user: boolean
    community: boolean
    comments: boolean
  }

  view: View

  defaultSort: {
    sort: SortType
    feed: 'All' | 'Subscribed' | 'Local'
    comments: CommentSortType
  }
  hidePosts: {
    deleted: boolean
    removed: boolean
  }
  expandSidebar: boolean
  expand: {
    communities: boolean
    moderates: boolean
    favorites: boolean
    about: boolean
    stats: boolean
    team: boolean
    accounts: boolean
  }
  displayNames: boolean
  nsfwBlur: boolean
  moderation: {
    presets: Preset[]
  }
  randomPlaceholders: boolean
  modlogCardView: boolean | undefined
  debugInfo: boolean
  expandImages: boolean

  font: 'inter' | 'satoshi/nunito' | 'system' | 'browser' | 'roboto'
  leftAlign: boolean
  hidePhoton: boolean

  newWidth: boolean
  markPostsAsRead: boolean
  hideReadPosts: boolean

  openLinksInNewTab: boolean
  crosspostOriginalLink: boolean

  embeds: {
    clickToView: boolean
    youtube: 'youtube' | 'invidious' | 'piped'
    invidious: string | undefined
    piped: string | undefined
  }
  dock: {
    noGap: boolean | null
    top: boolean | null
    pins: Link[]
    paletteHotkey: string
  }
  posts: {
    deduplicateEmbed: boolean
    showHidden: boolean
    noVirtualize: boolean
    reverseActions: boolean
  }
  infiniteScroll: boolean
  homeFeed: 'hot' | 'mine'
  language: string | null
  myFeedAuthors: string[]
  myFeedTags: string[]
  myFeedComuns: string[]
  myFeedComunCategories: Record<string, string[]>
  hiddenAuthors: string[]
  myFeedHideNegative: boolean
  useRtl: boolean
  translator: string | undefined
  parseTags: boolean
  tagRules: {
    [key: string]: 'hide' | 'blur'
  }
  logoColorMonth: number | null
}

export const defaultSettings: Settings = {
  settingsVer: 3,
  expandableImages: toBool(env.PUBLIC_EXPANDABLE_IMAGES) ?? true,
  markReadPosts: false,
  showInstances: {
    user: toBool(env.PUBLIC_SHOW_INSTANCES_USER) ?? true,
    community: toBool(env.PUBLIC_SHOW_INSTANCES_COMMUNITY) ?? true,
    comments: toBool(env.PUBLIC_SHOW_INSTANCES_COMMENTS) ?? true,
  },
  defaultSort: {
    sort: (env.PUBLIC_DEFAULT_FEED_SORT as SortType) ?? 'TopWeek',
    feed: (env.PUBLIC_DEFAULT_FEED as 'All' | 'Subscribed' | 'Local') ?? 'All',
    comments: 'Hot' as CommentSortType,
  },
  hidePosts: {
    deleted: toBool(env.PUBLIC_HIDE_DELETED) ?? true,
    removed: toBool(env.PUBLIC_HIDE_REMOVED) ?? true,
  },
  expandSidebar: toBool(env.PUBLIC_EXPAND_SIDEBAR) ?? true,
  expand: {
    communities: toBool(env.PUBLIC_EXPAND_COMMUNITIES) ?? true,
    favorites: toBool(env.PUBLIC_EXPAND_FAVORITES) ?? true,
    moderates: toBool(env.PUBLIC_EXPAND_MODERATES) ?? true,
    about: false,
    stats: false,
    team: false,
    accounts: true,
  },
  displayNames: toBool(env.PUBLIC_DISPLAY_NAMES) ?? true,
  nsfwBlur: false,
  moderation: {
    presets: [
      {
        title: 'Шаблон 1',
        content: `Ваш пост *"{{post}}"* было удалено по причине {{reason}}.`,
      },
    ],
  },
  randomPlaceholders: false,
  modlogCardView: toBool(env.PUBLIC_MODLOG_CARD_VIEW) ?? undefined,
  debugInfo: toBool(env.PUBLIC_DEBUG_INFO) ?? false,
  expandImages: toBool(env.PUBLIC_EXPAND_IMAGES) ?? true,
  // @ts-ignore
  view: env.PUBLIC_VIEW ?? 'cozy',
  font: 'roboto',
  leftAlign: toBool(env.PUBLIC_LEFT_ALIGN) ?? false,
  hidePhoton: toBool(env.PUBLIC_REMOVE_CREDIT) ?? false,
  newWidth: toBool(env.PUBLIC_LIMIT_LAYOUT_WIDTH) ?? true,
  markPostsAsRead: toBool(env.PUBLIC_MARK_POSTS_AS_READ) ?? true,
  hideReadPosts: false,
  openLinksInNewTab: false,
  crosspostOriginalLink: false,
  embeds: {
    clickToView: true,
    youtube: 'youtube',
    invidious: undefined,
    piped: undefined,
  },
  dock: {
    noGap: null,
    top: null,
    pins: [],
    paletteHotkey: '/',
  },
  posts: {
    deduplicateEmbed: toBool(env.PUBLIC_DEDUPLICATE_EMBED) ?? true,
    showHidden: false,
    noVirtualize: false,
    reverseActions: false,
  },
  infiniteScroll: true,
  homeFeed: 'hot',
  language: 'ru',
  myFeedAuthors: [],
  myFeedTags: [],
  myFeedComuns: [],
  myFeedComunCategories: {},
  hiddenAuthors: [],
  myFeedHideNegative: true,
  useRtl: false,
  translator: undefined,
  parseTags: true,
  tagRules: {
    cw: 'blur',
    nsfl: 'blur',
    nsfw: 'blur',
  },
  logoColorMonth: null,
}

export const userSettings = writable(defaultSettings)
export type FeedSettingsHydrationState = 'idle' | 'loading' | 'ready' | 'error'
export const feedSettingsHydrationState = writable<FeedSettingsHydrationState>('idle')
export const feedSettingsHydrated = writable(false)

type BackendFeedSettings = {
  home_feed?: string
  hide_read_posts?: boolean
  my_feed_authors?: string[]
  my_feed_tags?: string[]
  my_feed_comuns?: string[]
  my_feed_comun_categories?: Record<string, string[]>
  hidden_authors?: string[]
  my_feed_hide_negative?: boolean
  tag_rules?: Record<string, 'hide' | 'blur'>
}

const feedSettingsDefaults = () => ({
  homeFeed: defaultSettings.homeFeed,
  hideReadPosts: defaultSettings.hideReadPosts,
  myFeedAuthors: [...defaultSettings.myFeedAuthors],
  myFeedTags: [...defaultSettings.myFeedTags],
  myFeedComuns: [...defaultSettings.myFeedComuns],
  myFeedComunCategories: { ...defaultSettings.myFeedComunCategories },
  hiddenAuthors: [...defaultSettings.hiddenAuthors],
  myFeedHideNegative: defaultSettings.myFeedHideNegative,
  tagRules: { ...defaultSettings.tagRules },
})

const feedSettingsSnapshot = (settings: Settings) =>
  JSON.stringify({
    homeFeed: settings.homeFeed,
    hideReadPosts: settings.hideReadPosts,
    myFeedAuthors: settings.myFeedAuthors ?? [],
    myFeedTags: [],
    myFeedComuns: settings.myFeedComuns ?? [],
    myFeedComunCategories: settings.myFeedComunCategories ?? {},
    hiddenAuthors: settings.hiddenAuthors ?? [],
    myFeedHideNegative: settings.myFeedHideNegative,
    tagRules: settings.tagRules ?? {},
  })

const backendPayloadFromSettings = (settings: Settings) => ({
  home_feed: settings.homeFeed,
  hide_read_posts: settings.hideReadPosts,
  my_feed_authors: settings.myFeedAuthors ?? [],
  my_feed_tags: [],
  my_feed_comuns: settings.myFeedComuns ?? [],
  my_feed_comun_categories: settings.myFeedComunCategories ?? {},
  hidden_authors: settings.hiddenAuthors ?? [],
  my_feed_hide_negative: settings.myFeedHideNegative,
  tag_rules: settings.tagRules ?? {},
})

const settingsFromBackendPayload = (settings: Settings, payload: BackendFeedSettings): Settings =>
  migrate({
    ...settings,
    homeFeed: payload.home_feed ?? settings.homeFeed,
    hideReadPosts: payload.hide_read_posts ?? settings.hideReadPosts,
    myFeedAuthors: payload.my_feed_authors ?? settings.myFeedAuthors,
    myFeedTags: [],
    myFeedComuns: payload.my_feed_comuns ?? settings.myFeedComuns,
    myFeedComunCategories: payload.my_feed_comun_categories ?? settings.myFeedComunCategories,
    hiddenAuthors: payload.hidden_authors ?? settings.hiddenAuthors,
    myFeedHideNegative: payload.my_feed_hide_negative ?? settings.myFeedHideNegative,
    tagRules: payload.tag_rules ?? settings.tagRules,
  })

let backendFeedSettingsToken: string | null = null
let backendFeedSettingsHydrated = false
let applyingBackendFeedSettings = false
let backendFeedSettingsSaveTimer: ReturnType<typeof setTimeout> | null = null
let lastBackendFeedSettingsSnapshot = ''

const saveBackendFeedSettings = async (settings: Settings) => {
  if (!browser || !backendFeedSettingsToken || !backendFeedSettingsHydrated) return
  const snapshot = feedSettingsSnapshot(settings)
  if (snapshot === lastBackendFeedSettingsSnapshot) return
  const response = await fetch(buildAuthFeedSettingsUrl(), {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${backendFeedSettingsToken}`,
    },
    body: JSON.stringify(backendPayloadFromSettings(settings)),
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(payload?.error || 'Не удалось сохранить настройки ленты')
  }
  lastBackendFeedSettingsSnapshot = snapshot
}

const scheduleBackendFeedSettingsSave = (settings: Settings) => {
  if (!browser || applyingBackendFeedSettings || !backendFeedSettingsHydrated) return
  if (!backendFeedSettingsToken) return
  if (backendFeedSettingsSaveTimer) clearTimeout(backendFeedSettingsSaveTimer)
  backendFeedSettingsSaveTimer = setTimeout(() => {
    backendFeedSettingsSaveTimer = null
    saveBackendFeedSettings(get(userSettings)).catch((error) => {
      console.error('Failed to save feed settings:', error)
    })
  }, 500)
}

export const loadBackendFeedSettings = async (token: string | null) => {
  if (!browser || !token) {
    feedSettingsHydrationState.set('idle')
    feedSettingsHydrated.set(false)
    return null
  }
  backendFeedSettingsToken = token
  backendFeedSettingsHydrated = false
  feedSettingsHydrationState.set('loading')
  feedSettingsHydrated.set(false)
  const localSettings = get(userSettings)
  try {
    const response = await fetch(buildAuthFeedSettingsUrl(), {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok || !payload?.settings) {
      throw new Error(payload?.error || 'Не удалось загрузить настройки ленты')
    }

    applyingBackendFeedSettings = true
    try {
      userSettings.set(settingsFromBackendPayload(localSettings, payload.settings))
      lastBackendFeedSettingsSnapshot = feedSettingsSnapshot(get(userSettings))
      backendFeedSettingsHydrated = true
      feedSettingsHydrationState.set('ready')
      feedSettingsHydrated.set(true)
    } finally {
      applyingBackendFeedSettings = false
    }
    return payload.settings as BackendFeedSettings
  } catch (error) {
    backendFeedSettingsHydrated = false
    feedSettingsHydrationState.set('error')
    feedSettingsHydrated.set(false)
    throw error
  }
}

export const resetBackendFeedSettingsSync = () => {
  backendFeedSettingsToken = null
  backendFeedSettingsHydrated = false
  feedSettingsHydrationState.set('idle')
  feedSettingsHydrated.set(false)
  applyingBackendFeedSettings = false
  lastBackendFeedSettingsSnapshot = ''
  if (backendFeedSettingsSaveTimer) {
    clearTimeout(backendFeedSettingsSaveTimer)
    backendFeedSettingsSaveTimer = null
  }
  if (browser) {
    userSettings.update((settings) => ({
      ...settings,
      ...feedSettingsDefaults(),
    }))
  }
}

export const subscribeToComunBySlug = (slug?: string | null) => {
  const normalizedSlug = String(slug ?? '').trim()
  if (!normalizedSlug) return

  userSettings.update((settings) => {
    const next = new Set((settings.myFeedComuns ?? []).map((value) => value.trim()).filter(Boolean))
    next.add(normalizedSlug)
    return {
      ...settings,
      myFeedComuns: Array.from(next),
    }
  })
}

const migrate = (settings: any): Settings => {
  if (typeof settings?.moderation?.removalReasonPreset == 'string') {
    settings.moderation.presets = [
      {
        title: 'Preset 1',
        content: settings.moderation.removalReasonPreset,
      },
    ]
    settings.moderation.removalReasonPreset = undefined
  }
  if (!Array.isArray(settings?.myFeedAuthors)) {
    settings.myFeedAuthors = []
  } else {
    const seen = new Set<string>()
    settings.myFeedAuthors = settings.myFeedAuthors
      .map((author: unknown) => (typeof author === 'string' ? author.trim() : ''))
      .filter((author: string) => !!author)
      .filter((author: string) => {
        if (seen.has(author)) return false
        seen.add(author)
        return true
      })
  }
  if (!Array.isArray(settings?.myFeedTags)) {
    settings.myFeedTags = []
  } else {
    const seen = new Set<string>()
    settings.myFeedTags = settings.myFeedTags
      .map((tag: unknown) => (typeof tag === 'string' ? tag.trim() : ''))
      .filter((tag: string) => !!tag)
      .filter((tag: string) => {
        if (seen.has(tag)) return false
        seen.add(tag)
        return true
      })
  }
  if (!Array.isArray(settings?.myFeedComuns)) {
    settings.myFeedComuns = []
  } else {
    const seen = new Set<string>()
    settings.myFeedComuns = settings.myFeedComuns
      .map((slug: unknown) => (typeof slug === 'string' ? slug.trim() : ''))
      .filter((slug: string) => !!slug)
      .filter((slug: string) => {
        if (seen.has(slug)) return false
        seen.add(slug)
        return true
      })
  }
  if (!settings?.myFeedComunCategories || typeof settings.myFeedComunCategories !== 'object' || Array.isArray(settings.myFeedComunCategories)) {
    settings.myFeedComunCategories = {}
  } else {
    const normalizedCategories: Record<string, string[]> = {}
    for (const [rawSlug, rawCategories] of Object.entries(settings.myFeedComunCategories)) {
      const slug = typeof rawSlug === 'string' ? rawSlug.trim() : ''
      if (!slug || !Array.isArray(rawCategories)) continue
      const seen = new Set<string>()
      normalizedCategories[slug] = rawCategories
        .map((category: unknown) => (typeof category === 'string' ? category.trim() : ''))
        .filter((category: string) => !!category)
        .filter((category: string) => {
          if (seen.has(category)) return false
          seen.add(category)
          return true
        })
    }
    settings.myFeedComunCategories = normalizedCategories
  }
  if (!Array.isArray(settings?.hiddenAuthors)) {
    settings.hiddenAuthors = []
  } else {
    const seen = new Set<string>()
    settings.hiddenAuthors = settings.hiddenAuthors
      .map((author: unknown) => (typeof author === 'string' ? author.trim() : ''))
      .filter((author: string) => !!author)
      .filter((author: string) => {
        if (seen.has(author)) return false
        seen.add(author)
        return true
      })
  }
  const validHomeFeeds = new Set(['hot', 'mine'])
  if (!validHomeFeeds.has(settings?.homeFeed)) {
    settings.homeFeed = defaultSettings.homeFeed
  }
  if (typeof settings?.myFeedHideNegative !== 'boolean') {
    settings.myFeedHideNegative = defaultSettings.myFeedHideNegative
  }
  if (typeof settings?.hideReadPosts !== 'boolean') {
    settings.hideReadPosts = defaultSettings.hideReadPosts
  }
  settings.language = 'ru'
  settings.dock = { ...defaultSettings.dock, pins: [] }
  settings.defaultSort = { ...defaultSettings.defaultSort }
  settings.showInstances = { ...defaultSettings.showInstances }
  settings.displayNames = defaultSettings.displayNames
  settings.view = defaultSettings.view
  settings.leftAlign = defaultSettings.leftAlign
  settings.randomPlaceholders = defaultSettings.randomPlaceholders
  settings.expandImages = defaultSettings.expandImages
  settings.expandableImages = defaultSettings.expandableImages
  settings.nsfwBlur = defaultSettings.nsfwBlur
  settings.markReadPosts = defaultSettings.markReadPosts
  settings.crosspostOriginalLink = defaultSettings.crosspostOriginalLink
  settings.infiniteScroll = defaultSettings.infiniteScroll
  settings.translator = defaultSettings.translator
  settings.hidePosts = { ...defaultSettings.hidePosts }
  settings.posts = {
    ...defaultSettings.posts,
    ...(settings.posts ?? {}),
    deduplicateEmbed: defaultSettings.posts.deduplicateEmbed,
    showHidden: defaultSettings.posts.showHidden,
    reverseActions: defaultSettings.posts.reverseActions,
  }

  return settings
}

if (typeof window != 'undefined') {
  let oldUserSettings = JSON.parse(
    localStorage.getItem('settings') ?? JSON.stringify(defaultSettings)
  )

  console.log('Loaded settings from localStorage:', oldUserSettings)
  console.log('Default settings:', defaultSettings)

  oldUserSettings = migrate(oldUserSettings)

  userSettings.set({
    ...defaultSettings,
    ...oldUserSettings,
    ...feedSettingsDefaults(),
    settingsVer: defaultSettings.settingsVer,
  })
}

userSettings.subscribe((settings) => {
  if (typeof window != 'undefined') {
    localStorage.setItem(
      'settings',
      JSON.stringify({
        ...settings,
        ...feedSettingsDefaults(),
      })
    )
    scheduleBackendFeedSettingsSave(settings)
  }
  if (settings.language) {
    locale.set(settings.language)
  } else {
    if (browser) locale.set(navigator?.language)
  }
})
