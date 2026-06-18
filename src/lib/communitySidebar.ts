import { browser } from '$app/environment'
import { buildComunsSidebarUrl, type BackendComun } from '$lib/api/backend'
import { cachedJson, invalidateCachedJson } from '$lib/api/publicCache'
import { writable } from 'svelte/store'

const comunNameCollator = new Intl.Collator('ru', { sensitivity: 'base' })
const SIDEBAR_COMUNS_CACHE_KEY = 'public:sidebar-comuns'
const SIDEBAR_COMUNS_TTL_MS = 21_600_000

export const sidebarComunsStore = writable<BackendComun[]>([])
export const sidebarComunsLoaded = writable(false)
export const sidebarComunsLoading = writable(false)

let sidebarComunsPromise: Promise<BackendComun[]> | null = null
let sidebarComunsRequestId = 0

export const loadSidebarComuns = async (options: { force?: boolean } = {}) => {
  if (!browser) return []
  const force = Boolean(options.force)
  if (force) {
    invalidateCachedJson(SIDEBAR_COMUNS_CACHE_KEY)
    sidebarComunsPromise = null
    sidebarComunsRequestId += 1
  }
  if (sidebarComunsPromise) return sidebarComunsPromise

  const requestId = sidebarComunsRequestId
  sidebarComunsLoading.set(true)
  sidebarComunsPromise = cachedJson<{ comuns?: BackendComun[] }>(
    SIDEBAR_COMUNS_CACHE_KEY,
    buildComunsSidebarUrl(),
    { ttlMs: SIDEBAR_COMUNS_TTL_MS }
  )
    .then((data) => {
      const comuns = data.comuns ?? []
      if (requestId === sidebarComunsRequestId) {
        sidebarComunsStore.set(comuns)
        sidebarComunsLoaded.set(true)
      }
      return comuns
    })
    .catch((error) => {
      if (requestId === sidebarComunsRequestId) {
        sidebarComunsStore.set([])
        sidebarComunsLoaded.set(true)
      }
      console.error('Failed to load sidebar communities:', error)
      return []
    })
    .finally(() => {
      if (requestId === sidebarComunsRequestId) {
        sidebarComunsLoading.set(false)
        sidebarComunsPromise = null
      }
    })

  return sidebarComunsPromise
}

export const refreshSidebarComuns = () => loadSidebarComuns({ force: true })

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
