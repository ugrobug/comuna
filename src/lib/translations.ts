import i18n, { type Config } from 'sveltekit-i18n'

const config: Config = {
  loaders: [
    {
      locale: 'en',
      key: '',
      loader: async () => (await import('./i18n/en.json')).default,
    },
    {
      locale: 'he',
      key: '',
      loader: async () => (await import('./i18n/he.json')).default,
    },
    {
      locale: 'id',
      key: '',
      loader: async () => (await import('./i18n/id.json')).default,
    },
    {
      locale: 'bg',
      key: '',
      loader: async () => (await import('./i18n/bg.json')).default,
    },
    {
      locale: 'de',
      key: '',
      loader: async () => (await import('./i18n/de.json')).default,
    },
    {
      locale: 'es',
      key: '',
      loader: async () => (await import('./i18n/es.json')).default,
    },
    {
      locale: 'et',
      key: '',
      loader: async () => (await import('./i18n/et.json')).default,
    },
    {
      locale: 'fi',
      key: '',
      loader: async () => (await import('./i18n/fi.json')).default,
    },
    {
      locale: 'fr',
      key: '',
      loader: async () => (await import('./i18n/fr.json')).default,
    },
    {
      locale: 'hu',
      key: '',
      loader: async () => (await import('./i18n/hu.json')).default,
    },
    {
      locale: 'ja',
      key: '',
      loader: async () => (await import('./i18n/ja.json')).default,
    },
    {
      locale: 'nl',
      key: '',
      loader: async () => (await import('./i18n/nl.json')).default,
    },
    {
      locale: 'pl',
      key: '',
      loader: async () => (await import('./i18n/pl.json')).default,
    },
    {
      locale: 'pt',
      key: '',
      loader: async () => (await import('./i18n/pt.json')).default,
    },
    {
      locale: 'ru',
      key: '',
      loader: async () => (await import('./i18n/ru.json')).default,
    },
    {
      locale: 'tr',
      key: '',
      loader: async () => (await import('./i18n/tr.json')).default,
    },
    {
      locale: 'zh-Hans',
      key: '',
      loader: async () => (await import('./i18n/zh-Hans.json')).default,
    },
    {
      locale: 'zh-Hant',
      key: '',
      loader: async () => (await import('./i18n/zh-Hant.json')).default,
    },
  ],
  fallbackLocale: 'ru',
}

export const aliases = new Map([
  ['zh-CN', 'zh-Hans'],
  ['zh-TW', 'zh-Hant'],
  ['en-US', 'en'],
  ['en-GB', 'en'],
  ['en-AU', 'en'],
  ['en-CA', 'en'],
  ['fr-FR', 'fr'],
  ['fr-CA', 'fr'],
  ['fr-BE', 'fr'],
  ['es-ES', 'es'],
  ['es-MX', 'es'],
  ['es-AR', 'es'],
  ['de-DE', 'de'],
  ['de-AT', 'de'],
  ['de-CH', 'de'],
  ['pt-BR', 'pt'],
  ['pt-PT', 'pt'],
  ['tr-TR', 'tr'],
  ['id-ID', 'id'],
  ['fi-FI', 'fi'],
  ['et-EE', 'et'],
  ['he-IL', 'he'],
])

export type TranslationInstance = InstanceType<typeof i18n>

const clientTranslations = new i18n(config)
const requestTranslationResolverSymbol = Symbol.for('tambur.request-translations')

type RequestTranslationGlobal = typeof globalThis & {
  [requestTranslationResolverSymbol]?: () => TranslationInstance | undefined
}

const activeTranslations = (): TranslationInstance =>
  (globalThis as RequestTranslationGlobal)[requestTranslationResolverSymbol]?.() ??
  clientTranslations

export const createTranslationInstance = (): TranslationInstance => new i18n(config)

export const registerRequestTranslationResolver = (
  resolver: () => TranslationInstance | undefined
) => {
  ;(globalThis as RequestTranslationGlobal)[requestTranslationResolverSymbol] = resolver
}

type TranslationFunction = (key: string, ...params: any[]) => any

export const t = {
  subscribe: (run: (value: TranslationFunction) => void, invalidate?: (value?: any) => void) =>
    activeTranslations().t.subscribe(run as any, invalidate as any),
  get: ((key: string, ...params: any[]) =>
    activeTranslations().t.get(key, ...params)) as TranslationFunction,
}

export const locale = {
  subscribe: (...args: Parameters<TranslationInstance['locale']['subscribe']>) =>
    activeTranslations().locale.subscribe(...args),
  set: (...args: Parameters<TranslationInstance['locale']['set']>) =>
    activeTranslations().locale.set(...args),
  update: (...args: Parameters<TranslationInstance['locale']['update']>) =>
    activeTranslations().locale.update(...args),
  get: () => activeTranslations().locale.get(),
  forceSet: (...args: Parameters<TranslationInstance['locale']['forceSet']>) =>
    activeTranslations().locale.forceSet(...args),
}

export const locales = {
  subscribe: (...args: Parameters<TranslationInstance['locales']['subscribe']>) =>
    activeTranslations().locales.subscribe(...args),
  get: () => activeTranslations().locales.get(),
}

export const loading = {
  subscribe: (...args: Parameters<TranslationInstance['loading']['subscribe']>) =>
    activeTranslations().loading.subscribe(...args),
  get: () => activeTranslations().loading.get(),
  toPromise: (...args: Parameters<TranslationInstance['loading']['toPromise']>) =>
    activeTranslations().loading.toPromise(...args),
}

export const loadTranslations = (
  ...args: Parameters<TranslationInstance['loadTranslations']>
) => activeTranslations().loadTranslations(...args)
