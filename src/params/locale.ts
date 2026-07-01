import type { ParamMatcher } from '@sveltejs/kit'
import { translatedPostLanguages } from '$lib/postLanguages'

export const match: ParamMatcher = (param) =>
  translatedPostLanguages.includes(param as (typeof translatedPostLanguages)[number])
