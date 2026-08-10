import type { SiteUser } from '$lib/siteAuth'
import type { BackendFeedSettings } from '$lib/settings'

export type AuthBootstrap = {
  user: SiteUser
  settings: BackendFeedSettings
}
