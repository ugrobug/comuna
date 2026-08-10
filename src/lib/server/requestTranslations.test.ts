import { describe, expect, it } from 'vitest'
import { t } from '$lib/translations'
import { runWithRequestTranslations } from './requestTranslations'

const wait = (milliseconds: number) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds))

describe('request-scoped translations', () => {
  it('keeps concurrent SSR locales isolated', async () => {
    const [russian, english, portuguese] = await Promise.all([
      runWithRequestTranslations('ru', async () => {
        await wait(8)
        return t.get('nav.home')
      }),
      runWithRequestTranslations('en', async () => {
        await wait(4)
        return t.get('nav.home')
      }),
      runWithRequestTranslations('pt', async () => {
        await wait(1)
        return t.get('nav.home')
      }),
    ])

    expect(russian).toBe('Главная')
    expect(english).toBe('Home')
    expect(portuguese).toBe('Página inicial')
  })
})
