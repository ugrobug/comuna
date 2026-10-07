<script lang="ts">
  import { goto, pushState } from '$app/navigation'
  import { page } from '$app/stores'
  import ComunSettingsTabs from '$lib/components/comuns/ComunSettingsTabs.svelte'
  import { SettingsNavigation, type SettingsTabKey } from '$lib/settings/SettingsNavigation'
  import NotificationSettingsPanel from '$lib/components/notifications/NotificationSettingsPanel.svelte'
  import { defaultSettings, userSettings } from '$lib/settings'
  import { interfaceLanguageOptions } from '$lib/interfaceLanguages'
  import Setting from './Setting.svelte'
  import { toast, Modal, TextArea, TextInput } from 'mono-svelte'
  import SiteProfileSettingsSection from '$lib/components/users/SiteProfileSettingsSection.svelte'
  import {
    ArrowDownTray,
    ArrowPath,
    ArrowRight,
    ArrowUpTray,
    Icon,
  } from 'svelte-hero-icons'
  import { Button, Select } from 'mono-svelte'
  import Section from './Section.svelte'
  import ToggleSetting from './ToggleSetting.svelte'
  import { loadTranslations, locale, t } from '$lib/translations'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { profile } from '$lib/auth'
  import { buildTagsListUrl } from '$lib/api/backend'
  import { normalizeTag } from '$lib/tags'
  import {
    deleteSiteAccount,
    refreshSiteUser,
    siteToken,
    siteUser,
    updateSiteProfile,
    uploadSiteImage,
    type SiteUser,
  } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import { colorScheme, inDarkColorScheme } from '$lib/ui/colors'
  import { isPostLanguageCode, normalizeInterfaceLanguage, type PostLanguageCode } from '$lib/postLanguages'
  const settingsNavigation = new SettingsNavigation()
  let visitedTabs = new Set<SettingsTabKey>()
  let mounted = false
  let tagLemmasStarted = false
  $: activeTab = $page.state.settingsTab ?? settingsNavigation.resolve($page.url, Boolean($siteUser || $profile?.jwt))
  $: if (!visitedTabs.has(activeTab)) visitedTabs = new Set([...visitedTabs, activeTab])
  $: settingsTabs = settingsNavigation.keys.map((value) => ({ value, label: $t(`settings.tabs.${value}`) }))
  $: if (mounted && activeTab === 'feed' && !tagLemmasStarted) {
    tagLemmasStarted = true
    void loadTagLemmas()
  }
  const changeSettingsTab = (event: CustomEvent<string>) => {
    const key = event.detail as SettingsTabKey
    if (settingsNavigation.keys.includes(key)) {
      pushState(settingsNavigation.href($page.url, key), { ...$page.state, settingsTab: key })
    }
  }

  let importing = false
  let importText = ''
  let manualBlacklistTag = ''
  let tagLemmaMap = new Map<string, string>()
  let siteProfileDisplayName = ''
  let siteProfileAvatarUrl = ''
  let siteProfileBio = ''
  let siteProfileEmail = ''
  let siteProfileSaving = false
  let siteProfileAvatarUploading = false
  let deleteProfileModalOpen = false
  let deleteProfileConfirmed = false
  let deleteProfileDeleting = false
  let lastSiteUserSnapshot: string | null = null
  let selectedInterfaceLanguage =
    ($userSettings.languageManuallySelected ? $userSettings.language : normalizeInterfaceLanguage($locale)) ?? 'ru'
  let syncedInterfaceLanguage = selectedInterfaceLanguage
  $: hiddenAuthors = $userSettings.hiddenAuthors ?? []
  $: hiddenPostIds = $userSettings.hiddenPostIds ?? []
  $: hiddenComuns = $userSettings.hiddenComuns ?? []
  $: blacklistedTags = Object.entries($userSettings.tagRules ?? {})
    .filter(([, rule]) => rule === 'hide')
    .map(([tag]) => tag)
  $: {
    const storedLanguage =
      ($userSettings.languageManuallySelected
        ? $userSettings.language
        : normalizeInterfaceLanguage($locale)) ?? 'ru'
    if (storedLanguage !== syncedInterfaceLanguage) {
      selectedInterfaceLanguage = storedLanguage
      syncedInterfaceLanguage = storedLanguage
    }
  }

  const changeInterfaceLanguage = async () => {
    const language: PostLanguageCode = isPostLanguageCode(selectedInterfaceLanguage)
      ? selectedInterfaceLanguage
      : 'ru'

    syncedInterfaceLanguage = language
    selectedInterfaceLanguage = language
    await loadTranslations(language)
    userSettings.update((settings) => ({
      ...settings,
      language,
      languageManuallySelected: true,
    }))
  }

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

  const removeHiddenPost = (postId: number) => {
    $userSettings = {
      ...$userSettings,
      hiddenPostIds: ($userSettings.hiddenPostIds ?? []).filter((value) => value !== postId),
    }
  }

  const clearHiddenPosts = () => {
    $userSettings = { ...$userSettings, hiddenPostIds: [] }
  }

  const removeHiddenComun = (slug: string) => {
    $userSettings = {
      ...$userSettings,
      hiddenComuns: ($userSettings.hiddenComuns ?? []).filter((value) => value !== slug),
    }
  }

  const clearHiddenComuns = () => {
    $userSettings = { ...$userSettings, hiddenComuns: [] }
  }

  const syncSiteProfileForm = (user: SiteUser | null) => {
    const nextSnapshot = JSON.stringify({
      id: user?.id ?? null,
      display_name: user?.display_name ?? '',
      bio: user?.bio ?? '',
      avatar_url: user?.avatar_url ?? '',
      email: user?.email ?? '',
      email_verified: user?.email_verified ?? false,
    })
    if (nextSnapshot === lastSiteUserSnapshot) return
    lastSiteUserSnapshot = nextSnapshot
    siteProfileDisplayName = user?.display_name ?? ''
    siteProfileBio = user?.bio ?? ''
    siteProfileAvatarUrl = user?.avatar_url ?? ''
    siteProfileEmail = user?.email ?? ''
  }

  $: syncSiteProfileForm($siteUser)

  const onSiteProfileAvatarSelected = async (file: File) => {
    if (!file) return
    siteProfileAvatarUploading = true
    try {
      const uploadedUrl = await uploadSiteImage(file)
      siteProfileAvatarUrl = uploadedUrl
      toast({ content: $t('settings.siteProfile.avatarUploaded'), type: 'success' })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? $t('settings.siteProfile.avatarUploadFailed'),
        type: 'error',
      })
    } finally {
      siteProfileAvatarUploading = false
    }
  }

  const saveSiteProfileSettings = async () => {
    if (!$siteUser) {
      toast({ content: $t('settings.siteProfile.authRequired'), type: 'error' })
      return
    }
    siteProfileSaving = true
    try {
      const result = await updateSiteProfile({
        display_name: siteProfileDisplayName.trim(),
        bio: siteProfileBio,
        avatar_url: siteProfileAvatarUrl.trim() || '',
        email: siteProfileEmail.trim(),
      })
      toast({
        content: result.emailVerificationSent
          ? $t('settings.siteProfile.updatedVerifyEmail')
          : $t('settings.siteProfile.updated'),
        type: 'success',
      })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? $t('settings.siteProfile.updateFailed'),
        type: 'error',
      })
    } finally {
      siteProfileSaving = false
    }
  }

  const openDeleteProfileModal = () => {
    deleteProfileConfirmed = false
    deleteProfileModalOpen = true
  }

  const closeDeleteProfileModal = () => {
    if (deleteProfileDeleting) return
    deleteProfileModalOpen = false
    deleteProfileConfirmed = false
  }

  const deleteSiteProfile = async () => {
    if (!deleteProfileConfirmed || deleteProfileDeleting) return
    deleteProfileDeleting = true
    try {
      await deleteSiteAccount()
      deleteProfileModalOpen = false
      toast({ content: $t('settings.siteProfile.deleted'), type: 'success' })
      await goto('/')
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? $t('settings.siteProfile.deleteFailed'),
        type: 'error',
      })
    } finally {
      deleteProfileDeleting = false
    }
  }

  onMount(() => {
    mounted = true
    if ($siteToken) {
      refreshSiteUser().catch(() => {})
    }
    if ($colorScheme === 'system') {
      $colorScheme = inDarkColorScheme() ? 'dark' : 'light'
    }
  })

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
    title={$t('settings.import')}
    action={$t('settings.import')}
  >
    <TextArea bind:value={importText} style="font-family: monospace;" />
  </Modal>
{/if}

{#if deleteProfileModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-6">
    <div class="w-full max-w-lg rounded-2xl border border-red-200 bg-white p-5 shadow-xl dark:border-red-900/50 dark:bg-zinc-900">
      <div class="flex flex-col gap-4">
        <div>
          <h2 class="text-xl font-semibold text-slate-950 dark:text-zinc-50">
            {$t('settings.siteProfile.deleteTitle')}
          </h2>
          <p class="mt-2 text-sm leading-6 text-slate-600 dark:text-zinc-300">
            {$t('settings.siteProfile.deleteWarning')}
          </p>
        </div>
        <label class="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950/40 dark:text-zinc-200">
          <input
            type="checkbox"
            class="mt-1 h-4 w-4 rounded border-slate-300 text-red-600 focus:ring-red-500"
            bind:checked={deleteProfileConfirmed}
            disabled={deleteProfileDeleting}
          />
          <span>{$t('settings.siteProfile.deleteConfirm')}</span>
        </label>
        <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            on:click={closeDeleteProfileModal}
            disabled={deleteProfileDeleting}
          >
            {$t('common.cancel')}
          </button>
          <button
            type="button"
            class="inline-flex items-center justify-center rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            on:click={deleteSiteProfile}
            disabled={!deleteProfileConfirmed || deleteProfileDeleting}
          >
            {deleteProfileDeleting ? $t('settings.siteProfile.deleting') : $t('settings.siteProfile.delete')}
          </button>
        </div>
      </div>
    </div>
  </div>
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

<ComunSettingsTabs
  tabs={settingsTabs}
  value={activeTab}
  ariaLabel={$t('settings.title')}
  panelPrefix="site-settings"
  on:change={changeSettingsTab}
/>

<div
  class="flex flex-col gap-4"
  style="scroll-behavior: smooth;"
>
  <div id="site-settings-panel-about" role="tabpanel" aria-labelledby="site-settings-tab-about" tabindex="0" hidden={activeTab !== 'about'}>
    {#if visitedTabs.has('about')}
      <div class="flex flex-col gap-4">
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
          <Section id="comuna-profile" title={$t('settings.siteProfile.title')}>
            <SiteProfileSettingsSection
              siteUser={$siteUser}
              bind:displayName={siteProfileDisplayName}
              bind:bio={siteProfileBio}
              bind:avatarUrl={siteProfileAvatarUrl}
              bind:email={siteProfileEmail}
              saving={siteProfileSaving}
              uploading={siteProfileAvatarUploading}
              on:avatarSelected={(event) => onSiteProfileAvatarSelected(event.detail)}
              on:clearAvatar={() => (siteProfileAvatarUrl = '')}
              on:externalLinked={() => refreshSiteUser().catch(() => {})}
              on:save={saveSiteProfileSettings}
            />
          </Section>
        {/if}
        {#if !$siteUser && !$profile?.jwt}
          <p class="rounded-xl border border-slate-200 bg-white p-5 text-slate-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">{$t('settings.siteProfile.authRequired')}</p>
        {/if}
        {#if $siteUser}
          <button
            type="button"
            class="mt-2 inline-flex w-fit items-center justify-center rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700"
            on:click={openDeleteProfileModal}
          >
            {$t('settings.siteProfile.delete')}
          </button>
        {/if}
      </div>
    {/if}
  </div>
  <div id="site-settings-panel-notifications" role="tabpanel" aria-labelledby="site-settings-tab-notifications" tabindex="0" hidden={activeTab !== 'notifications'}>
    {#if visitedTabs.has('notifications')}
      <div class="flex flex-col gap-4">
        {#if $siteUser}
          <Section id="notifications" title={$t('settings.tabs.notifications')}>
            <NotificationSettingsPanel />
          </Section>
        {:else}
          <p class="rounded-xl border border-slate-200 bg-white p-5 text-slate-700 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">{$t('settings.siteProfile.authRequired')}</p>
        {/if}
      </div>
    {/if}
  </div>
  <div id="site-settings-panel-interface" role="tabpanel" aria-labelledby="site-settings-tab-interface" tabindex="0" hidden={activeTab !== 'interface'}>
    {#if visitedTabs.has('interface')}
      <div class="flex flex-col gap-4">
        <Section id="app" title={$t('settings.tabs.interface')}>
          <ToggleSetting
            bind:checked={$userSettings.openLinksInNewTab}
            title={$t('settings.app.postsInNewTab.title')}
            description={$t('settings.app.postsInNewTab.description')}
          />
          <Setting>
            <span slot="title">{$t('settings.app.theme.title')}</span>
            <span slot="description">{$t('settings.app.theme.description')}</span>
            <Select bind:value={$colorScheme}>
              <option value="light">{$t('settings.app.theme.light')}</option>
              <option value="dark">{$t('settings.app.theme.dark')}</option>
            </Select>
          </Setting>
          <Setting>
            <span slot="title">{$t('settings.app.lang.title')}</span>
            <span slot="description">{$t('settings.app.lang.description')}</span>
            <Select bind:value={selectedInterfaceLanguage} on:change={changeInterfaceLanguage}>
              {#each interfaceLanguageOptions as language (language.code)}
                <option value={language.code}>
                  {language.flag} {$t(`site.language.names.${language.code}`)}
                </option>
              {/each}
            </Select>
          </Setting>
        </Section>
      </div>
    {/if}
  </div>
  <div id="site-settings-panel-feed" role="tabpanel" aria-labelledby="site-settings-tab-feed" tabindex="0" hidden={activeTab !== 'feed'}>
    {#if visitedTabs.has('feed')}
      <div class="flex flex-col gap-4">
        <Section id="my-feed" title={$t('settings.tabs.feed')}>
          <Setting>
            <span slot="title">{$t('settings.app.homeFeed.title')}</span>
            <span slot="description">{$t('settings.app.homeFeed.description')}</span>
            <Select bind:value={$userSettings.homeFeed}>
              <option value="hot">{$t('settings.app.homeFeed.hot')}</option>
              <option value="mine">{$t('settings.app.homeFeed.mine')}</option>
            </Select>
          </Setting>
          <ToggleSetting
            bind:checked={$userSettings.hideReadPosts}
            title={$t('settings.app.hideReadPosts.title')}
            description={$t('settings.app.hideReadPosts.description')}
          />
          <Setting itemsClass="!flex-col !items-start">
            <span slot="title">{$t('settings.myFeed.hiddenAuthors.title')}</span>
            <span slot="description">
              {$t('settings.myFeed.hiddenAuthors.description')}
            </span>
            {#if hiddenAuthors.length}
              <div class="flex flex-wrap gap-2">
                {#each hiddenAuthors as username}
                  <span class="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-xs font-medium text-slate-700 dark:text-zinc-200">
                    @{username}
                    <button
                      type="button"
                      class="text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                      aria-label={`${$t('settings.myFeed.hiddenAuthors.remove')} ${username}`}
                      on:click={() => removeHiddenAuthor(username)}
                    >
                      ×
                    </button>
                  </span>
                {/each}
              </div>
              <Button size="sm" color="ghost" on:click={clearHiddenAuthors}>
                {$t('settings.myFeed.clearList')}
              </Button>
            {:else}
              <span class="text-sm text-slate-500 dark:text-zinc-400">{$t('settings.myFeed.hiddenAuthors.empty')}</span>
            {/if}
          </Setting>
          <Setting itemsClass="!flex-col !items-start">
            <span slot="title">{$t('settings.myFeed.hiddenPosts.title')}</span>
            <span slot="description">{$t('settings.myFeed.hiddenPosts.description')}</span>
            {#if hiddenPostIds.length}
              <div class="flex flex-wrap gap-2">
                {#each hiddenPostIds as postId}
                  <span class="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-xs font-medium text-slate-700 dark:text-zinc-200">
                    #{postId}
                    <button
                      type="button"
                      class="text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                      aria-label={`${$t('settings.myFeed.hiddenPosts.remove')} ${postId}`}
                      on:click={() => removeHiddenPost(postId)}
                    >
                      ×
                    </button>
                  </span>
                {/each}
              </div>
              <Button size="sm" color="ghost" on:click={clearHiddenPosts}>
                {$t('settings.myFeed.clearList')}
              </Button>
            {:else}
              <span class="text-sm text-slate-500 dark:text-zinc-400">{$t('settings.myFeed.hiddenPosts.empty')}</span>
            {/if}
          </Setting>
          <Setting itemsClass="!flex-col !items-start">
            <span slot="title">{$t('settings.myFeed.hiddenComuns.title')}</span>
            <span slot="description">{$t('settings.myFeed.hiddenComuns.description')}</span>
            {#if hiddenComuns.length}
              <div class="flex flex-wrap gap-2">
                {#each hiddenComuns as slug}
                  <span class="inline-flex items-center gap-2 rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-xs font-medium text-slate-700 dark:text-zinc-200">
                    {slug}
                    <button
                      type="button"
                      class="text-slate-500 hover:text-slate-700 dark:text-zinc-400 dark:hover:text-zinc-200"
                      aria-label={`${$t('settings.myFeed.hiddenComuns.remove')} ${slug}`}
                      on:click={() => removeHiddenComun(slug)}
                    >
                      ×
                    </button>
                  </span>
                {/each}
              </div>
              <Button size="sm" color="ghost" on:click={clearHiddenComuns}>
                {$t('settings.myFeed.clearList')}
              </Button>
            {:else}
              <span class="text-sm text-slate-500 dark:text-zinc-400">{$t('settings.myFeed.hiddenComuns.empty')}</span>
            {/if}
          </Setting>
          <ToggleSetting
            bind:checked={$userSettings.myFeedHideNegative}
            title={$t('settings.myFeed.hideNegative.title')}
            description={$t('settings.myFeed.hideNegative.description')}
          />
          <Setting itemsClass="!flex-col !items-start">
            <span slot="title">{$t('settings.myFeed.blacklistedTags.title')}</span>
            <span slot="description">
              {$t('settings.myFeed.blacklistedTags.description')}
            </span>
            <div class="flex flex-wrap items-end gap-2">
              <TextInput
                label={$t('settings.myFeed.blacklistedTags.addLabel')}
                bind:value={manualBlacklistTag}
                placeholder={$t('settings.myFeed.blacklistedTags.placeholder')}
              />
              <Button size="sm" color="secondary" on:click={addBlacklistedTag}>
                {$t('common.add')}
              </Button>
              {#if blacklistedTags.length}
                <Button size="sm" color="ghost" on:click={clearBlacklistedTags}>
                  {$t('settings.myFeed.clearList')}
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
                      aria-label={`${$t('settings.myFeed.blacklistedTags.remove')} ${tag}`}
                      on:click={() => removeBlacklistedTag(tag)}
                    >
                      ×
                    </button>
                  </span>
                {/each}
              </div>
            {:else}
              <span class="text-sm text-slate-500 dark:text-zinc-400">{$t('settings.myFeed.blacklistedTags.empty')}</span>
            {/if}
          </Setting>
        </Section>
      </div>
    {/if}
  </div>

</div>
