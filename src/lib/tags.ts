export type TagItem = string | { name: string; lemma?: string | null }

export const normalizeTag = (value: string): string => value.trim().toLowerCase()

export const getTagName = (tag: TagItem): string =>
  typeof tag === 'string' ? tag : tag.name

export const getTagLemma = (tag: TagItem): string => {
  if (typeof tag === 'string') return normalizeTag(tag)
  const lemma = tag.lemma ?? tag.name
  return normalizeTag(lemma)
}

export const getTagKey = (tag: TagItem): string => getTagLemma(tag)
