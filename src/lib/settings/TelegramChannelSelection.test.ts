import { describe, it, expect } from 'vitest'
import type { BackendComun } from '$lib/api/backend'
import { TelegramChannelSelection } from './TelegramChannelSelection'

const community = (fields = {}) => ({ id: 1, slug: 'community', ...fields }) as BackendComun
const linked = () => community({ telegram_channel_username: 'channel', telegram_source_author_id: 7,
  telegram_source_author: { id: 7, username: 'channel' } })

describe('Telegram community selection', () => {
  it('does not send stale empty channel fields when saving another setting', () => {
    const saved = community()
    const draft = community({ product_description: 'New description' })
    expect(new TelegramChannelSelection(saved, draft).patch()).toEqual({})
  })
  it('does not call a locally selected confirmed channel connected before save', () => {
    const selection = new TelegramChannelSelection(community(), linked())
    expect(selection.connected).toBe(false)
    expect(selection.changed).toBe(true)
    expect(selection.patch()).toEqual({ telegram_source_author_id: 7, telegram_channel_username: 'channel' })
    expect(new TelegramChannelSelection(linked(), linked()).connected).toBe(true)
  })
  it('refreshes the server link without losing an edited description', () => {
    const selection = new TelegramChannelSelection(community(), community({ product_description: 'Unsaved' }))
    const result = selection.refresh(linked())
    expect(result.draft?.product_description).toBe('Unsaved')
    expect(new TelegramChannelSelection(result.saved, result.draft).patch()).toEqual({})
    expect(new TelegramChannelSelection(result.saved, result.draft).connected).toBe(true)
  })
  it('preserves an intentional different channel selection while refreshing', () => {
    const draft = community({ telegram_channel_username: 'other' })
    const result = new TelegramChannelSelection(community(), draft).refresh(linked())
    expect(result.draft?.telegram_channel_username).toBe('other')
    expect(new TelegramChannelSelection(result.saved, result.draft).changed).toBe(true)
  })
  it('allows explicit disconnection and treats equivalent URLs as unchanged', () => {
    expect(new TelegramChannelSelection(linked(), community()).patch()).toEqual({
      telegram_source_author_id: null, telegram_channel_username: '',
    })
    const url = linked(); url.telegram_channel_username = 'https://t.me/CHANNEL'
    expect(new TelegramChannelSelection(linked(), url).changed).toBe(false)
  })
})
