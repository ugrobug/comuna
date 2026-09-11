import { afterEach, describe, expect, it, vi } from 'vitest'
import { scheduleError, toLocalDateTime } from './postSchedule'

afterEach(() => vi.useRealTimers())

describe('publication time', () => {
  it('allows immediate publication and rejects invalid or elapsed dates', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2030-02-01T12:00:00Z'))
    expect(scheduleError(null)).toBe('')
    expect(scheduleError('')).toBe('')
    expect(scheduleError('invalid')).not.toBe('')
    expect(scheduleError('2030-02-01T15:00:00+03:00')).not.toBe('')
    expect(scheduleError('2030-02-01T15:01:00+03:00')).toBe('')
  })

  it('round-trips a saved date through the local date/time input', () => {
    const instant = '2030-02-01T23:30:00Z'
    expect(new Date(toLocalDateTime(instant)).toISOString()).toBe(instant.replace('00Z', '00.000Z'))
  })

  it('keeps empty or malformed saved dates out of the date/time input', () => {
    expect(toLocalDateTime(null)).toBe('')
    expect(toLocalDateTime('invalid')).toBe('')
  })
})
