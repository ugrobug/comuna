import type { BackendPost } from '$lib/api/backend'
import type { SitePostTemplate } from '$lib/postTemplates'
import { parseSerializedEditorModel, looksLikeSerializedEditorModel } from '$lib/util'
import { slugifyTitle } from '$lib/util/slug'

export type PostLinkSnapshot = {
  post_id: number
  path: string
  title: string
  author_title: string
  author_username: string
  rubric?: string
  rubric_slug?: string
  rubric_icon_url?: string
  preview_text?: string
  preview_image_url?: string
}

export type PostLinkBlockData = {
  url?: string
  announcement?: string
  post_id?: number
  snapshot?: PostLinkSnapshot | null
}

type PostLinkSnapshotSource = Partial<BackendPost> & {
  name?: string | null
  body?: string | null
  preview_text?: string | null
  preview_description?: string | null
  preview_image_url?: string | null
}

const POST_PATH_RE = /\/b\/post\/(\d+)(?:-[^/?#]+)?/i

const trimOrEmpty = (value: unknown): string => (typeof value === 'string' ? value.trim() : '')

const stripHtmlTags = (value: string): string =>
  value
    .replace(/<br\s*\/?>/gi, ' ')
    .replace(/<\/(p|div|li|blockquote|h[1-6])>/gi, ' ')
    .replace(/<[^>]*>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()

const truncateText = (value: string, maxLength = 180): string => {
  const clean = value.replace(/\s+/g, ' ').trim()
  if (clean.length <= maxLength) return clean
  return `${clean.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`
}

const normalizePreviewTextCandidate = (value: string): string => {
  const raw = trimOrEmpty(value)
  if (!raw) return ''

  const parsed = parseSerializedEditorModel(raw)
  if (parsed) {
    return extractPreviewTextFromJson(parsed)
  }

  if (looksLikeSerializedEditorModel(raw)) {
    return ''
  }

  return truncateText(stripHtmlTags(raw))
}

const extractPreviewTextFromJson = (content: any): string => {
  if (trimOrEmpty(content?.additional?.previewDescription)) {
    return truncateText(trimOrEmpty(content.additional.previewDescription))
  }

  const blocks = Array.isArray(content?.blocks) ? content.blocks : []
  for (const block of blocks) {
    const type = trimOrEmpty(block?.type).toLowerCase()
    if (type === 'paragraph') {
      const text = stripHtmlTags(trimOrEmpty(block?.data?.text))
      if (text) return truncateText(text)
    }
    if (type === 'quote') {
      const text = stripHtmlTags(trimOrEmpty(block?.data?.text))
      if (text) return truncateText(text)
    }
    if (type === 'header') {
      const text = stripHtmlTags(trimOrEmpty(block?.data?.text))
      if (text) return truncateText(text)
    }
  }

  return ''
}

const extractPreviewImageFromJson = (content: any): string => {
  const previewImage = trimOrEmpty(content?.additional?.previewImage)
  if (previewImage) return previewImage

  const blocks = Array.isArray(content?.blocks) ? content.blocks : []
  for (const block of blocks) {
    const type = trimOrEmpty(block?.type).toLowerCase()
    if (type === 'image') {
      const imageUrl = trimOrEmpty(block?.data?.file?.url) || trimOrEmpty(block?.data?.url)
      if (imageUrl) return imageUrl
    }
    if (type === 'gallery') {
      const galleryUrl = trimOrEmpty(block?.data?.images?.[0]?.url)
      if (galleryUrl) return galleryUrl
    }
    if (type === 'imagecompare' || type === 'compare') {
      const compareUrl =
        trimOrEmpty(block?.data?.before?.url) || trimOrEmpty(block?.data?.after?.url)
      if (compareUrl) return compareUrl
    }
  }

  return ''
}

const extractPreviewTextFromContent = (rawContent: string): string => {
  const content = trimOrEmpty(rawContent)
  if (!content) return ''

  if (content.startsWith('{') && content.endsWith('}')) {
    try {
      return extractPreviewTextFromJson(JSON.parse(content))
    } catch {
      return ''
    }
  }

  const parsed = parseSerializedEditorModel(content)
  if (parsed) {
    return extractPreviewTextFromJson(parsed)
  }

  if (looksLikeSerializedEditorModel(content)) {
    return ''
  }

  return truncateText(stripHtmlTags(content))
}

const extractPreviewImageFromContent = (rawContent: string): string => {
  const content = trimOrEmpty(rawContent)
  if (!content) return ''

  if (content.startsWith('{') && content.endsWith('}')) {
    try {
      return extractPreviewImageFromJson(JSON.parse(content))
    } catch {
      return ''
    }
  }

  const parsed = parseSerializedEditorModel(content)
  if (parsed) {
    return extractPreviewImageFromJson(parsed)
  }

  if (looksLikeSerializedEditorModel(content)) {
    return ''
  }

  return ''
}

const extractTemplatePreviewImage = (template: SitePostTemplate | null | undefined): string => {
  if (!template || typeof template !== 'object') return ''
  if (template.type === 'movie_review') {
    return trimOrEmpty(template.data?.poster_url)
  }
  if (template.type === 'music_release') {
    return trimOrEmpty(template.data?.cover_image_url)
  }
  return ''
}

const resolvePostTitle = (post: PostLinkSnapshotSource): string =>
  trimOrEmpty(post.title) || trimOrEmpty(post.name)

const resolvePostContent = (post: PostLinkSnapshotSource): string =>
  trimOrEmpty(post.content) || trimOrEmpty(post.body)

export const buildPostPublicPath = (postId: number, title?: string | null): string => {
  const normalizedId = Number.isFinite(postId) ? Math.floor(postId) : 0
  if (normalizedId <= 0) return ''
  const slug = slugifyTitle(trimOrEmpty(title))
  return slug ? `/b/post/${normalizedId}-${slug}` : `/b/post/${normalizedId}`
}

export const extractInternalPostId = (value: string): number | null => {
  const raw = trimOrEmpty(value)
  if (!raw) return null

  if (/^\d+$/.test(raw)) {
    const numeric = Number(raw)
    return Number.isFinite(numeric) && numeric > 0 ? Math.floor(numeric) : null
  }

  const pathMatch = raw.match(POST_PATH_RE)
  if (pathMatch?.[1]) {
    const numeric = Number(pathMatch[1])
    return Number.isFinite(numeric) && numeric > 0 ? Math.floor(numeric) : null
  }

  try {
    const parsed = new URL(raw)
    const match = parsed.pathname.match(POST_PATH_RE)
    if (!match?.[1]) return null
    const numeric = Number(match[1])
    return Number.isFinite(numeric) && numeric > 0 ? Math.floor(numeric) : null
  } catch {
    return null
  }
}

export const isInternalPostReference = (value: string): boolean => {
  return extractInternalPostId(value) !== null
}

export const normalizeInternalPostReference = (
  value: string,
  title?: string | null
): { postId: number | null; path: string } => {
  const postId = extractInternalPostId(value)
  if (!postId) return { postId: null, path: '' }

  const raw = trimOrEmpty(value)
  if (raw.startsWith('/')) {
    const match = raw.match(POST_PATH_RE)
    return { postId, path: match?.[0] || buildPostPublicPath(postId, title) }
  }

  try {
    const parsed = new URL(raw)
    const match = parsed.pathname.match(POST_PATH_RE)
    if (match?.[0]) {
      return { postId, path: match[0] }
    }
  } catch {
    return { postId, path: buildPostPublicPath(postId, title) }
  }

  return { postId, path: buildPostPublicPath(postId, title) }
}

export const buildPostLinkSnapshot = (post: PostLinkSnapshotSource): PostLinkSnapshot => {
  const postId = Number(post.id)
  const title = resolvePostTitle(post)
  const authorUsername = trimOrEmpty(post.author?.username) || 'author'
  const authorTitle = trimOrEmpty(post.author?.title) || authorUsername
  const path = buildPostPublicPath(postId, title)
  const rawContent = resolvePostContent(post)
  const previewImageUrl =
    trimOrEmpty(post.preview_image_url) ||
    extractTemplatePreviewImage(post.template) ||
    extractPreviewImageFromContent(rawContent)
  const previewText =
    normalizePreviewTextCandidate(trimOrEmpty(post.preview_text)) ||
    normalizePreviewTextCandidate(trimOrEmpty(post.preview_description)) ||
    extractPreviewTextFromContent(rawContent)

  const snapshot: PostLinkSnapshot = {
    post_id: postId,
    path,
    title,
    author_title: authorTitle,
    author_username: authorUsername,
  }

  const rubric = trimOrEmpty(post.rubric)
  const rubricSlug = trimOrEmpty(post.rubric_slug)
  const rubricIconUrl = trimOrEmpty(post.rubric_icon_url)

  if (rubric) snapshot.rubric = rubric
  if (rubricSlug) snapshot.rubric_slug = rubricSlug
  if (rubricIconUrl) snapshot.rubric_icon_url = rubricIconUrl
  if (previewText) snapshot.preview_text = previewText
  if (previewImageUrl) snapshot.preview_image_url = previewImageUrl

  return snapshot
}

export const normalizePostLinkBlockData = (value: unknown): PostLinkBlockData => {
  const raw = value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
  const snapshotRaw =
    raw.snapshot && typeof raw.snapshot === 'object'
      ? (raw.snapshot as Record<string, unknown>)
      : null

  const normalizedUrl = trimOrEmpty(raw.url)
  const snapshot =
    snapshotRaw && Number(snapshotRaw.post_id) > 0
      ? {
          post_id: Math.floor(Number(snapshotRaw.post_id)),
          path:
            trimOrEmpty(snapshotRaw.path) ||
            buildPostPublicPath(
              Math.floor(Number(snapshotRaw.post_id)),
              trimOrEmpty(snapshotRaw.title)
            ),
          title: trimOrEmpty(snapshotRaw.title),
          author_title: trimOrEmpty(snapshotRaw.author_title),
          author_username: trimOrEmpty(snapshotRaw.author_username),
          rubric: trimOrEmpty(snapshotRaw.rubric) || undefined,
          rubric_slug: trimOrEmpty(snapshotRaw.rubric_slug) || undefined,
          rubric_icon_url: trimOrEmpty(snapshotRaw.rubric_icon_url) || undefined,
          preview_text: trimOrEmpty(snapshotRaw.preview_text) || undefined,
          preview_image_url: trimOrEmpty(snapshotRaw.preview_image_url) || undefined,
        }
      : null

  const postIdCandidate = Number(raw.post_id ?? snapshot?.post_id ?? extractInternalPostId(normalizedUrl))
  const postId = Number.isFinite(postIdCandidate) && postIdCandidate > 0 ? Math.floor(postIdCandidate) : undefined
  const normalized = normalizeInternalPostReference(
    normalizedUrl || snapshot?.path || (postId ? String(postId) : ''),
    snapshot?.title
  )

  return {
    url: normalized.path || snapshot?.path || '',
    announcement: trimOrEmpty(raw.announcement),
    post_id: normalized.postId ?? postId,
    snapshot,
  }
}
