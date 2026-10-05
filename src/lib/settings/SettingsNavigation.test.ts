import { describe, expect, it } from 'vitest'
import { SettingsNavigation } from './SettingsNavigation'

const navigation = new SettingsNavigation()
const url = (value = '') => new URL(`https://tambur.pub/settings${value}`)

describe('settings tab navigation', () => {
  it('defaults to profile for a signed-in user and interface for a guest', () => {
    expect(navigation.resolve(url(), true)).toBe('about')
    expect(navigation.resolve(url(), false)).toBe('interface')
  })
  it.each(navigation.keys)('retains explicit tab %s through reload for any visitor', (tab) => {
    expect(navigation.resolve(url(`?tab=${tab}`), true)).toBe(tab)
    expect(navigation.resolve(url(`?tab=${tab}`), false)).toBe(tab)
  })
  it.each([
    ['notifications', 'notifications'], ['notifications-history', 'notifications'],
    ['comuna-profile', 'about'], ['linked-channels', 'about'], ['max', 'about'],
    ['account', 'about'], ['app', 'interface'], ['my-feed', 'feed'],
  ])('preserves legacy anchor %s', (anchor, tab) => {
    expect(navigation.resolve(url(`#${anchor}`), true)).toBe(tab)
    expect(navigation.resolve(url(`?tab=about#${anchor}`), true)).toBe(tab)
  })
  it('ignores unknown or inherited keys', () => {
    expect(navigation.resolve(url('?tab=unknown#unknown'), true)).toBe('about')
    expect(navigation.resolve(url('?tab=__proto__#__proto__'), false)).toBe('interface')
  })
  it('retains unrelated parameters and removes obsolete anchors when switching', () => {
    const original = url('?next=%2Fid10&tab=about#notifications')
    const target = navigation.href(original, 'feed')
    expect(target).toBe('/settings?next=%2Fid10&tab=feed')
    expect(original.hash).toBe('#notifications')
  })
})
