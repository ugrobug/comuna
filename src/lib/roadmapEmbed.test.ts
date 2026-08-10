import { describe, expect, it } from 'vitest'
import {
  buildComunRoadmapEmbedCode,
  buildComunRoadmapEmbedPath,
  buildComunRoadmapPagePath,
  roadmapEmbedCardLabel,
  roadmapEmbedLabels,
} from './roadmapEmbed'

describe('roadmap embed helpers', () => {
  it('builds localized public paths', () => {
    expect(buildComunRoadmapEmbedPath('product team', 'ru')).toBe(
      '/embed/roadmap/product%20team'
    )
    expect(buildComunRoadmapEmbedPath('product team', 'en')).toBe(
      '/en/embed/roadmap/product%20team'
    )
    expect(buildComunRoadmapPagePath('product team', 'de')).toBe(
      '/de/comuns/product%20team/roadmap'
    )
  })

  it('returns labels for supported languages and falls back to Russian', () => {
    expect(roadmapEmbedLabels('en').inProgress).toBe('In progress')
    expect(roadmapEmbedLabels('unknown').inProgress).toBe('В работе')
    expect(roadmapEmbedCardLabel('ru', 1)).toBe('карточка')
    expect(roadmapEmbedCardLabel('ru', 2)).toBe('карточки')
    expect(roadmapEmbedCardLabel('ru', 5)).toBe('карточек')
    expect(roadmapEmbedCardLabel('en', 1)).toBe('card')
    expect(roadmapEmbedCardLabel('en', 2)).toBe('cards')
  })

  it('escapes generated iframe attributes', () => {
    const code = buildComunRoadmapEmbedCode({
      baseUrl: 'https://tambur.pub/',
      slug: 'roadmap',
      language: 'en',
      communityName: 'A "roadmap" & team',
    })

    expect(code).toContain('src="https://tambur.pub/en/embed/roadmap/roadmap"')
    expect(code).toContain('title="Roadmap — A &quot;roadmap&quot; &amp; team"')
    expect(code).toContain('width="100%" height="720"')
  })
})
