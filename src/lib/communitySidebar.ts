import type { BackendComun } from '$lib/api/backend'

const comunNameCollator = new Intl.Collator('ru', { sensitivity: 'base' })

export const normalizeComunSlug = (slug?: string | null) =>
  String(slug ?? '').trim().toLowerCase()

const comunRatingScore = (comun: BackendComun) => Number(comun.rating?.score ?? 0) || 0

const comunSortOrder = (comun: BackendComun) => Number(comun.sort_order ?? 0) || 0

export const sortComunsByRating = (comuns: BackendComun[]) =>
  [...comuns].sort((left, right) => {
    const ratingDiff = comunRatingScore(right) - comunRatingScore(left)
    if (ratingDiff) return ratingDiff

    const sortOrderDiff = comunSortOrder(left) - comunSortOrder(right)
    if (sortOrderDiff) return sortOrderDiff

    return comunNameCollator.compare(left.name ?? '', right.name ?? '')
  })

export const selectSidebarComuns = (
  comuns: BackendComun[],
  subscribedSlugs: string[] | undefined,
  subscriptionsReady: boolean,
  limit = 10
) => {
  if (!subscriptionsReady) {
    return {
      items: [] as BackendComun[],
      total: 0,
    }
  }

  const rankedComuns = sortComunsByRating(comuns)
  const subscribedSlugSet = new Set(
    (subscribedSlugs ?? []).map(normalizeComunSlug).filter(Boolean)
  )
  const implicitManagedSlugSet = new Set(
    rankedComuns
      .filter((comun) => Boolean(comun.can_moderate))
      .map((comun) => normalizeComunSlug(comun.slug))
      .filter(Boolean)
  )
  const subscribedComuns = rankedComuns.filter((comun) =>
    subscribedSlugSet.has(normalizeComunSlug(comun.slug)) ||
    implicitManagedSlugSet.has(normalizeComunSlug(comun.slug))
  )
  const sourceComuns = subscribedComuns.length ? subscribedComuns : rankedComuns

  return {
    items: sourceComuns.slice(0, limit),
    total: sourceComuns.length,
  }
}
