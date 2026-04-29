import type { BackendThematicFeed } from '$lib/api/backend'
import { normalizeTag } from '$lib/tags'

type UserSettingsLike = {
  myFeedRubrics?: string[]
  myFeedAuthors?: string[]
  myFeedTags?: string[]
  myFeedComuns?: string[]
  myFeedComunCategories?: Record<string, string[]>
  hiddenAuthors?: string[]
  tagRules?: Record<string, 'hide' | 'blur'>
}

export const hasMyFeedCustomizations = (settings: UserSettingsLike) => {
  const rubrics = settings.myFeedRubrics ?? []
  const authors = settings.myFeedAuthors ?? []
  const tags = settings.myFeedTags ?? []
  const comuns = settings.myFeedComuns ?? []
  const comunCategories = settings.myFeedComunCategories ?? {}
  const hiddenAuthors = settings.hiddenAuthors ?? []
  const tagRules = settings.tagRules ?? {}
  return (
    rubrics.length > 0 ||
    authors.length > 0 ||
    tags.length > 0 ||
    comuns.length > 0 ||
    Object.keys(comunCategories).length > 0 ||
    hiddenAuthors.length > 0 ||
    Object.keys(tagRules).length > 0
  )
}

export const buildMyFeedSettingsFromFolderPreset = (
  settings: UserSettingsLike,
  folderPreset: BackendThematicFeed
) => {
  const authors = Array.from(
    new Set(
      (folderPreset.authors ?? [])
        .map((author) => (author?.username ?? '').trim())
        .filter(Boolean)
    )
  )
  const excludedAuthors = Array.from(
    new Set(
      (folderPreset.excluded_authors ?? [])
        .map((author) => (author?.username ?? '').trim())
        .filter(Boolean)
    )
  )
  const rubrics = Array.from(
    new Set(
      (folderPreset.rubrics ?? [])
        .map((rubric) => (rubric?.slug ?? '').trim())
        .filter(Boolean)
    )
  )
  const includedTags = Array.from(
    new Set(
      (folderPreset.tags ?? [])
        .map((tag) => normalizeTag(tag?.lemma ?? tag?.name ?? ''))
        .filter(Boolean)
    )
  )
  const nextTagRules: Record<string, 'hide' | 'blur'> = {
    ...(settings.tagRules ?? {}),
  }
  for (const [key, value] of Object.entries(nextTagRules)) {
    if (value === 'hide') {
      delete nextTagRules[key]
    }
  }
  for (const tag of folderPreset.blocked_tags ?? []) {
    const normalized = normalizeTag(tag?.lemma ?? tag?.name ?? '')
    if (!normalized) continue
    nextTagRules[normalized] = 'hide'
  }
  return {
    ...settings,
    myFeedRubrics: rubrics,
    myFeedAuthors: authors,
    myFeedTags: includedTags,
    hiddenAuthors: excludedAuthors,
    tagRules: nextTagRules,
  }
}
