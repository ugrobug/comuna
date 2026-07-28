import { describe, expect, it } from 'vitest'
import { stringifyJsonLd, toWellFormedUnicode, truncateUnicodeText } from './seoJsonLd'

describe('SEO JSON-LD Unicode handling', () => {
  it('does not split an emoji at the description limit', () => {
    const description = `${'a'.repeat(199)}🥹tail`
    const truncated = truncateUnicodeText(description, 200)
    const json = stringifyJsonLd({ description: truncated })

    expect(truncated).toBe(`${'a'.repeat(199)}🥹…`)
    expect(JSON.parse(json)).toEqual({ description: truncated })
    expect(json).not.toMatch(/\\ud83e(?!\\udd79)/i)
  })

  it('replaces unpaired UTF-16 surrogates before serialization', () => {
    const malformed = `before${String.fromCharCode(0xd83e)}after`

    expect(toWellFormedUnicode(malformed)).toBe('before�after')
    expect(JSON.parse(stringifyJsonLd({ value: malformed }))).toEqual({
      value: 'before�after',
    })
  })

  it('escapes characters that can break an embedded script tag', () => {
    const json = stringifyJsonLd({ value: '</script>&' })

    expect(json).toBe('{"value":"\\u003c/script\\u003e\\u0026"}')
  })
})
