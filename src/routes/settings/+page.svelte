<script lang="ts">
  import { goto } from '$app/navigation'
  import NotificationHistoryPanel from '$lib/components/notifications/NotificationHistoryPanel.svelte'
  import NotificationSettingsPanel from '$lib/components/notifications/NotificationSettingsPanel.svelte'
  import { subscribeToComunBySlug } from '$lib/settings'
  import { defaultSettings, userSettings } from '$lib/settings'
  import Setting from './Setting.svelte'
  import { toast, Modal, TextArea, TextInput } from 'mono-svelte'
  import SiteProfileSettingsSection from '$lib/components/users/SiteProfileSettingsSection.svelte'
  import TelegramChannelsSection from '$lib/components/users/TelegramChannelsSection.svelte'
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
  import {
    buildComunFromTelegramChannelUrl,
    buildTagsListUrl,
  } from '$lib/api/backend'
  import { normalizeTag } from '$lib/tags'
  import {
    fetchVerificationCode,
    refreshSiteUser,
    siteToken,
    siteUser,
    updateSiteProfile,
    uploadSiteImage,
  } from '$lib/siteAuth'
  import { onMount } from 'svelte'
  import { colorScheme, inDarkColorScheme } from '$lib/ui/colors'
  let importing = false
  let importText = ''
  let manualBlacklistTag = ''
  let tagLemmaMap = new Map<string, string>()
  let siteProfileDisplayName = ''
  let siteProfileAvatarUrl = ''
  let siteProfileSaving = false
  let siteProfileAvatarUploading = false
  let lastSiteUserSnapshot: string | null = null
  let channelVerificationCode = ''
  let channelVerificationCodeLoading = false
  let channelVerificationCodeError = ''
  let creatingComunByAuthorId: number | null = null
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

  const onSiteProfileAvatarSelected = async (file: File) => {
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

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const createComunFromAuthor = async (author: { id?: number; username: string }) => {
    const authorId = Number(author?.id ?? 0)
    if (!authorId || creatingComunByAuthorId) return
    creatingComunByAuthorId = authorId
    try {
      const response = await fetch(buildComunFromTelegramChannelUrl(), {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          author_id: authorId,
          author_username: author.username,
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || !payload?.comun?.slug) {
        throw new Error(payload?.error || 'Не удалось создать сообщество')
      }
      subscribeToComunBySlug(payload.comun.slug)
      await refreshSiteUser()
      toast({
        content: payload?.created === false ? 'Сообщество уже существует' : 'Сообщество создано',
        type: 'success',
      })
      await goto(`/comuns/${payload.comun.slug}/settings`)
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось создать сообщество',
        type: 'error',
      })
    } finally {
      creatingComunByAuthorId = null
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

  onMount(() => {
    loadTagLemmas()
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
      <SiteProfileSettingsSection
        siteUser={$siteUser}
        bind:displayName={siteProfileDisplayName}
        bind:avatarUrl={siteProfileAvatarUrl}
        saving={siteProfileSaving}
        uploading={siteProfileAvatarUploading}
        on:avatarSelected={(event) => onSiteProfileAvatarSelected(event.detail)}
        on:clearAvatar={() => (siteProfileAvatarUrl = '')}
        on:save={saveSiteProfileSettings}
      />
    </Section>
  {/if}
  {#if $siteUser}
    <Section id="linked-channels" title="Привязка Telegram-каналов">
      <TelegramChannelsSection
        siteUser={$siteUser}
        verificationCode={channelVerificationCode}
        verificationCodeLoading={channelVerificationCodeLoading}
        verificationCodeError={channelVerificationCodeError}
        {creatingComunByAuthorId}
        on:loadCode={loadChannelVerificationCode}
        on:createComun={(event) => createComunFromAuthor(event.detail)}
      />
    </Section>
  {/if}
  {#if $siteUser}
    <Section id="notifications" title="Оповещения">
      <div class="flex flex-col gap-6">
        <NotificationSettingsPanel />
        <NotificationHistoryPanel />
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
        <option value="mine">Моя лента</option>
      </Select>
    </Setting>
    <ToggleSetting
      bind:checked={$userSettings.hideReadPosts}
      title="Скрывать прочитанные"
      description="Если вы уже открывали пост, он больше не будет показываться в «Горячем» и «Моей ленте»."
    />
  </Section>

  <Section id="my-feed" title="Моя лента">
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
