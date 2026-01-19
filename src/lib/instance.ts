// maybe fix circular dependency, hopefully.

import { browser } from '$app/environment'
import { env } from '$env/dynamic/public'
import { writable } from 'svelte/store'

const normalizeInstance = (value?: string) => {
  if (!value) return undefined
  const trimmed = value.trim()
  if (!trimmed || trimmed === 'undefined' || trimmed === 'null') return undefined
  return trimmed
}

export const PUBLIC_INSTANCE_URL = normalizeInstance(env.PUBLIC_INSTANCE_URL)
export const PUBLIC_INTERNAL_INSTANCE = normalizeInstance(env.PUBLIC_INTERNAL_INSTANCE)
export const HAS_LEMMY_INSTANCE = Boolean(PUBLIC_INSTANCE_URL)

export const LINKED_INSTANCE_URL =
  (env.PUBLIC_LOCK_TO_INSTANCE ?? 'true').toLowerCase() == 'true'
    ? PUBLIC_INSTANCE_URL
    : undefined

const getDefaultInstance = (): string => {
  if (browser) {
    return PUBLIC_INSTANCE_URL ?? ''
  }
  return PUBLIC_INTERNAL_INSTANCE ?? PUBLIC_INSTANCE_URL ?? ''
}

export const DEFAULT_INSTANCE_URL = getDefaultInstance()
export let instance = writable(DEFAULT_INSTANCE_URL)
