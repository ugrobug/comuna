import { browser } from '$app/environment'
import { env } from '$env/dynamic/public'
import type { SitePostTemplate } from '$lib/postTemplates'
import { slugifyTitle } from '$lib/util/slug'

export const getBackendBaseUrl = (): string => {
  if (!browser) {
    const base = env.PUBLIC_INTERNAL_BACKEND_URL || ''
    return base.replace(/\/$/, '')
  }
  const base = env.PUBLIC_BACKEND_URL || 'http://localhost:8000'
  return base.replace(/\/$/, '')
}

export const buildAuthorPostsUrl = (username: string): string => {
  return `${getBackendBaseUrl()}/api/authors/${encodeURIComponent(username)}/posts/`
}

export const buildRubricsUrl = (options?: { includeHidden?: boolean }): string => {
  const base = `${getBackendBaseUrl()}/api/rubrics/`
  if (!options?.includeHidden) {
    return base
  }
  const params = new URLSearchParams({ include_hidden: '1' })
  return `${base}?${params.toString()}`
}

export const buildRubricPostsUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/rubrics/${encodeURIComponent(slug)}/posts/`
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

export const buildTagsListUrl = (): string => {
  return `${getBackendBaseUrl()}/api/tags/`
}

export const buildTagsEnsureUrl = (): string => {
  return `${getBackendBaseUrl()}/api/tags/ensure/`
}

export const buildThematicFeedsListUrl = (): string => {
  return `${getBackendBaseUrl()}/api/thematic-feeds/`
}

export const buildComunsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/comuns/`
}

export const buildComunUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/`
}

export const buildComunVoteUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/comuns/${encodeURIComponent(slug)}/vote/`
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

export const buildThematicFeedPostsUrl = (
  slug: string,
  options?: {
    hideRead?: boolean
    onlyRead?: boolean
  }
): string => {
  const base = `${getBackendBaseUrl()}/api/thematic-feeds/${encodeURIComponent(slug)}/posts/`
  const params = new URLSearchParams()
  if (options?.onlyRead) {
    params.set('only_read', '1')
  } else if (options?.hideRead) {
    params.set('hide_read', '1')
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildThematicFeedsManageUrl = (slug?: string): string => {
  const base = `${getBackendBaseUrl()}/api/thematic-feeds/manage/`
  if (!slug) return base
  return `${base}${encodeURIComponent(slug)}/`
}

export const buildBackendPostPath = (post: { id: number; title: string }): string => {
  const slug = slugifyTitle(post.title)
  return slug ? `/b/post/${post.id}-${slug}` : `/b/post/${post.id}`
}

export const buildHomeFeedUrl = (options?: {
  hideRead?: boolean
  onlyRead?: boolean
}): string => {
  const base = `${getBackendBaseUrl()}/api/home/`
  const params = new URLSearchParams()
  if (options?.onlyRead) {
    params.set('only_read', '1')
  } else if (options?.hideRead) {
    params.set('hide_read', '1')
  }
  const query = params.toString()
  return query ? `${base}?${query}` : base
}

export const buildFreshFeedUrl = (options?: {
  hideRead?: boolean
  onlyRead?: boolean
}): string => {
  const base = `${getBackendBaseUrl()}/api/home/fresh/`
  const params = new URLSearchParams()
  if (options?.onlyRead) {
    params.set('only_read', '1')
  } else if (options?.hideRead) {
    params.set('hide_read', '1')
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
  rubrics?: string[],
  authors?: string[],
  tags?: string[],
  comuns?: string[],
  hideNegative: boolean = true,
  hideRead: boolean = false,
  onlyRead: boolean = false
): string => {
  const base = `${getBackendBaseUrl()}/api/home/my/`
  const params = new URLSearchParams()
  if (rubrics?.length) {
    params.set('rubrics', rubrics.join(','))
  }
  if (authors?.length) {
    params.set('authors', authors.join(','))
  }
  if (tags?.length) {
    params.set('tags', tags.join(','))
  }
  if (comuns?.length) {
    params.set('comuns', comuns.join(','))
  }
  if (!hideNegative) {
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

export const buildTopAuthorsMonthUrl = (limit = 5): string => {
  const params = new URLSearchParams({ limit: String(limit) })
  return `${getBackendBaseUrl()}/api/authors/top-month/?${params.toString()}`
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
  name: string
  lemma?: string | null
  mood?: string
}

export type BackendThematicFeedAuthor = {
  id?: number
  username: string
  title?: string | null
}

export type BackendThematicFeedRubric = {
  id?: number
  name: string
  slug?: string | null
  description?: string | null
}

export type BackendThematicFeed = {
  id?: number
  name: string
  slug: string
  description?: string | null
  is_active?: boolean
  sort_order?: number
  moderators_count?: number
  authors_count?: number
  excluded_authors_count?: number
  rubrics_count?: number
  tags_count?: number
  blocked_tags_count?: number
  moderators?: Array<{ id: number; username: string }>
  authors?: BackendThematicFeedAuthor[]
  excluded_authors?: BackendThematicFeedAuthor[]
  rubrics?: BackendThematicFeedRubric[]
  tags?: BackendTag[]
  blocked_tags?: BackendTag[]
  excluded_tags?: BackendTag[]
  moderator_ids?: number[]
  author_ids?: number[]
  excluded_author_ids?: number[]
  rubric_ids?: number[]
  tag_ids?: number[]
  excluded_tag_ids?: number[]
}

export type BackendComunCategory = {
  id: number
  name: string
  slug: string
  description?: string | null
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

export type BackendComun = {
  id: number
  name: string
  slug: string
  website_url?: string | null
  logo_url?: string | null
  product_description?: string | null
  target_audience?: string | null
  rating?: BackendComunRating
  hide_from_home?: boolean
  hide_from_fresh?: boolean
  allowed_template_types?: string[]
  allowed_post_templates?: string[]
  template_editor_blocks_by_template?: Record<string, string[]>
  is_active?: boolean
  sort_order?: number
  can_moderate?: boolean
  can_manage_moderators?: boolean
  creator?: { id?: number; username?: string | null; display_name?: string | null }
  moderators?: Array<{ id: number; username: string; display_name?: string | null }>
  moderators_count?: number
  moderator_ids?: number[]
  categories?: BackendComunCategory[]
  categories_count?: number
  category_ids?: number[]
  product_tag?: { id: number; name: string; lemma?: string | null } | null
  product_tag_id?: number | null
  welcome_post_id?: number | null
  welcome_post_ref?: string
  welcome_post?: BackendPost | null
  activity?: BackendComunActivity | null
  options?: {
    categories?: BackendComunCategory[]
    tags?: BackendTag[]
    users?: Array<{ id: number; username: string; display_name?: string | null }>
    template_types?: Array<{ value: string; label: string }>
    template_editor_block_options_by_template?: Record<string, Array<{ value: string; label: string }>>
    template_editor_blocks_by_template?: Record<string, string[]>
  }
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
  first_name?: string | null
  last_name?: string | null
}

export type BackendPublicSiteUserComun = {
  id: number
  name: string
  slug: string
  website_url?: string | null
  logo_url?: string | null
  product_description?: string | null
  target_audience?: string | null
  role?: 'creator' | 'moderator' | string
  can_moderate?: boolean
  categories_count?: number
  product_tag?: { id: number; name: string; lemma?: string | null } | null
}

export type BackendPublicSiteUserAuthor = {
  id: number
  username: string
  title?: string | null
  channel_url?: string | null
  avatar_url?: string | null
  description?: string | null
  rubric?: string | null
  rubric_slug?: string | null
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

export type BackendPost = {
  id: number
  title: string
  content: string
  template?: SitePostTemplate | null
  vote_poll_participations?: BackendPostVotePollParticipation[]
  poll?: BackendPoll | null
  created_at: string
  source_url?: string | null
  channel_url?: string | null
  rubric?: string | null
  rubric_slug?: string | null
  rubric_icon_url?: string | null
  comments_count?: number
  likes_count?: number
  views_count?: number
  is_favorite?: boolean
  tags?: BackendTag[]
  comun_category?: BackendComunCategory | null
  comun_category_id?: number | null
  author?: BackendAuthor
}

export const backendPostToPostView = (
  post: BackendPost,
  fallbackAuthor?: BackendAuthor
) => {
  const author = post.author ?? fallbackAuthor
  const authorName = author?.username ?? 'author'
  const authorTitle = author?.title ?? authorName
  const rubricName = post.rubric ?? undefined
  const rubricSlug = post.rubric_slug ?? undefined
  const sourceUrl = typeof post.source_url === 'string' ? post.source_url.trim() : ''
  const authorChannelUrl = typeof author?.channel_url === 'string' ? author.channel_url.trim() : ''
  const communityName =
    rubricSlug ?? (rubricName ? rubricName.toLowerCase().replace(/\s+/g, '-') : 'no-rubric')
  const communityTitle = rubricName ?? 'Без рубрики'

  const titleWithTags = post.title

  const creatorId = stableId(authorName)
  const communityId = rubricSlug ? stableId(rubricSlug) : stableId(`${authorName}-rubric`)

  return {
    post: {
      id: post.id,
      name: titleWithTags,
      body: post.content,
      template: post.template ?? null,
      vote_poll_participations: post.vote_poll_participations ?? [],
      poll: post.poll ?? null,
      url: '',
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
      thumbnail_url: null,
      language_id: 0,
    },
    creator: {
      id: creatorId,
      name: authorName,
      display_name: authorTitle,
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
      actor_id: `https://rubrics.local/${communityName}`,
      icon: post.rubric_icon_url ?? undefined,
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
    subscribed: 'NotSubscribed',
    saved: Boolean(post.is_favorite),
    read: false,
    hidden: false,
    my_vote: 0,
  }
}
