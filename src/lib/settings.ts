import type { CommentSortType, SortType } from 'lemmy-js-client'
import { writable } from 'svelte/store'
import { env } from '$env/dynamic/public'
import { locale } from './translations'
import { browser } from '$app/environment'
import type { Link } from './components/ui/navbar/link'

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

interface Settings {
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
  language: string | null
  myFeedRubrics: string[]
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
  language: 'ru',
  myFeedRubrics: [],
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
  if (!Array.isArray(settings?.myFeedRubrics)) {
    settings.myFeedRubrics = []
  }
  settings.language = 'ru'
  settings.dock = { ...defaultSettings.dock, pins: [] }
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
    settingsVer: defaultSettings.settingsVer,
  })
}

userSettings.subscribe((settings) => {
  if (typeof window != 'undefined') {
    localStorage.setItem('settings', JSON.stringify(settings))
  }
  if (settings.language) {
    locale.set(settings.language)
  } else {
    if (browser) locale.set(navigator?.language)
  }
})
