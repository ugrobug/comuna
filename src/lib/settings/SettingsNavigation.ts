export type SettingsTabKey = 'about' | 'notifications' | 'interface' | 'feed'

/** URL navigation for settings, including links saved before tabs existed. */
export class SettingsNavigation {
  readonly keys: readonly SettingsTabKey[] = ['about', 'notifications', 'interface', 'feed']
  private readonly legacySections: Record<string, SettingsTabKey> = {
    account: 'about', 'comuna-profile': 'about', 'linked-channels': 'about', max: 'about',
    notifications: 'notifications', 'notifications-history': 'notifications',
    app: 'interface', 'my-feed': 'feed',
  }

  resolve(url: URL, signedIn: boolean): SettingsTabKey {
    const section = this.legacySections[url.hash.slice(1)]
    if (Object.prototype.hasOwnProperty.call(this.legacySections, url.hash.slice(1))) return section
    const requested = url.searchParams.get('tab')
    return this.keys.includes(requested as SettingsTabKey)
      ? requested as SettingsTabKey
      : signedIn ? 'about' : 'interface'
  }

  href(url: URL, key: SettingsTabKey): string {
    const next = new URL(url)
    next.searchParams.set('tab', key)
    next.hash = ''
    return `${next.pathname}${next.search}`
  }
}
