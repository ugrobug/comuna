import { env } from '$env/dynamic/public'
import { slugifyTitle } from '$lib/util/slug'

export const getBackendBaseUrl = (): string => {
  const base = env.PUBLIC_BACKEND_URL || 'http://localhost:8000'
  return base.replace(/\/$/, '')
}

export const buildAuthorPostsUrl = (username: string): string => {
  return `${getBackendBaseUrl()}/api/authors/${encodeURIComponent(username)}/posts/`
}

export const buildRubricsUrl = (): string => {
  return `${getBackendBaseUrl()}/api/rubrics/`
}

export const buildRubricPostsUrl = (slug: string): string => {
  return `${getBackendBaseUrl()}/api/rubrics/${encodeURIComponent(slug)}/posts/`
}

export const buildPostDetailUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/`
}

export const buildPostCommentsUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/comments/`
}

export const buildPostLikeUrl = (id: number | string): string => {
  return `${getBackendBaseUrl()}/api/posts/${encodeURIComponent(id)}/like/`
}

export const buildBackendPostPath = (post: { id: number; title: string }): string => {
  const slug = slugifyTitle(post.title)
  return slug ? `/b/post/${post.id}-${slug}` : `/b/post/${post.id}`
}

export const buildHomeFeedUrl = (): string => {
  return `${getBackendBaseUrl()}/api/home/`
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
}

export type BackendPost = {
  id: number
  title: string
  content: string
  created_at: string
  source_url?: string | null
  channel_url?: string | null
  rubric?: string | null
  rubric_slug?: string | null
  rubric_icon_url?: string | null
  comments_count?: number
  likes_count?: number
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

  const titleWithTags = post.title

  const creatorId = stableId(authorName)
  const communityId = rubricSlug ? stableId(rubricSlug) : stableId(`${authorName}-rubric`)

  return {
    post: {
      id: post.id,
      name: titleWithTags,
      body: post.content,
      url: '',
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
      ap_id: post.source_url ?? `https://post.local/${post.id}`,
      embed_description: '',
      thumbnail_url: null,
      language_id: 0,
    },
    creator: {
      id: creatorId,
      name: authorName,
      display_name: authorTitle,
      avatar: author?.avatar_url ?? undefined,
      actor_id: author?.channel_url ?? `https://t.me/${authorName}`,
      local: true,
      admin: false,
      bot_account: false,
      banned: false,
      deleted: false,
      published: post.created_at,
    },
    community: rubricName
      ? {
          id: communityId,
          name: rubricSlug ?? rubricName.toLowerCase().replace(/\s+/g, '-'),
          title: rubricName,
          actor_id: `https://rubrics.local/${rubricSlug ?? rubricName}`,
          icon: post.rubric_icon_url ?? undefined,
          local: true,
          deleted: false,
          hidden: false,
          nsfw: false,
          published: post.created_at,
          removed: false,
        }
      : undefined,
    counts: {
      id: post.id,
      post_id: post.id,
      comments: post.comments_count ?? 0,
      score: post.likes_count ?? 0,
      upvotes: 0,
      downvotes: 0,
      published: post.created_at,
      newest_comment_time: post.created_at,
    },
    creator_is_admin: false,
    creator_is_moderator: false,
    creator_banned_from_community: false,
    subscribed: 'NotSubscribed',
    saved: false,
    read: false,
    hidden: false,
    my_vote: 0,
  }
}
