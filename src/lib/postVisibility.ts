import type { BackendPost } from '$lib/api/backend'
import type { Settings } from '$lib/settings'
import { getTagKey, getTagName, normalizeTag } from '$lib/tags'

export type HiddenContentReasonKind = 'post' | 'author' | 'community' | 'tag'

export type HiddenContentReason = {
  kind: HiddenContentReasonKind
  values: Array<string | number>
  label?: string
}

const normalizeHiddenValue = (value: unknown): string =>
  String(value ?? '').trim().toLowerCase()

export const getBackendPostHiddenReasons = (
  post: BackendPost,
  settings: Pick<Settings, 'hiddenAuthors' | 'hiddenPostIds' | 'hiddenComuns' | 'tagRules'>
): HiddenContentReason[] => {
  const reasons: HiddenContentReason[] = []

  if ((settings.hiddenPostIds ?? []).includes(post.id)) {
    reasons.push({ kind: 'post', values: [post.id] })
  }

  const author = normalizeHiddenValue(post.author?.username)
  if (
    author &&
    (settings.hiddenAuthors ?? []).some((value) => normalizeHiddenValue(value) === author)
  ) {
    reasons.push({ kind: 'author', values: [author], label: post.author?.username ?? author })
  }

  const community = normalizeHiddenValue(post.comun?.slug ?? post.comun_slug)
  if (
    community &&
    (settings.hiddenComuns ?? []).some((value) => normalizeHiddenValue(value) === community)
  ) {
    reasons.push({
      kind: 'community',
      values: [community],
      label: post.comun?.name ?? post.comun?.slug ?? post.comun_slug ?? community,
    })
  }

  for (const tag of post.tags ?? []) {
    const tagName = getTagName(tag)
    const keys = Array.from(
      new Set([getTagKey(tag), normalizeTag(tagName)].map(normalizeHiddenValue).filter(Boolean))
    )
    const hiddenKeys = keys.filter((key) => settings.tagRules?.[key] === 'hide')
    if (hiddenKeys.length) {
      reasons.push({ kind: 'tag', values: hiddenKeys, label: tagName })
    }
  }

  return reasons
}

export const clearHiddenContentReasons = (
  settings: Settings,
  reasons: HiddenContentReason[]
): Settings => {
  const postIds = new Set(
    reasons
      .filter((reason) => reason.kind === 'post')
      .flatMap((reason) => reason.values)
      .map(Number)
      .filter(Number.isFinite)
  )
  const authors = new Set(
    reasons
      .filter((reason) => reason.kind === 'author')
      .flatMap((reason) => reason.values)
      .map(normalizeHiddenValue)
      .filter(Boolean)
  )
  const communities = new Set(
    reasons
      .filter((reason) => reason.kind === 'community')
      .flatMap((reason) => reason.values)
      .map(normalizeHiddenValue)
      .filter(Boolean)
  )
  const tagKeys = new Set(
    reasons
      .filter((reason) => reason.kind === 'tag')
      .flatMap((reason) => reason.values)
      .map(normalizeHiddenValue)
      .filter(Boolean)
  )
  const tagRules = { ...(settings.tagRules ?? {}) }
  for (const key of tagKeys) delete tagRules[key]

  return {
    ...settings,
    hiddenPostIds: (settings.hiddenPostIds ?? []).filter((id) => !postIds.has(id)),
    hiddenAuthors: (settings.hiddenAuthors ?? []).filter(
      (value) => !authors.has(normalizeHiddenValue(value))
    ),
    hiddenComuns: (settings.hiddenComuns ?? []).filter(
      (value) => !communities.has(normalizeHiddenValue(value))
    ),
    tagRules,
  }
}

export const isBackendPostVisible = (
  post: BackendPost,
  settings: Pick<Settings, 'hiddenAuthors' | 'hiddenPostIds' | 'hiddenComuns'>
): boolean => {
  if ((settings.hiddenPostIds ?? []).includes(post.id)) return false

  const author = (post.author?.username ?? '').trim().toLowerCase()
  if (author && (settings.hiddenAuthors ?? []).some((value) => value.trim().toLowerCase() === author)) {
    return false
  }

  const comun = (post.comun?.slug ?? post.comun_slug ?? '').trim().toLowerCase()
  if (comun && (settings.hiddenComuns ?? []).some((value) => value.trim().toLowerCase() === comun)) {
    return false
  }

  return true
}

export type PostTagRule = 'blur' | 'hide' | undefined

export const shouldHidePostContent = (rule: PostTagRule, showFullBody: boolean) =>
  rule === 'hide' && !showFullBody
