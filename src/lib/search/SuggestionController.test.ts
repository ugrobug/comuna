import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { SuggestionController } from './SuggestionController'

describe('SuggestionController', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('does no work on creation and debounces rapid input into the last query', async () => {
    const load = vi.fn().mockResolvedValue({ payload: 'result', cacheable: true })
    const changed = vi.fn()
    const controller = new SuggestionController(load, changed)
    expect(load).not.toHaveBeenCalled()
    controller.search('ки'); controller.search('кин'); controller.search('кино')
    await vi.advanceTimersByTimeAsync(220)
    expect(load).toHaveBeenCalledTimes(1)
    expect(load.mock.calls[0][0]).toBe('кино')
    expect(changed).toHaveBeenLastCalledWith({ open: true, loading: false, payload: 'result' })
  })

  it('aborts and ignores an old response immediately, including during the next debounce', async () => {
    let resolve: (value: unknown) => void = () => {}
    const load = vi.fn().mockImplementation(() => new Promise(done => { resolve = done }))
    const changed = vi.fn()
    const controller = new SuggestionController(load, changed)
    controller.search('кино')
    await vi.advanceTimersByTimeAsync(220)
    const signal = load.mock.calls[0][1] as AbortSignal
    controller.search('спорт')
    expect(signal.aborted).toBe(true)
    resolve({ payload: 'old', cacheable: true })
    await Promise.resolve()
    expect(changed).toHaveBeenLastCalledWith({ open: true, loading: true })
    controller.close()
    await vi.advanceTimersByTimeAsync(220)
    expect(load).toHaveBeenCalledTimes(1)
  })

  it('clearing, closing and destruction cancel pending requests', async () => {
    const load = vi.fn()
    const changed = vi.fn()
    const controller = new SuggestionController(load, changed)
    controller.search('ки'); controller.search('к')
    await vi.advanceTimersByTimeAsync(220)
    expect(load).not.toHaveBeenCalled()
    expect(changed).toHaveBeenLastCalledWith({ open: false, loading: false })
    controller.search('кино'); controller.close()
    controller.search('спорт'); controller.destroy()
    await vi.advanceTimersByTimeAsync(220)
    expect(load).not.toHaveBeenCalled()
  })

  it('reuses only public responses within the short TTL', async () => {
    const load = vi.fn().mockResolvedValue({ payload: 'result', cacheable: true })
    const controller = new SuggestionController(load, vi.fn())
    controller.search('кино')
    await vi.advanceTimersByTimeAsync(220)
    controller.close(); controller.search('кино')
    expect(load).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(10_001)
    controller.search('кино')
    await vi.advanceTimersByTimeAsync(220)
    expect(load).toHaveBeenCalledTimes(2)
    controller.destroy()
  })

  it('does not cache private/dynamic invitations and recovers after an error', async () => {
    const load = vi.fn().mockResolvedValue({ payload: 'private', cacheable: false })
    const changed = vi.fn()
    const controller = new SuggestionController(load, changed)
    controller.search('кино')
    await vi.advanceTimersByTimeAsync(220)
    controller.close(); controller.search('кино')
    await vi.advanceTimersByTimeAsync(220)
    expect(load).toHaveBeenCalledTimes(2)
    load.mockRejectedValueOnce(new Error('offline'))
    controller.search('спорт')
    await vi.advanceTimersByTimeAsync(220)
    expect(changed).toHaveBeenLastCalledWith({ open: true, loading: false, failed: true })
    controller.search('спорт')
    await vi.advanceTimersByTimeAsync(220)
    expect(changed).toHaveBeenLastCalledWith({ open: true, loading: false, payload: 'private' })
  })
})
