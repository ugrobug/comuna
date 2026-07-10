import { describe, expect, it } from 'vitest'
import { getLocalizedDefaultStaticPage } from '../src/lib/staticPageContent'

const decodeEditorPayload = (payload: string) =>
  JSON.parse(Buffer.from(payload, 'base64').toString('utf-8'))

describe('localized static page fallbacks', () => {
  it.each([
    ['en', 'Apps', 'Read your feed'],
    ['es', 'Aplicaciones', 'Lee tu feed'],
    ['pt', 'Aplicativos', 'Leia seu feed'],
    ['de', 'Apps', 'Lies deinen Feed'],
    ['fr', 'Applications', 'Consultez votre fil'],
    ['tr', 'Uygulamalar', 'Akışınızı'],
    ['id', 'Aplikasi', 'Baca feed'],
  ] as const)('provides the apps page in %s', (language, title, intro) => {
    const page = getLocalizedDefaultStaticPage('apps', language)
    const payload = decodeEditorPayload(page.content)

    expect(page.title).toBe(title)
    expect(payload.blocks[0].data.text).toContain(intro)
    expect(payload.blocks[1].data.text).toContain('Google Play')
    expect(payload.blocks[1].data.text).toContain('RuStore')
  })
})
