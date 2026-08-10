import { AsyncLocalStorage } from 'node:async_hooks'
import type { PostLanguageCode } from '$lib/postLanguages'
import {
  createTranslationInstance,
  registerRequestTranslationResolver,
  type TranslationInstance,
} from '$lib/translations'

const requestTranslations = new AsyncLocalStorage<TranslationInstance>()
const translationsByLanguage = new Map<
  PostLanguageCode,
  Promise<TranslationInstance>
>()

registerRequestTranslationResolver(() => requestTranslations.getStore())

const translationInstanceForLanguage = (language: PostLanguageCode) => {
  const existing = translationsByLanguage.get(language)
  if (existing) return existing

  const pending = (async () => {
    const instance = createTranslationInstance()
    await instance.loadTranslations(language)
    return instance
  })()
  translationsByLanguage.set(language, pending)
  return pending
}

export const runWithRequestTranslations = async <T>(
  language: PostLanguageCode,
  callback: () => T | Promise<T>
): Promise<T> => {
  const instance = await translationInstanceForLanguage(language)
  return requestTranslations.run(instance, callback)
}
