<script lang="ts">
  import { defaultSettings, userSettings } from '$lib/settings'
  import Setting from './Setting.svelte'
  import { toast, Modal, TextArea, TextInput } from 'mono-svelte'
  import {
    ArrowDownTray,
    ArrowPath,
    ArrowRight,
    ArrowUpTray,
    Icon,
    ArrowTopRightOnSquare,
  } from 'svelte-hero-icons'
  import { Button, Select } from 'mono-svelte'
  import Section from './Section.svelte'
  import ToggleSetting from './ToggleSetting.svelte'
  import { t } from '$lib/translations'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { profile } from '$lib/auth'
  import { buildRubricsUrl, buildTagsListUrl } from '$lib/api/backend'
  import { normalizeTag } from '$lib/tags'
  import {
    fetchVerificationCode,
    fetchSiteNotificationSettings,
    refreshSiteUser,
    siteToken,
    siteUser,
    type SiteNotificationEventSetting,
    updateSiteNotificationSettings,
    updateSiteProfile,
    uploadSiteImage,
  } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import { colorScheme, inDarkColorScheme } from '$lib/ui/colors'
  let importing = false
  let importText = ''
  let myFeedRubrics: Array<{ name: string; slug: string }> = []
  let myFeedRubricsLoading = false
  let manualBlacklistTag = ''
  let tagLemmaMap = new Map<string, string>()
  let siteProfileDisplayName = ''
  let siteProfileAvatarUrl = ''
  let siteProfileSaving = false
  let siteProfileAvatarUploading = false
  let siteProfileFileInput: HTMLInputElement | null = null
  let lastSiteUserSnapshot: string | null = null
  let channelVerificationCode = ''
  let channelVerificationCodeLoading = false
  let channelVerificationCodeError = ''
  let notificationEvents: SiteNotificationEventSetting[] = []
  let notificationSettingsLoading = false
  let notificationSettingsSaving = false
  let notificationSettingsLoaded = false
  let notificationSettingsLoadAttempted = false
  let notificationTelegramLinked = false
  let notificationTelegramUsername = ''
  let notificationTelegramFirstName = ''
  let notificationSettingsSnapshot = '[]'
  let notificationSettingsDirty = false
  $: myFeedAuthors = $userSettings.myFeedAuthors ?? []
  $: hiddenAuthors = $userSettings.hiddenAuthors ?? []
  $: blacklistedTags = Object.entries($userSettings.tagRules ?? {})
    .filter(([, rule]) => rule === 'hide')
    .map(([tag]) => tag)

  const removeBlacklistedTag = (tag: string) => {
    const nextRules = { ...($userSettings.tagRules ?? {}) }
    delete nextRules[tag]
    $userSettings = { ...$userSettings, tagRules: nextRules }
  }

  const addBlacklistedTag = () => {
    const normalized = normalizeTag(manualBlacklistTag)
    if (!normalized) return
    const lemma = tagLemmaMap.get(normalized) ?? normalized
    $userSettings = {
      ...$userSettings,
      tagRules: { ...($userSettings.tagRules ?? {}), [lemma]: 'hide' },
    }
    manualBlacklistTag = ''
  }

  const clearBlacklistedTags = () => {
    $userSettings = { ...$userSettings, tagRules: {} }
  }

  const loadMyFeedRubrics = async () => {
    if (myFeedRubricsLoading) return
    myFeedRubricsLoading = true
    try {
      const response = await fetch(buildRubricsUrl())
      if (!response.ok) return
      const data = await response.json()
      myFeedRubrics = data.rubrics ?? []
    } catch (error) {
      myFeedRubrics = []
    } finally {
      myFeedRubricsLoading = false
    }
  }

  const loadTagLemmas = async () => {
    try {
      const response = await fetch(buildTagsListUrl())
      if (!response.ok) return
      const data = await response.json()
      const entries =
        data.tags?.map((tag: { name: string; lemma?: string }) => [
          normalizeTag(tag.name),
          normalizeTag(tag.lemma ?? tag.name),
        ]) ?? []
      tagLemmaMap = new Map(entries)
      migrateTagRules()
    } catch (error) {
      tagLemmaMap = new Map()
    }
  }

  const migrateTagRules = () => {
    const rules = $userSettings.tagRules ?? {}
    let changed = false
    const nextRules = { ...rules }
    for (const [key, rule] of Object.entries(rules)) {
      const normalized = normalizeTag(key)
      const lemma = tagLemmaMap.get(normalized)
      if (lemma && lemma !== normalized) {
        if (!nextRules[lemma]) {
          nextRules[lemma] = rule
        }
        delete nextRules[key]
        changed = true
      }
    }
    if (changed) {
      $userSettings = { ...$userSettings, tagRules: nextRules }
    }
  }

  const toggleMyFeedRubric = (slug: string) => {
    const current = new Set($userSettings.myFeedRubrics ?? [])
    if (current.has(slug)) {
      current.delete(slug)
    } else {
      current.add(slug)
    }
    $userSettings = { ...$userSettings, myFeedRubrics: Array.from(current) }
  }

  const removeMyFeedAuthor = (username: string) => {
    $userSettings = {
      ...$userSettings,
      myFeedAuthors: ($userSettings.myFeedAuthors ?? []).filter(
        (value) => value !== username
      ),
    }
  }

  const removeHiddenAuthor = (username: string) => {
    $userSettings = {
      ...$userSettings,
      hiddenAuthors: ($userSettings.hiddenAuthors ?? []).filter(
        (value) => value !== username
      ),
    }
  }

  const clearHiddenAuthors = () => {
    $userSettings = { ...$userSettings, hiddenAuthors: [] }
  }

  const syncSiteProfileForm = () => {
    const nextSnapshot = JSON.stringify({
      id: $siteUser?.id ?? null,
      display_name: $siteUser?.display_name ?? '',
      avatar_url: $siteUser?.avatar_url ?? '',
    })
    if (nextSnapshot === lastSiteUserSnapshot) return
    lastSiteUserSnapshot = nextSnapshot
    siteProfileDisplayName = $siteUser?.display_name ?? ''
    siteProfileAvatarUrl = $siteUser?.avatar_url ?? ''
  }

  $: syncSiteProfileForm()
  $: notificationSettingsDirty =
    JSON.stringify(
      notificationEvents.map((event) => ({
        key: event.key,
        site_enabled: event.site_enabled,
        telegram_enabled: event.telegram_enabled,
      }))
    ) !== notificationSettingsSnapshot

  const pickSiteProfileAvatar = () => {
    siteProfileFileInput?.click()
  }

  const onSiteProfileAvatarSelected = async (event: Event) => {
    const input = event.currentTarget as HTMLInputElement | null
    const file = input?.files?.[0]
    if (!file) return
    siteProfileAvatarUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      siteProfileAvatarUrl = uploadedUrl
      toast({ content: 'Аватар загружен. Нажмите «Сохранить»', type: 'success' })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось загрузить аватар',
        type: 'error',
      })
    } finally {
      siteProfileAvatarUploading = false
      if (input) input.value = ''
    }
  }

  const saveSiteProfileSettings = async () => {
    if (!$siteUser) {
      toast({ content: 'Нужна авторизация', type: 'error' })
      return
    }
    siteProfileSaving = true
    try {
      await updateSiteProfile({
        display_name: siteProfileDisplayName.trim(),
        avatar_url: siteProfileAvatarUrl.trim() || '',
      })
      toast({ content: 'Профиль Comuna обновлен', type: 'success' })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось обновить профиль',
        type: 'error',
      })
    } finally {
      siteProfileSaving = false
    }
  }

  const loadChannelVerificationCode = async () => {
    channelVerificationCodeLoading = true
    channelVerificationCodeError = ''
    try {
      channelVerificationCode = await fetchVerificationCode()
    } catch (error) {
      channelVerificationCodeError =
        (error as Error)?.message ?? 'Не удалось получить код'
    } finally {
      channelVerificationCodeLoading = false
    }
  }

  const resetNotificationSettingsState = () => {
    notificationEvents = []
    notificationSettingsLoading = false
    notificationSettingsSaving = false
    notificationSettingsLoaded = false
    notificationSettingsLoadAttempted = false
    notificationTelegramLinked = false
    notificationTelegramUsername = ''
    notificationTelegramFirstName = ''
    notificationSettingsSnapshot = '[]'
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
      notificationSettingsSnapshot = JSON.stringify(
        (data.events ?? []).map((event) => ({
          key: event.key,
          site_enabled: event.site_enabled,
          telegram_enabled: event.telegram_enabled,
        }))
      )
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
    channel: 'site' | 'telegram',
    value: boolean
  ) => {
    const next = [...notificationEvents]
    const item = next[index]
    if (!item) return
    next[index] = {
      ...item,
      site_enabled: channel === 'site' ? value : item.site_enabled,
      telegram_enabled: channel === 'telegram' ? value : item.telegram_enabled,
    }
    notificationEvents = next
  }

  const onNotificationCheckboxChange = (
    event: Event,
    index: number,
    channel: 'site' | 'telegram'
  ) => {
    const target = event.currentTarget as HTMLInputElement | null
    toggleNotificationEventChannel(index, channel, Boolean(target?.checked))
  }

  const saveNotificationSettings = async () => {
    if (!$siteUser) {
      toast({ content: 'Нужна авторизация', type: 'error' })
      return
    }
    notificationSettingsSaving = true
    try {
      const data = await updateSiteNotificationSettings(
        notificationEvents.map((event) => ({
          key: event.key,
          site_enabled: event.site_enabled,
          telegram_enabled: event.telegram_enabled,
        }))
      )
      notificationEvents = data.events ?? []
      notificationTelegramLinked = Boolean(data.telegram?.linked)
      notificationTelegramUsername = data.telegram?.username ?? ''
      notificationTelegramFirstName = data.telegram?.first_name ?? ''
      notificationSettingsSnapshot = JSON.stringify(
        (data.events ?? []).map((event) => ({
          key: event.key,
          site_enabled: event.site_enabled,
          telegram_enabled: event.telegram_enabled,
        }))
      )
      toast({ content: 'Настройки оповещений сохранены', type: 'success' })
    } catch (error) {
      toast({
        content:
          (error as Error)?.message ?? 'Не удалось сохранить настройки оповещений',
        type: 'error',
      })
    } finally {
      notificationSettingsSaving = false
    }
  }

  onMount(() => {
    loadMyFeedRubrics()
    loadTagLemmas()
    if ($siteToken) {
      refreshSiteUser().catch(() => {})
      loadSiteNotificationSettings().catch(() => {})
    }
    if ($colorScheme === 'system') {
      $colorScheme = inDarkColorScheme() ? 'dark' : 'light'
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

<svelte:head>
  <title>{$t('settings.title')}</title>
</svelte:head>

{#if importing}
  <Modal
    bind:open={importing}
    on:action={() => {
      try {
        if (importText == '') {
          throw new Error('Import is empty')
        }
        const parsed = JSON.parse(importText)
        const merged = { ...defaultSettings, ...parsed }

        $userSettings = merged

        toast({ content: $t('toast.settingsImport'), type: 'success' })
        importing = false
      } catch (err) {
        // @ts-ignore
        toast({ content: err, type: 'error' })
      }
    }}
    title={$t('routes.theme.import')}
    action={$t('routes.theme.import')}
  >
    <TextArea bind:value={importText} style="font-family: monospace;" />
  </Modal>
{/if}

<Header pageHeader class="text-3xl font-bold flex justify-between">
  {$t('settings.title')}
  <div class="flex items-center">
    <Button
      size="square-lg"
      on:click={() => {
        importText = ''
        importing = true
      }}
      class="font-normal"
      title={$t('settings.import')}
      roundingSide="left"
    >
      <Icon src={ArrowDownTray} mini size="18" slot="prefix" />
    </Button>
    <Button
      size="square-lg"
      on:click={() => {
        const json = JSON.stringify($userSettings)
        navigator?.clipboard?.writeText?.(json)
        toast({ content: $t('toast.copied') })
      }}
      class="font-normal"
      title={$t('settings.export')}
      rounding="none"
    >
      <Icon src={ArrowUpTray} mini size="18" slot="prefix" />
    </Button>
    <Button
      size="square-lg"
      on:click={() => {
        toast({
          content: $t('toast.resetSettings'),
          action: () => ($userSettings = defaultSettings),
        })
      }}
      class="font-normal"
      title={$t('settings.reset')}
      roundingSide="right"
    >
      <Icon src={ArrowPath} mini size="18" slot="prefix" />
    </Button>
  </div>
</Header>

<div class="flex items-center gap-2 flex-wrap w-full my-5">
  {#if $siteUser}
    <Button href="#notifications" size="sm" class="text-xs" rounding="pill">
      <Icon src={ArrowTopRightOnSquare} size="14" micro />
      Оповещения
    </Button>
  {/if}
  <Button href="#app" size="sm" class="text-xs" rounding="pill">
    <Icon src={ArrowTopRightOnSquare} size="14" micro />
    {$t('settings.app.title')}
  </Button>
</div>

<div
  class="flex flex-col *:py-2 divide-y divide-slate-200 dark:divide-zinc-800"
  style="scroll-behavior: smooth;"
>
  {#if $profile?.jwt}
    <Section open={false} id="account" title={$t('settings.account.title')}>
      <div>
        <Button
          color="primary"
          size="lg"
          href="/profile/settings"
          class="block"
        >
          {$t('profile.profile')}
          <Icon src={ArrowRight} micro size="16" slot="suffix" />
        </Button>
      </div>
    </Section>
  {/if}
  {#if $siteUser}
    <Section id="comuna-profile" title="Профиль Comuna">
      <div class="flex flex-col gap-4">
        <div class="text-sm text-slate-500 dark:text-zinc-400">
          Это профиль, который отображается на сайте в комментариях и на странице пользователя.
        </div>

        <div class="flex flex-col sm:flex-row gap-4 items-start">
          <div class="w-20 h-20 rounded-full overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800 shrink-0">
            {#if siteProfileAvatarUrl}
              <img src={siteProfileAvatarUrl} alt="Аватар профиля" class="w-full h-full object-cover" />
            {:else}
              <div class="w-full h-full grid place-items-center text-lg font-semibold text-slate-500 dark:text-zinc-400">
                {($siteUser.display_name || $siteUser.username || '?').slice(0, 1).toUpperCase()}
              </div>
            {/if}
          </div>

          <div class="flex-1 min-w-0 flex flex-col gap-3">
            <input
              bind:this={siteProfileFileInput}
              type="file"
              accept="image/*"
              class="hidden"
              on:change={onSiteProfileAvatarSelected}
            />

            <TextInput
              bind:value={siteProfileDisplayName}
              label="Имя отображаемое на сайте"
              placeholder={`Например: ${$siteUser.username}`}
              maxLength={120}
            />

            <div class="flex flex-wrap items-center gap-2">
              <Button
                size="sm"
                on:click={pickSiteProfileAvatar}
                disabled={siteProfileSaving || siteProfileAvatarUploading}
              >
                {siteProfileAvatarUrl ? 'Заменить аватарку' : 'Загрузить аватарку'}
              </Button>
              {#if siteProfileAvatarUrl}
                <Button
                  size="sm"
                  color="ghost"
                  on:click={() => (siteProfileAvatarUrl = '')}
                  disabled={siteProfileSaving || siteProfileAvatarUploading}
                >
                  Убрать аватарку
                </Button>
              {/if}
              {#if siteProfileAvatarUploading}
                <span class="text-xs text-slate-500 dark:text-zinc-400">Загрузка...</span>
              {/if}
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <Button
                on:click={saveSiteProfileSettings}
                disabled={siteProfileSaving || siteProfileAvatarUploading}
              >
                {siteProfileSaving ? 'Сохраняем...' : 'Сохранить'}
              </Button>
              <div class="text-xs text-slate-500 dark:text-zinc-400">
                Логин @{ $siteUser.username } не меняется и используется для входа.
              </div>
            </div>
          </div>
        </div>
      </div>
    </Section>
  {/if}
  {#if $siteUser}
    <Section id="linked-channels" title="Привязка Telegram-каналов">
      <div class="flex flex-col gap-4">
        <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
          <h3 class="text-base font-semibold mb-2">Подтверждение админа канала</h3>
          <p class="text-sm text-slate-500 dark:text-zinc-400">
            Получите код и отправьте его в бота. Бот подтвердит, что вы администратор канала.
          </p>
          <div class="mt-4 flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              color="primary"
              on:click={loadChannelVerificationCode}
              loading={channelVerificationCodeLoading}
              disabled={channelVerificationCodeLoading}
            >
              Получить код
            </Button>
            {#if channelVerificationCode}
              <div class="rounded-lg bg-slate-100 dark:bg-zinc-900 px-4 py-2 text-sm font-mono">
                {channelVerificationCode}
              </div>
            {/if}
          </div>
          {#if channelVerificationCodeError}
            <p class="text-sm text-red-600 mt-3">{channelVerificationCodeError}</p>
          {/if}
          <p class="text-sm text-slate-500 dark:text-zinc-400 mt-4">
            Отправьте код боту в Telegram — @comuna_tg_bot.
          </p>
        </div>

        <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
          <h3 class="text-base font-semibold mb-2">Ваши подтвержденные каналы</h3>
          {#if $siteUser.is_author && $siteUser.authors.length}
            <ul class="flex flex-col gap-3 text-sm">
              {#each $siteUser.authors as author}
                <li class="flex flex-col gap-1">
                  <div>
                    @{author.username}
                    {#if author.title}
                      <span class="text-slate-500 dark:text-zinc-400">— {author.title}</span>
                    {/if}
                  </div>
                  <div class="text-xs text-slate-500 dark:text-zinc-400">
                    Режим: {author.auto_publish === false ? 'Согласование' : 'Автопубликация'}
                    <span class="mx-1">•</span>
                    Тематика: {author.rubric ?? 'не выбрана'}
                    <span class="mx-1">•</span>
                    Задержка: {author.publish_delay_days ? `${author.publish_delay_days} дн.` : 'без задержки'}
                    <span class="mx-1">•</span>
                    Комментарии: {author.notify_comments ? 'оповещать' : 'не оповещать'}
                    {#if author.author_rating !== undefined}
                      <span class="mx-1">•</span>
                      Рейтинг: {author.author_rating}
                    {/if}
                  </div>
                  {#if author.invite_url}
                    <a
                      class="text-xs text-blue-600 hover:underline dark:text-blue-400"
                      href={author.invite_url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Ссылка приглашения
                    </a>
                  {/if}
                </li>
              {/each}
            </ul>
          {:else}
            <p class="text-sm text-slate-500 dark:text-zinc-400">Пока нет подтвержденных каналов.</p>
          {/if}
        </div>
      </div>
    </Section>
  {/if}
  {#if $siteUser}
    <Section id="notifications" title="Оповещения">
      <div class="flex flex-col gap-4">
        <div class="text-sm text-slate-500 dark:text-zinc-400">
          Выберите, для каких событий показывать уведомления в колокольчике на сайте и
          отправлять сообщения в Telegram-бот.
        </div>

        <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-3 bg-slate-50/60 dark:bg-zinc-900/40">
          <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
            Telegram: {notificationTelegramLinked ? 'подключен' : 'не подключен'}
          </div>
          <div class="text-xs text-slate-500 dark:text-zinc-400 mt-1">
            {#if notificationTelegramLinked}
              {#if notificationTelegramUsername}
                Аккаунт: @{notificationTelegramUsername}
              {:else if notificationTelegramFirstName}
                Аккаунт: {notificationTelegramFirstName}
              {:else}
                Telegram-аккаунт привязан к профилю.
              {/if}
            {:else}
              Привяжите Telegram через вход/авторизацию Telegram, чтобы бот мог присылать оповещения.
            {/if}
          </div>
        </div>

        {#if notificationSettingsLoading && !notificationEvents.length}
          <div class="text-sm text-slate-500 dark:text-zinc-400">
            Загружаем настройки оповещений...
          </div>
        {:else if notificationEvents.length}
          <div class="overflow-x-auto rounded-xl border border-slate-200 dark:border-zinc-800">
            <table class="w-full min-w-[680px] text-sm">
              <thead class="bg-slate-50 dark:bg-zinc-900/70">
                <tr class="text-left">
                  <th class="px-4 py-3 font-medium text-slate-700 dark:text-zinc-200">Событие</th>
                  <th class="px-4 py-3 font-medium text-center text-slate-700 dark:text-zinc-200 w-28">На сайте</th>
                  <th class="px-4 py-3 font-medium text-center text-slate-700 dark:text-zinc-200 w-28">Telegram</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-200 dark:divide-zinc-800">
                {#each notificationEvents as event, index}
                  <tr class="align-top">
                    <td class="px-4 py-3">
                      <div class="font-medium text-slate-900 dark:text-zinc-100">
                        {event.title}
                      </div>
                      {#if event.description}
                        <div class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
                          {event.description}
                        </div>
                      {/if}
                    </td>
                    <td class="px-4 py-3 text-center">
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                        checked={event.site_enabled}
                        on:change={(e) => onNotificationCheckboxChange(e, index, 'site')}
                      />
                    </td>
                    <td class="px-4 py-3 text-center">
                      <input
                        type="checkbox"
                        class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                        checked={event.telegram_enabled}
                        on:change={(e) => onNotificationCheckboxChange(e, index, 'telegram')}
                      />
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>

          <div class="flex flex-wrap items-center gap-2">
            <Button
              on:click={saveNotificationSettings}
              disabled={notificationSettingsSaving || !notificationSettingsDirty}
            >
              {notificationSettingsSaving ? 'Сохраняем...' : 'Сохранить настройки'}
            </Button>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              Изменения применяются ко всем будущим уведомлениям.
            </div>
          </div>
        {:else}
          <div class="text-sm text-slate-500 dark:text-zinc-400">
            Список событий уведомлений пока пуст.
          </div>
        {/if}
      </div>
    </Section>
  {/if}
  <Section id="app" title={$t('settings.app.title')}>
    <ToggleSetting
      bind:checked={$userSettings.openLinksInNewTab}
      title={$t('settings.app.postsInNewTab.title')}
      description={$t('settings.app.postsInNewTab.description')}
    />
    <Setting>
      <span slot="title">{$t('settings.app.theming.title')}</span>
      <span slot="description">{$t('settings.app.theming.description')}</span>
      <Button href="/theme">
        {$t('settings.app.theming.link')}
        <Icon src={ArrowRight} size="16" mini slot="suffix" />
      </Button>
    </Setting>
    <Setting>
      <span slot="title">Темная/светлая тема</span>
      <span slot="description">Выберите светлую или темную тему.</span>
      <Select bind:value={$colorScheme}>
        <option value="light">Светлая</option>
        <option value="dark">Темная</option>
      </Select>
    </Setting>
    <Setting>
      <span slot="title">Главная страница</span>
      <span slot="description">Выберите, какая лента будет открываться при входе на сайт.</span>
      <Select bind:value={$userSettings.homeFeed}>
        <option value="hot">Горячее</option>
        <option value="fresh">Свежее</option>
        <option value="mine">Моя лента</option>
      </Select>
    </Setting>
    <ToggleSetting
      bind:checked={$userSettings.hideReadPosts}
      title="Скрывать прочитанные"
      description="Если вы уже открывали пост, он больше не будет показываться в «Горячем», «Свежем» и «Моей ленте»."
    />
  </Section>

  <Section id="my-feed" title="Моя лента">
    <Setting itemsClass="!flex-col !items-start">
      <span slot="title">Рубрики моей ленты</span>
      <span slot="description">
        Выберите интересные рубрики — они будут отображаться в разделе «Моя лента».
      </span>
      {#if myFeedRubricsLoading}
        <span class="text-sm text-slate-500">Загружаем рубрики...</span>
      {:else if myFeedRubrics.length}
        <div class="grid gap-3 sm:grid-cols-2 w-full">
          {#each myFeedRubrics as rubric}
            <label class="flex items-center gap-3 text-sm text-slate-700 dark:text-zinc-200">
              <input
                class="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
                type="checkbox"
                checked={$userSettings.myFeedRubrics?.includes(rubric.slug)}
                on:change={() => toggleMyFeedRubric(rubric.slug)}
              />
              <span>{rubric.name}</span>
            </label>
          {/each}
        </div>
        <a href="/?feed=mine" class="text-sm text-blue-600 dark:text-blue-400 hover:underline">
          Открыть мою ленту
        </a>
      {:else}
        <span class="text-sm text-slate-500">Рубрики пока недоступны.</span>
      {/if}
    </Setting>
    <Setting itemsClass="!flex-col !items-start">
      <span slot="title">Авторы моей ленты</span>
      <span slot="description">
        Добавляйте авторов на их страницах кнопкой «Добавить в мою ленту».
      </span>
      {#if myFeedAuthors.length}
        <div class="flex flex-wrap gap-2">
          {#each myFeedAuthors as username}
            <span class="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-xs font-medium text-slate-700 dark:text-zinc-200">
              @{username}
              <button
                type="button"
                class="text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                aria-label={`Удалить автора ${username} из моей ленты`}
                on:click={() => removeMyFeedAuthor(username)}
              >
                ×
              </button>
            </span>
          {/each}
        </div>
      {:else}
        <span class="text-sm text-slate-500 dark:text-zinc-400">Пока нет выбранных авторов.</span>
      {/if}
    </Setting>
    <Setting itemsClass="!flex-col !items-start">
      <span slot="title">Скрытые авторы</span>
      <span slot="description">
        Посты этих авторов не показываются в лентах.
      </span>
      {#if hiddenAuthors.length}
        <div class="flex flex-wrap gap-2">
          {#each hiddenAuthors as username}
            <span class="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-xs font-medium text-slate-700 dark:text-zinc-200">
              @{username}
              <button
                type="button"
                class="text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                aria-label={`Убрать автора ${username} из скрытых`}
                on:click={() => removeHiddenAuthor(username)}
              >
                ×
              </button>
            </span>
          {/each}
        </div>
        <Button size="sm" color="ghost" on:click={clearHiddenAuthors}>
          Очистить список
        </Button>
      {:else}
        <span class="text-sm text-slate-500 dark:text-zinc-400">Скрытых авторов пока нет.</span>
      {/if}
    </Setting>
    <ToggleSetting
      bind:checked={$userSettings.myFeedHideNegative}
      title="Не показывать посты с отрицательным рейтингом"
      description="В моей ленте скрывать публикации с рейтингом ниже нуля."
    />
    <Setting itemsClass="!flex-col !items-start">
      <span slot="title">Черный список тегов</span>
      <span slot="description">
        Посты с этими тегами скрываются во всех лентах.
      </span>
      <div class="flex flex-wrap items-end gap-2">
        <TextInput
          label="Добавить тег вручную"
          bind:value={manualBlacklistTag}
          placeholder="Например: йога"
        />
        <Button size="sm" color="secondary" on:click={addBlacklistedTag}>
          Добавить
        </Button>
        {#if blacklistedTags.length}
          <Button size="sm" color="ghost" on:click={clearBlacklistedTags}>
            Очистить список
          </Button>
        {/if}
      </div>
      {#if blacklistedTags.length}
        <div class="flex flex-wrap gap-2">
          {#each blacklistedTags as tag}
            <span class="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-xs font-medium text-slate-700 dark:text-zinc-200">
              #{tag}
              <button
                type="button"
                class="text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                aria-label={`Удалить тег ${tag} из черного списка`}
                on:click={() => removeBlacklistedTag(tag)}
              >
                ×
              </button>
            </span>
          {/each}
        </div>
      {:else}
        <span class="text-sm text-slate-500 dark:text-zinc-400">Черный список пуст.</span>
      {/if}
    </Setting>
  </Section>
</div>
