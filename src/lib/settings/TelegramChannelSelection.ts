import type { BackendComun } from '$lib/api/backend'

/** A confirmed channel option is not a persisted community connection. */
export class TelegramChannelSelection {
  constructor(readonly saved: BackendComun | null, readonly draft: BackendComun | null) {}

  static snapshot(value: BackendComun | null) {
    return {
      author_id: Number(value?.telegram_source_author_id ?? value?.telegram_source_author?.id ?? 0) || null,
      username: String(value?.telegram_channel_username ?? value?.telegram_source_author?.username ?? '')
        .trim().replace(/^https?:\/\/t\.me\//i, '').replace(/^@/, '').split(/[/?#]/, 1)[0].toLowerCase(),
    }
  }

  get changed() {
    return JSON.stringify(TelegramChannelSelection.snapshot(this.saved)) !==
      JSON.stringify(TelegramChannelSelection.snapshot(this.draft))
  }

  get connected() {
    return Boolean(TelegramChannelSelection.snapshot(this.saved).author_id) && !this.changed
  }

  patch() {
    if (!this.changed) return {}
    const next = TelegramChannelSelection.snapshot(this.draft)
    return {
      telegram_source_author_id: next.author_id,
      telegram_channel_username: next.username,
    }
  }

  refresh(server: BackendComun) {
    const link = {
      telegram_source_author_id: server.telegram_source_author_id ?? server.telegram_source_author?.id ?? null,
      telegram_channel_username: server.telegram_channel_username ?? '',
      telegram_source_author: server.telegram_source_author ?? null,
    }
    return {
      saved: { ...this.saved, ...link } as BackendComun,
      draft: this.changed ? this.draft : { ...this.draft, ...link } as BackendComun,
    }
  }
}
