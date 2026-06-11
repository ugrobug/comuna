import { browser } from '$app/environment'
import { env as publicEnv } from '$env/dynamic/public'
import type { SitePostTemplate } from '$lib/postTemplates'
import { slugifyTitle } from '$lib/util/slug'
import type { PostView } from 'lemmy-js-client'

export const getBackendBaseUrl = (): string => {
  if (!browser) {
    const base =
      process.env.INTERNAL_BACKEND_URL ||
      publicEnv.PUBLIC_BACKEND_URL ||
      ''
    return base.replace(/\/$/, '')
  }
  const base = (publicEnv.PUBLIC_BACKEND_URL || '').replace(/\/$/, '')
  if (!base || base === window.location.origin) {
    return ''
  }
  return base
}

export const buildAuthorPostsUrl = (username: string): string => {
  return `${getBackendBaseUrl()}/api/authors/${encodeURIComponent(username)}/posts/`
}

export const buildTagPostsUrl = (tag: string): string => {
  return `${getBackendBaseUrl()}/api/tags/${encodeURIComponent(tag)}/posts/`
}

export const buildPostDetailUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/`
}

export const buildPostCommentsUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/comments/`
}

export const buildCommentDetailUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/comments/${encodeURIComponent(id)}/`
}

export const buildCommentLikeUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/comments/${encodeURIComponent(id)}/like/`
}

export const buildRecentCommentsUrl = (limit = 5): string => {
  const params = new URLSearchParams({ limit: String(limit) })
  return `${getBackendBaseUrl()}/api/comments/recent/?${params.toString()}`
}

export const buildPostLikeUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/like/`
}

export const buildPostFavoriteUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/favorite/`
}

export const buildPostReadUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/read/`
}

export const buildPostViewUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/view/`
}

export const buildPostPollVoteUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/poll-vote/`
}

export const buildPostRatingVoteUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/rating-vote/`
}

export const buildBugReportStatusUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/bug-report-status/`
}

export const buildBugReportConfirmationUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/bug-report-confirmation/`
}

export const buildTagsListUrl = (params?: { q?: string; limit?: number }): string => {
  const searchParams = new URLSearchParams()
  if (params?.q) searchParams.set('q', params.q)
  if (params?.limit) searchParams.set('limit', String(params.limit))
  const queryString = searchParams.toString()
  return `${getBackendBaseUrl()}/api/tags/${queryString ? `?${queryString}` : ''}`
}

export const buildTagsEnsureUrl = (): string => {
  return `${getBackendBaseUrl()}/api/tags/ensure/`
}

export const buildComunsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/comuns/`
}

export const buildComunsCatalogUrl = (options?: {
  page?: number
  limit?: number
  q?: string
}): string => {
  const params = new URLSearchParams()
  if (typeof options?.page === 'number') {
    params.set('page', String(options.page))
  }
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  if (options?.q) {
    params.set('q', options.q)
  }
  const query = params.toString()
  return `${getBackendBaseUrl()}/api/comuns/catalog/${query ? `?${query}` : ''}`
}

export const buildComunsComposerUrl = (): string => {
  return `${getBackendBaseUrl()}/api/comuns/composer/`
}

export const buildComunsSidebarUrl = (): string => {
  return `${getBackendBaseUrl()}/api/comuns/sidebar/`
}

export const buildComunFromTelegramChannelUrl = (): string => {
  return `${getBackendBaseUrl()}/api/comuns/from-telegram-channel/`
}

export const buildComunUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/`
}

export const buildComunCustomTemplateEditorPath = (
  slug: string,
  templateRef: string | number
): string => {
  return `/comuns/${encodeURIComponent(slug)}/settings/templates/${encodeURIComponent(String(templateRef))}`
}

export const buildComunGlossaryPath = (slug: string): string => {
  return `/comuns/${encodeURIComponent(slug)}/glossary`
}

export const buildComunKnowledgeBasePath = (slug: string): string => {
  return `/comuns/${encodeURIComponent(slug)}/knowledge-base`
}

export const buildComunKnowledgeBaseUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/knowledge-base/`
}

export const buildComunKnowledgeBaseItemUrl = (
  slug: string,
  itemId: number | string
): string => {
  return `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/knowledge-base/${encodeURIComponent(itemId)}/`
}

export const buildComunRoadmapPath = (slug: string): string => {
  return `/comuns/${encodeURIComponent(slug)}/roadmap`
}

export const buildComunVoteUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/vote/`
}

export const buildComunWelcomePostOptionsUrl = (
  slug: string,
  options?: {
    q?: string
    limit?: number
  }
): string => {
  const base = `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/welcome-post-options/`
  const params = new URLSearchParams()
  if (options?.q) {
    params.set('q', options.q)
  }
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildComunPostsUrl = (
  slug: string,
  options?: {
    categorySlug?: string
  }
): string => {
  const base = `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/posts/`
  const params = new URLSearchParams()
  if (options?.categorySlug) {
    params.set('category', options.categorySlug)
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildComunPostCategoryUrl = (slug: string, postId: number | string): string => {
  return `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/posts/${encodeURIComponent(postId)}/category/`
}

export const buildPublicUserProfileUrl = (
  userId: number | string,
  options?: { limit?: number; offset?: number }
): string => {
  const base = `${getBackendBaseUrl()}/api/site-users/${encodeURIComponent(userId)}/profile/`
  const params = new URLSearchParams()
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  if (typeof options?.offset === 'number') {
    params.set('offset', String(options.offset))
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildAuthChatsUrl = (options?: { limit?: number; offset?: number }): string => {
  const base = `${getBackendBaseUrl()}/api/auth/chats/`
  const params = new URLSearchParams()
  if (typeof options?.limit === 'number') params.set('limit', String(options.limit))
  if (typeof options?.offset === 'number') params.set('offset', String(options.offset))
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildAuthChatUrl = (
  chatId: number | string,
  options?: { limit?: number; beforeId?: number }
): string => {
  const base = `${getBackendBaseUrl()}/api/auth/chats/${encodeURIComponent(chatId)}/`
  const params = new URLSearchParams()
  if (typeof options?.limit === 'number') params.set('limit', String(options.limit))
  if (typeof options?.beforeId === 'number') params.set('before_id', String(options.beforeId))
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildAuthChatMessagesUrl = (chatId: number | string): string => {
  return `${getBackendBaseUrl()}/api/auth/chats/${encodeURIComponent(chatId)}/messages/`
}

export const buildAuthChatReportBlockUrl = (chatId: number | string): string => {
  return `${getBackendBaseUrl()}/api/auth/chats/${encodeURIComponent(chatId)}/report-block/`
}

export const buildAuthFeedSettingsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/auth/feed-settings/`
}

export const buildModeratorAnalyticsUrl = (options?: {
  from?: string
  to?: string
}): string => {
  const base = `${getBackendBaseUrl()}/api/moderator/analytics/`
  const params = new URLSearchParams()
  if (options?.from) {
    params.set('from', options.from)
  }
  if (options?.to) {
    params.set('to', options.to)
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildModeratorPostViewSettingsUrl = (options?: {
  q?: string
  limit?: number
}): string => {
  const base = `${getBackendBaseUrl()}/api/moderator/post-view-settings/`
  const params = new URLSearchParams()
  if (options?.q) {
    params.set('q', options.q)
  }
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildModeratorPostViewSettingUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/moderator/posts/${encodeURIComponent(id)}/view-settings/`
}

export const buildModeratorRatingSettingsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/moderator/rating-settings/`
}

export const buildModeratorRatingSettingsUpdateUrl = (): string => {
  return `${getBackendBaseUrl()}/api/moderator/rating-settings/update/`
}

export const buildModeratorChatReportsUrl = (options?: {
  status?: string
  limit?: number
  offset?: number
}): string => {
  const base = `${getBackendBaseUrl()}/api/moderator/chat-reports/`
  const params = new URLSearchParams()
  if (options?.status) {
    params.set('status', options.status)
  }
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  if (typeof options?.offset === 'number') {
    params.set('offset', String(options.offset))
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildModeratorChatReportUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/moderator/chat-reports/${encodeURIComponent(id)}/`
}

export const buildSpecialLandnameUrl = (text: string = '', options?: { track?: boolean }): string => {
  const params = new URLSearchParams()
  if (text) {
    params.set('text', text)
  }
  if (options?.track) {
    params.set('track', '1')
  }
  const query = params.toString()
  return `${getBackendBaseUrl()}/api/special-projects/landname/${query ? `?${query}` : ''}`
}

export const buildSpecialLandnameAlphabetUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/landname/alphabet/`
}

export const buildSpecialLandnameSuggestionUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/landname/suggestions/`
}

export const buildSpecialLandnameShareUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/landname/share/`
}

export const buildSpecialLandnamePreviewImageUrl = (text: string = ''): string => {
  const params = new URLSearchParams()
  if (text) {
    params.set('text', text)
  }
  const query = params.toString()
  return `${getBackendBaseUrl()}/api/special-projects/landname/preview.png${query ? `?${query}` : ''}`
}

export const buildSpecialLandnameAdminLettersUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/landname/admin/letters/`
}

export const buildSpecialLandnameAdminGenerationsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/landname/admin/generations/`
}

export const buildSpecialLandnameAdminLetterUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/landname/admin/letters/${encodeURIComponent(id)}/`
}

export const buildSpecialLandnameAdminSuggestionUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/landname/admin/suggestions/${encodeURIComponent(id)}/`
}

export const buildSpecialLandnameAdminSuggestionApproveUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/landname/admin/suggestions/${encodeURIComponent(id)}/approve/`
}

export const buildSpecialBookStatusUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/status/`
}

export const buildSpecialBookAdminStatsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/admin/stats/`
}

export const buildSpecialBookAdminSettingsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/admin/settings/`
}

export const buildSpecialBookAdminBlockedWordsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/admin/blocked-words/`
}

export const buildSpecialBookAdminBlockedWordUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/admin/blocked-words/${encodeURIComponent(id)}/`
}

export const buildSpecialBookAdminWordsUrl = (options?: {
  offset?: number
  limit?: number
  q?: string
}): string => {
  const params = new URLSearchParams()
  if (typeof options?.offset === 'number') {
    params.set('offset', String(options.offset))
  }
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  if (options?.q) {
    params.set('q', options.q)
  }
  const query = params.toString()
  return `${getBackendBaseUrl()}/api/special-projects/book/admin/words/${query ? `?${query}` : ''}`
}

export const buildSpecialBookAdminWordCensorUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/admin/words/${encodeURIComponent(id)}/censor/`
}

export const buildSpecialBookAdminSelectionCensorUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/admin/selection/censor/`
}

export const buildSpecialBookWordsUrl = (options?: {
  offset?: number
  limit?: number
}): string => {
  const params = new URLSearchParams()
  if (typeof options?.offset === 'number') {
    params.set('offset', String(options.offset))
  }
  if (typeof options?.limit === 'number') {
    params.set('limit', String(options.limit))
  }
  const query = params.toString()
  return `${getBackendBaseUrl()}/api/special-projects/book/words/${query ? `?${query}` : ''}`
}

export const buildSpecialBookSubmitUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/submit/`
}

export const buildSpecialBookReminderUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/reminder/`
}

export const buildSpecialBookFinalNotificationUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/book/final-notification/`
}

export const buildSpecial1001FilmsStatusUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/status/`
}

export const buildSpecial1001FilmsStartUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/start/`
}

export const buildSpecial1001FilmsResumeUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/resume/`
}

export const buildSpecial1001FilmsEntryUrl = (token: string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/entries/${encodeURIComponent(token)}/`
}

export const buildSpecial1001FilmsEntryCommentsUrl = (token: string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/entries/${encodeURIComponent(token)}/comments/`
}

export const buildSpecial1001FilmsEntryRatingVoteUrl = (token: string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/entries/${encodeURIComponent(token)}/rating-vote/`
}

export const buildSpecial1001FilmsAdminFilmsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/admin/films/`
}

export const buildSpecial1001FilmsAdminLandingImagesUrl = (): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/admin/landing-images/`
}

export const buildSpecial1001FilmsAdminFilmUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/special-projects/365-films/admin/films/${encodeURIComponent(id)}/`
}

export const buildLandingPageUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/landing-pages/${encodeURIComponent(slug)}/`
}

export const buildLandingPageLeadsUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/landing-pages/${encodeURIComponent(slug)}/leads/`
}

export const buildLandingPagesAdminUrl = (): string => {
  return `${getBackendBaseUrl()}/api/landing-pages/admin/pages/`
}

export const buildLandingPageAdminUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/landing-pages/admin/pages/${encodeURIComponent(slug)}/`
}

export const buildLandingPageAdminImagesUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/landing-pages/admin/pages/${encodeURIComponent(slug)}/images/`
}

export const buildLandingPageAdminImageUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/landing-pages/admin/images/${encodeURIComponent(id)}/`
}

export const buildBackendPostPath = (post: { id: number; title: string }): string => {
  const slug = slugifyTitle(post.title)
  return slug ? `/b/post/${post.id}-${slug}` : `/b/post/${post.id}`
}

export const buildHomeFeedUrl = (options?: {
  hideRead?: boolean
  onlyRead?: boolean
  card?: boolean
}): string => {
  const base = `${getBackendBaseUrl()}/api/home/`
  const params = new URLSearchParams()
  if (options?.onlyRead) {
    params.set('only_read', '1')
  } else if (options?.hideRead) {
    params.set('hide_read', '1')
  }
  if (options?.card) {
    params.set('card', '1')
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildFavoritesFeedUrl = (options?: {
  hideRead?: boolean
  onlyRead?: boolean
}): string => {
  const base = `${getBackendBaseUrl()}/api/home/favorites/`
  const params = new URLSearchParams()
  if (options?.onlyRead) {
    params.set('only_read', '1')
  } else if (options?.hideRead) {
    params.set('hide_read', '1')
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildMyFeedUrl = (
  authors?: string[],
  tags?: string[],
  comuns?: string[],
  comunCategories?: Record<string, string[]>,
  hideNegative?: boolean,
  hideRead: boolean = false,
  onlyRead: boolean = false
): string => {
  const base = `${getBackendBaseUrl()}/api/home/my/`
  const params = new URLSearchParams()
  if (authors?.length) {
    params.set('authors', authors.join(','))
  }
  if (tags?.length) {
    params.set('tags', tags.join(','))
  }
  if (comuns?.length) {
    params.set('comuns', comuns.join(','))
  }
  if (comunCategories && Object.keys(comunCategories).length) {
    params.set('comun_categories', JSON.stringify(comunCategories))
  }
  if (typeof hideNegative === 'boolean' && !hideNegative) {
    params.set('hide_negative', '0')
  }
  if (onlyRead) {
    params.set('only_read', '1')
  } else if (hideRead) {
    params.set('hide_read', '1')
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildSearchUrl = (
  query: string,
  page = 1,
  limit = 20,
  type: string = 'All',
  sort: string = 'New'
): string => {
  const params = new URLSearchParams({
    q: query,
    page: String(page),
    limit: String(limit),
    type: type,
    sort: sort,
  })
  return `${getBackendBaseUrl()}/api/search/?${params.toString()}`
}

export type BackendTopAuthorPeriod = 'week' | 'month' | 'all'

export type BackendTopAuthor = {
  username: string
  title?: string | null
  channel_url?: string | null
  avatar_url?: string | null
  author_rating?: number
  rating: number
  score?: number
  posts_count: number
  period: BackendTopAuthorPeriod
  month_rating?: number
  month_score?: number
  month_posts?: number
  week_rating?: number
  week_score?: number
  week_posts?: number
  all_time_rating?: number
  all_time_score?: number
  all_time_posts?: number
}

export type BackendTopComun = {
  id: number
  slug: string
  name: string
  title?: string | null
  logo_url?: string | null
  avatar_url?: string | null
  rating: number
  score?: number
  posts_count: number
  comments_count: number
}

export const buildTopAuthorsUrl = (options?: {
  period?: BackendTopAuthorPeriod
  limit?: number | 'all'
}): string => {
  const params = new URLSearchParams()
  params.set('period', options?.period ?? 'month')
  if (options?.limit !== undefined) {
    params.set('limit', String(options.limit))
  }
  return `${getBackendBaseUrl()}/api/authors/top/?${params.toString()}`
}

export const buildTopAuthorsMonthUrl = (limit = 5): string => {
  const params = new URLSearchParams({ limit: String(limit) })
  return `${getBackendBaseUrl()}/api/authors/top-month/?${params.toString()}`
}

export const buildTopComunsUrl = (options?: { limit?: number | 'all' }): string => {
  const params = new URLSearchParams()
  if (options?.limit !== undefined) {
    params.set('limit', String(options.limit))
  }
  return `${getBackendBaseUrl()}/api/comuns/top/?${params.toString()}`
}

export const buildStaticPageContentUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/content-pages/${encodeURIComponent(slug)}/`
}

const stableId = (input: string): number => {
  let hash = 0
  for (let i = 0; i < input.length; i += 1) {
    hash = (hash << 5) - hash + input.charCodeAt(i)
    hash |= 0
  }
  return Math.abs(hash) || 1
}

export type BackendAuthor = {
  username: string
  title?: string | null
  channel_url?: string | null
  avatar_url?: string | null
  description?: string | null
  subscribers_count?: number
  posts_count?: number
  notify_comments_enabled?: boolean
}

export type BackendTag = {
  id: number
  name: string
  lemma?: string | null
  mood?: string
}

export type BackendComunCategory = {
  id: number
  name: string
  slug: string
  description?: string | null
  sort_order?: number
  only_moderators_can_post?: boolean
  hide_from_home?: boolean
  can_post?: boolean
  allowed_template_types?: string[]
  category_allowed_template_types?: string[]
  inherits_comun_template_types?: boolean
}

export type BackendComunGlossaryTerm = {
  id: number
  term: string
  slug: string
  definition: string
  sort_order?: number
}

export type BackendComunActivityMember = {
  user_id: number
  username: string
  avatar_url?: string | null
  points: number
  rank: number
  stats?: Record<string, number>
}

export type BackendComunActivity = {
  participants_count?: number
  top_members?: BackendComunActivityMember[]
  points?: Record<string, number>
}

export type BackendComunRating = {
  score: number
  upvotes: number
  downvotes: number
  user_vote?: number
}

export type BackendComunCustomTemplateBlock = {
  id?: number
  block_type: string
  placement: 'available' | 'header' | 'footer'
  is_required?: boolean
  sort_order?: number
}

export type BackendComunCustomTemplateField = {
  id?: number
  key?: string
  label: string
  field_type: 'text' | 'file' | 'select' | 'checkbox'
  placement: 'available' | 'header' | 'footer'
  is_required?: boolean
  options?: string[]
  settings?: {
    max_length?: number
    default_checked?: boolean
  }
  sort_order?: number
}

export type BackendComunCustomTemplate = {
  id?: number
  name: string
  slug?: string
  sort_order?: number
  blocks?: BackendComunCustomTemplateBlock[]
  fields?: BackendComunCustomTemplateField[]
}

export type BackendComun = {
  id: number
  name: string
  slug: string
  subscribers_count?: number
  authors_count?: number
  website_url?: string | null
  logo_url?: string | null
  product_description?: string | null
  rules_text?: string | null
  target_audience?: string | null
  glossary_enabled?: boolean
  glossary_auto_link_enabled?: boolean
  roadmap_enabled?: boolean
  knowledge_base_enabled?: boolean
  roadmap_category_ids?: number[]
  roadmap_categories?: BackendComunCategory[]
  glossary_terms?: BackendComunGlossaryTerm[]
  glossary_terms_count?: number
  tags?: BackendTag[]
  tag_ids?: number[]
  minimum_author_rating_to_post?: number
  only_moderators_can_post?: boolean
  forbid_external_links?: boolean
  rating?: BackendComunRating
  hide_from_home?: boolean
  allowed_template_types?: string[]
  allowed_post_templates?: string[]
  template_type_options?: Array<{ value: string; label: string; description?: string }>
  template_editor_blocks_by_template?: Record<string, string[]>
  custom_templates?: BackendComunCustomTemplate[]
  is_active?: boolean
  sort_order?: number
  can_moderate?: boolean
  can_manage_moderators?: boolean
  can_post?: boolean
  can_post_without_category?: boolean
  can_post_category_ids?: number[]
  can_start_post?: boolean
  is_subscribed?: boolean
  creator?: { id?: number; username?: string | null; display_name?: string | null; is_deleted?: boolean }
  moderators?: Array<{ id: number; username: string; display_name?: string | null; is_deleted?: boolean }>
  moderators_count?: number
  moderator_ids?: number[]
  excluded_authors?: Array<{ id: number; username: string; title?: string | null; avatar_url?: string | null }>
  excluded_author_ids?: number[]
  categories?: BackendComunCategory[]
  categories_count?: number
  category_ids?: number[]
  blocked_tags?: BackendTag[]
  excluded_tags?: BackendTag[]
  blocked_tag_ids?: number[]
  excluded_tag_ids?: number[]
  telegram_source_author?: {
    id: number
    username: string
    title?: string | null
    channel_url?: string | null
    avatar_url?: string | null
  } | null
  telegram_source_author_id?: number | null
  telegram_channel_username?: string | null
  welcome_post_id?: number | null
  welcome_post_ref?: string
  welcome_post?: BackendPost | null
  activity?: BackendComunActivity | null
  options?: {
    categories?: BackendComunCategory[]
    tags?: BackendTag[]
    users?: Array<{ id: number; username: string; display_name?: string | null }>
    authors?: Array<{ id: number; username: string; title?: string | null; avatar_url?: string | null }>
    telegram_channels?: Array<{
      id: number
      username: string
      title?: string | null
      channel_url?: string | null
      avatar_url?: string | null
    }>
    template_types?: Array<{ value: string; label: string; description?: string }>
    template_editor_block_options_by_template?: Record<string, Array<{ value: string; label: string }>>
    template_editor_blocks_by_template?: Record<string, string[]>
    custom_template_editor?: {
      block_options?: Array<{ value: string; label: string }>
      block_placement_options?: Array<{ value: string; label: string }>
      field_type_options?: Array<{ value: string; label: string }>
      field_placement_options?: Array<{ value: string; label: string }>
    }
  }
}

export type BackendPostComun = {
  id: number
  name: string
  slug: string
  logo_url?: string | null
  knowledge_base_enabled?: boolean
  can_moderate?: boolean
}

export type BackendComunKnowledgeBaseItem = {
  id: number
  item_type: 'group' | 'post'
  title: string
  parent_id?: number | null
  post_id?: number | null
  post_path?: string | null
  sort_order?: number
  depth?: number
  children?: BackendComunKnowledgeBaseItem[]
}

export type BackendPublicSiteUser = {
  id: number
  username: string
  display_name?: string | null
  avatar_url?: string | null
  posts_count?: number
  comuns_count?: number
  authors_count?: number
  is_staff?: boolean
  is_deleted?: boolean
  first_name?: string | null
  last_name?: string | null
}

export type BackendSiteChatUser = {
  id: number
  username: string
  display_name?: string | null
  avatar_url?: string | null
  profile_url?: string | null
  is_deleted?: boolean
}

export type BackendSiteChatMessage = {
  id: number
  chat_id: number
  sender: BackendSiteChatUser
  sender_id: number
  body: string
  read_at?: string | null
  created_at: string
  updated_at?: string | null
}

export type BackendSiteChat = {
  id: number
  participant: BackendSiteChatUser
  created_at: string
  updated_at?: string | null
  last_message_at?: string | null
  last_message?: BackendSiteChatMessage | null
  unread_count?: number
}

export type BackendSiteChatReportStatus = 'open' | 'reviewed' | 'dismissed'

export type BackendSiteChatReport = {
  id: number
  chat_id: number
  status: BackendSiteChatReportStatus
  status_label?: string
  created_at: string
  updated_at?: string | null
  reviewed_at?: string | null
  reporter: BackendSiteChatUser
  reported_user: BackendSiteChatUser
  reviewed_by?: BackendSiteChatUser | null
  message: {
    id?: number | null
    sender_id?: number | null
    body: string
    created_at?: string | null
  }
}

export type BackendPublicSiteUserComun = {
  id: number
  name: string
  slug: string
  website_url?: string | null
  logo_url?: string | null
  product_description?: string | null
  rules_text?: string | null
  target_audience?: string | null
  tags?: BackendTag[]
  role?: 'creator' | 'moderator' | string
  can_moderate?: boolean
  categories_count?: number
}

export type BackendPublicSiteUserAuthor = {
  id: number
  username: string
  title?: string | null
  channel_url?: string | null
  avatar_url?: string | null
  description?: string | null
}

export type BackendPollOption = {
  index: number
  text: string
  voter_count: number
  post_id?: number
  post_path?: string
}

export type BackendPoll = {
  id?: string | null
  question: string
  is_anonymous: boolean
  allows_multiple_answers: boolean
  is_closed: boolean
  close_at?: string | null
  total_voter_count: number
  options: BackendPollOption[]
  user_selection?: number[]
}

export type BackendPostVotePollParticipation = {
  poll_post_id: number
  poll_post_title: string
  poll_post_path: string
  question: string
  close_at?: string | null
}

export type BackendPostRating = {
  block_id?: string
  scale_min: number
  scale_max: number
  average_value?: number | null
  votes_count: number
  user_vote?: number | null
}

export type BackendBugReportConfirmation = {
  count: number
  confirmed: boolean
}

export type BackendPost = {
  id: number
  title: string
  content: string
  template?: SitePostTemplate | null
  enabled_template_editor_blocks?: string[]
  vote_poll_participations?: BackendPostVotePollParticipation[]
  poll?: BackendPoll | null
  post_ratings?: Record<string, BackendPostRating>
  post_rating?: BackendPostRating | null
  preview_image_url?: string | null
  thumbnail_url?: string | null
  created_at: string
  source_url?: string | null
  channel_url?: string | null
  comun?: BackendPostComun | null
  comun_slug?: string | null
  comments_count?: number
  likes_count?: number
  views_count?: number
  is_favorite?: boolean
  can_manage?: boolean
  can_manage_bug_report_status?: boolean
  bug_report_confirmation?: BackendBugReportConfirmation | null
  tags?: BackendTag[]
  comun_category?: BackendComunCategory | null
  comun_category_id?: number | null
  author?: BackendAuthor
}

export const isSpecialProjectPost = (post: BackendPost | null | undefined): boolean => {
  const username = post?.author?.username?.trim().toLowerCase()
  return username === 'tambur-1001-films'
}

export const backendPostCommunityPath = (post: BackendPost): string | undefined => {
  const comunSlug = post.comun?.slug ?? post.comun_slug
  if (comunSlug) return `/comuns/${encodeURIComponent(comunSlug)}`
  return undefined
}

export const backendPostToPostView = (
  post: BackendPost,
  fallbackAuthor?: BackendAuthor,
  options: { includePreviewMedia?: boolean } = { includePreviewMedia: true }
): PostView => {
  const author = post.author ?? fallbackAuthor
  const authorName = author?.username ?? 'author'
  const authorTitle = author?.title ?? authorName
  const comunName = post.comun?.name ?? undefined
  const comunSlug = post.comun?.slug ?? post.comun_slug ?? undefined
  const comunLogoUrl = post.comun?.logo_url ?? undefined
  const sourceUrl = typeof post.source_url === 'string' ? post.source_url.trim() : ''
  const previewImageUrl =
    typeof post.preview_image_url === 'string' ? post.preview_image_url.trim() : ''
  const thumbnailUrl =
    typeof post.thumbnail_url === 'string' ? post.thumbnail_url.trim() : previewImageUrl
  const authorChannelUrl = typeof author?.channel_url === 'string' ? author.channel_url.trim() : ''
  const communityName = comunSlug ?? `author-${authorName}`
  const communityTitle = comunName ?? authorTitle

  const titleWithTags = post.title

  const creatorId = stableId(authorName)
  const communityId = stableId(communityName)

  return {
    post: {
      id: post.id,
      name: titleWithTags,
      body: post.content,
      template: post.template ?? null,
      enabled_template_editor_blocks: post.enabled_template_editor_blocks ?? [],
      comun_slug: comunSlug,
      comun_category_id: post.comun_category_id ?? null,
      comun_category: post.comun_category ?? null,
      comun_knowledge_base_enabled: Boolean(post.comun?.knowledge_base_enabled),
      comun_can_moderate: Boolean(post.comun?.can_moderate),
      can_manage_bug_report_status: Boolean(post.can_manage_bug_report_status),
      bug_report_confirmation: post.bug_report_confirmation ?? null,
      vote_poll_participations: post.vote_poll_participations ?? [],
      poll: post.poll ?? null,
      post_ratings: post.post_ratings ?? {},
      post_rating: post.post_rating ?? null,
      url: options.includePreviewMedia === false ? '' : previewImageUrl,
      tags: post.tags ?? [],
      published: post.created_at,
      updated: post.created_at,
      nsfw: false,
      locked: false,
      removed: false,
      deleted: false,
      featured_local: false,
      featured_community: false,
      local: true,
      creator_id: creatorId,
      community_id: communityId,
      ap_id: sourceUrl || `https://post.local/${post.id}`,
      embed_description: '',
      thumbnail_url: thumbnailUrl || undefined,
      language_id: 0,
    },
    creator: {
      id: creatorId,
      name: authorName,
      display_name: authorTitle,
      can_manage_backend: Boolean(post.can_manage),
      avatar: author?.avatar_url ?? undefined,
      actor_id: authorChannelUrl || `https://t.me/${authorName}`,
      comuna_notify_comments: author?.notify_comments_enabled,
      local: true,
      admin: false,
      bot_account: false,
      banned: false,
      deleted: false,
      published: post.created_at,
    },
    community: {
      id: communityId,
      name: communityName,
      title: communityTitle,
      actor_id: comunSlug ? `https://comuns.local/${communityName}` : `https://authors.local/${authorName}`,
      icon: comunLogoUrl ?? undefined,
      local: true,
      deleted: false,
      hidden: false,
      nsfw: false,
      published: post.created_at,
      removed: false,
    },
    counts: {
      id: post.id,
      post_id: post.id,
      comments: post.comments_count ?? 0,
      score: post.likes_count ?? 0,
      views: post.views_count ?? 0,
      upvotes: 0,
      downvotes: 0,
      published: post.created_at,
      newest_comment_time: post.created_at,
    },
    creator_is_admin: false,
    creator_is_moderator: false,
    creator_banned_from_community: false,
    banned_from_community: false,
    creator_blocked: false,
    subscribed: 'NotSubscribed',
    saved: Boolean(post.is_favorite),
    read: false,
    hidden: false,
    unread_comments: 0,
    my_vote: 0,
  } as unknown as PostView
}
