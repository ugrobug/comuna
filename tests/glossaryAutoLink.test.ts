import { describe, expect, it } from 'vitest'
import {
  applyGlossaryAutoLinkMatches,
  findGlossaryAutoLinkMatches,
} from '../src/lib/glossaryAutoLink'

const encodeEditorPayload = (payload: unknown) =>
  Buffer.from(JSON.stringify(payload), 'utf-8').toString('base64')

const decodeEditorPayload = (payload: string) =>
  JSON.parse(Buffer.from(payload, 'base64').toString('utf-8'))

describe('glossary auto linking', () => {
  it('finds standalone glossary terms in EditorJS text', () => {
    const content = encodeEditorPayload({
      blocks: [
        {
          type: 'paragraph',
          data: {
            text: 'Терминтак не матчим, а Термин и термин матчим. <a href="/x">Термин</a> <code>Термин</code>',
          },
        },
      ],
    })

    const terms = [{ term: 'Термин', slug: 'termin', definition: 'Новый термин' }]
    const matches = findGlossaryAutoLinkMatches(content, terms)

    expect(matches.map((match) => match.matchedText)).toEqual(['Термин', 'термин'])

    const nextContent = applyGlossaryAutoLinkMatches(
      content,
      terms,
      matches.map((match) => match.id)
    )
    const nextPayload = decodeEditorPayload(nextContent)
    const nextText = nextPayload.blocks[0].data.text

    expect(nextText).toContain('Терминтак')
    expect(nextText.match(/post-glossary-term/g)).toHaveLength(2)
    expect(nextText).toContain('data-glossary-slug="termin"')
  })
})
