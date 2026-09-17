import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest'
vi.mock('$lib/util', () => ({ deserializeEditorModel: JSON.parse }))
vi.mock('$lib/translations', () => ({ locale: { subscribe: () => () => {} }, t: { subscribe: () => () => {} } }))
import { buildPostTemplatePayload, createEmptyCompanionTemplateData, normalizeCompanionTemplateData, validateCompanionTemplate } from './index'

beforeEach(() => { vi.useFakeTimers(); vi.setSystemTime(new Date('2030-02-01T12:00:00Z')) })
afterEach(() => vi.useRealTimers())
const invitation = () => ({ ...createEmptyCompanionTemplateData(), description: 'Прогулка', lat: 0, lng: 0, starts_at: '2030-02-02T15:00:00+03:00' })

describe('companion template', () => {
  it('preserves the chosen point and optional radius through editor serialization', () => {
    const data = invitation()
    const payload = buildPostTemplatePayload('companion', null, null, null, null, null, data)
    expect(payload).toEqual({ type: 'companion', version: 1, data: { ...data, starts_at: '2030-02-02T12:00:00.000Z' } })
    expect(normalizeCompanionTemplateData(payload?.data)).toEqual(payload?.data)
    expect(validateCompanionTemplate(data)).toBe('')
  })
  it('requires a point, description and future meeting, but allows drafts to remain incomplete', () => {
    expect(buildPostTemplatePayload('companion', null)?.type).toBe('companion')
    for (const change of [{ lat: null }, { description: '' }, { starts_at: '' }, { starts_at: '2030-02-01T12:00:00Z' }, { radius_m: -1 }]) {
      expect(validateCompanionTemplate({ ...invitation(), ...change })).not.toBe('')
    }
    expect(validateCompanionTemplate(invitation(), '2030-02-03T00:00:00Z')).not.toBe('')
  })
})
