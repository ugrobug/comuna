<script lang="ts">
  import { onMount } from 'svelte'
  import { toast } from 'mono-svelte'
  import {
    fetchSiteNotificationSettings,
    siteToken,
    siteUser,
    type SiteNotificationEventSetting,
    updateSiteNotificationSettings,
  } from '$lib/siteAuth'
  import NotificationSettingsSection from './NotificationSettingsSection.svelte'

  let notificationEvents: SiteNotificationEventSetting[] = []
  let notificationSettingsLoading = false
  let notificationSettingsSaving = false
  let notificationSettingsLoaded = false
  let notificationSettingsLoadAttempted = false
  let notificationTelegramLinked = false
  let notificationTelegramUsername = ''
  let notificationTelegramFirstName = ''
  let notificationPushConfigured = false
  let notificationPushRegisteredDevicesCount = 0
  let notificationPushPlatforms: string[] = []
  let notificationSettingsSaveVersion = 0

  const resetNotificationSettingsState = () => {
    notificationEvents = []
    notificationSettingsLoading = false
    notificationSettingsSaving = false
    notificationSettingsLoaded = false
    notificationSettingsLoadAttempted = false
    notificationTelegramLinked = false
    notificationTelegramUsername = ''
    notificationTelegramFirstName = ''
    notificationPushConfigured = false
    notificationPushRegisteredDevicesCount = 0
    notificationPushPlatforms = []
    notificationSettingsSaveVersion += 1
  }

  const notificationSettingsPayload = (events: SiteNotificationEventSetting[]) =>
    events.map((event) => ({
      key: event.key,
      site_enabled: event.site_enabled,
      telegram_enabled: event.telegram_enabled,
      push_enabled: event.push_enabled,
      grouping_period: event.grouping_period,
    }))

  const saveNotificationSettingsNow = async (
    events: SiteNotificationEventSetting[],
    previousEvents: SiteNotificationEventSetting[]
  ) => {
    if (!$siteUser) {
      toast({ content: 'Нужна авторизация', type: 'error' })
      notificationEvents = previousEvents
      return
    }

    const saveVersion = ++notificationSettingsSaveVersion
    notificationSettingsSaving = true
    try {
      const data = await updateSiteNotificationSettings(notificationSettingsPayload(events))
      if (saveVersion !== notificationSettingsSaveVersion) return
      notificationEvents = data.events ?? []
      notificationTelegramLinked = Boolean(data.telegram?.linked)
      notificationTelegramUsername = data.telegram?.username ?? ''
      notificationTelegramFirstName = data.telegram?.first_name ?? ''
      notificationPushConfigured = Boolean(data.push?.configured)
      notificationPushRegisteredDevicesCount = Number(data.push?.registered_devices_count || 0)
      notificationPushPlatforms = data.push?.active_platforms ?? []
    } catch (error) {
      if (saveVersion === notificationSettingsSaveVersion) {
        notificationEvents = previousEvents
        toast({
          content:
            (error as Error)?.message ?? 'Не удалось сохранить настройки оповещений',
          type: 'error',
        })
      }
    } finally {
      if (saveVersion === notificationSettingsSaveVersion) {
        notificationSettingsSaving = false
      }
    }
  }

  const loadSiteNotificationSettings = async () => {
    if (notificationSettingsLoading || !$siteToken) return
    notificationSettingsLoadAttempted = true
    notificationSettingsLoading = true
    try {
      const data = await fetchSiteNotificationSettings()
      notificationEvents = data.events ?? []
      notificationTelegramLinked = Boolean(data.telegram?.linked)
      notificationTelegramUsername = data.telegram?.username ?? ''
      notificationTelegramFirstName = data.telegram?.first_name ?? ''
      notificationPushConfigured = Boolean(data.push?.configured)
      notificationPushRegisteredDevicesCount = Number(data.push?.registered_devices_count || 0)
      notificationPushPlatforms = data.push?.active_platforms ?? []
      notificationSettingsLoaded = true
    } catch (error) {
      toast({
        content:
          (error as Error)?.message ?? 'Не удалось загрузить настройки оповещений',
        type: 'error',
      })
    } finally {
      notificationSettingsLoading = false
    }
  }

  const toggleNotificationEventChannel = (
    index: number,
    channel: 'site' | 'telegram' | 'push',
    value: boolean
  ) => {
    const next = [...notificationEvents]
    const item = next[index]
    if (!item) return
    const previousEvents = notificationEvents
    next[index] = {
      ...item,
      site_enabled: channel === 'site' ? value : item.site_enabled,
      telegram_enabled: channel === 'telegram' ? value : item.telegram_enabled,
      push_enabled: channel === 'push' ? value : item.push_enabled,
    }
    notificationEvents = next
    saveNotificationSettingsNow(next, previousEvents).catch(() => {})
  }

  const updateNotificationEventGrouping = (
    index: number,
    groupingPeriod: 'none' | 'day' | 'week'
  ) => {
    const next = [...notificationEvents]
    const item = next[index]
    if (!item || !item.supports_grouping) return
    const previousEvents = notificationEvents
    next[index] = {
      ...item,
      grouping_period: groupingPeriod,
    }
    notificationEvents = next
    saveNotificationSettingsNow(next, previousEvents).catch(() => {})
  }

  onMount(() => {
    if ($siteToken) {
      loadSiteNotificationSettings().catch(() => {})
    }
  })

  $: if (
    $siteToken &&
    !notificationSettingsLoaded &&
    !notificationSettingsLoading &&
    !notificationSettingsLoadAttempted
  ) {
    loadSiteNotificationSettings().catch(() => {})
  }

  $: if (
    !$siteToken &&
    (notificationSettingsLoaded ||
      notificationSettingsLoadAttempted ||
      notificationEvents.length > 0)
  ) {
    resetNotificationSettingsState()
  }
</script>

<NotificationSettingsSection
  events={notificationEvents}
  loading={notificationSettingsLoading}
  saving={notificationSettingsSaving}
  telegramLinked={notificationTelegramLinked}
  telegramUsername={notificationTelegramUsername}
  telegramFirstName={notificationTelegramFirstName}
  pushConfigured={notificationPushConfigured}
  pushRegisteredDevicesCount={notificationPushRegisteredDevicesCount}
  pushPlatforms={notificationPushPlatforms}
  on:toggle={(event) =>
    toggleNotificationEventChannel(
      event.detail.index,
      event.detail.channel,
      event.detail.value
    )}
  on:grouping={(event) =>
    updateNotificationEventGrouping(
      event.detail.index,
      event.detail.groupingPeriod
    )}
/>
