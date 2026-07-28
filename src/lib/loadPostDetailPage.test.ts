import { describe, expect, it } from 'vitest'
import { canonicalPostRedirectPath } from './postCanonicalPath'

const canonicalPath =
  '/en/b/post/13455-where-the-good-doctor-2017-was-filmed'

describe('loadPostDetailPage canonical URL', () => {
  it('returns the canonical target for an outdated localized slug', () => {
    expect(
      canonicalPostRedirectPath(
        '/en/b/post/13455-where-was-the-good-doctor-filmed',
        canonicalPath
      )
    ).toBe(canonicalPath)
  })

  it('does not redirect the canonical localized path', () => {
    expect(canonicalPostRedirectPath(canonicalPath, canonicalPath)).toBeNull()
  })
})
