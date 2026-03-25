import type { BackendAuthor } from '$lib/api/backend'

export type AuthorBlockSnapshot = {
  username: string
  title: string
  path: string
  avatar_url?: string
}

export type AuthorBlockData = {
  caption?: string
  username?: string
  snapshot?: AuthorBlockSnapshot | null
}

const trimOrEmpty = (value: unknown): string => (typeof value === 'string' ? value.trim() : '')

export const buildAuthorPublicPath = (username: string | null | undefined): string => {
  const normalized = trimOrEmpty(username)
  if (!normalized) return ''
  return `/${encodeURIComponent(normalized)}`
}

export const buildAuthorBlockSnapshot = (
  author: Partial<BackendAuthor> | null | undefined
): AuthorBlockSnapshot | null => {
  const username = trimOrEmpty(author?.username)
  if (!username) return null

  const title = trimOrEmpty(author?.title) || username
  const avatarUrl = trimOrEmpty(author?.avatar_url)
  return {
    username,
    title,
    path: buildAuthorPublicPath(username),
    avatar_url: avatarUrl || undefined,
  }
}

export const normalizeAuthorBlockData = (value: unknown): AuthorBlockData => {
  const raw = value && typeof value === 'object' ? (value as Record<string, unknown>) : {}
  const snapshotRaw =
    raw.snapshot && typeof raw.snapshot === 'object'
      ? (raw.snapshot as Record<string, unknown>)
      : null

  const snapshotUsername =
    trimOrEmpty(snapshotRaw?.username) || trimOrEmpty(raw.username)

  const snapshot =
    snapshotUsername
      ? {
          username: snapshotUsername,
          title: trimOrEmpty(snapshotRaw?.title) || snapshotUsername,
          path: trimOrEmpty(snapshotRaw?.path) || buildAuthorPublicPath(snapshotUsername),
          avatar_url: trimOrEmpty(snapshotRaw?.avatar_url) || undefined,
        }
      : null

  return {
    caption: trimOrEmpty(raw.caption),
    username: snapshot?.username || undefined,
    snapshot,
  }
}
