<script lang="ts">
  import { goto } from '$app/navigation'
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
    deleteSiteAccount,
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
  let siteProfileEmail = ''
  let siteProfileSaving = false
  let siteProfileAvatarUploading = false
  let deleteProfileModalOpen = false
  let deleteProfileConfirmed = false
  let deleteProfileDeleting = false
  let lastSiteUserSnapshot: string | null = null
  let channelVerificationCode = ''
  let channelVerificationCodeLoading = false
  let channelVerificationCodeError = ''
  let creatingComunByAuthorId: number | null = null
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
      email: $siteUser?.email ?? '',
      email_verified: $siteUser?.email_verified ?? false,
    })
    if (nextSnapshot === lastSiteUserSnapshot) return
    lastSiteUserSnapshot = nextSnapshot
    siteProfileDisplayName = $siteUser?.display_name ?? ''
    siteProfileAvatarUrl = $siteUser?.avatar_url ?? ''
    siteProfileEmail = $siteUser?.email ?? ''
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
      const result = await updateSiteProfile({
        display_name: siteProfileDisplayName.trim(),
        avatar_url: siteProfileAvatarUrl.trim() || '',
        email: siteProfileEmail.trim(),
      })
      toast({
        content: result.emailVerificationSent
          ? 'Профиль обновлен. Проверьте почту и подтвердите email.'
          : 'Профиль Тамбур обновлен',
        type: 'success',
      })
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось обновить профиль',
        type: 'error',
      })
    } finally {
      siteProfileSaving = false
    }
  }

  const deleteProfileWarning =
    'Я подтверждаю удаление всех персональных данных и учетной записи безвозвратно. Понимаю, что все неудаленные посты, сообщества и комментарии остаются на сайте без привязки к пользователю'

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
      toast({ content: 'Профиль удален', type: 'success' })
      await goto('/')
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось удалить профиль',
        type: 'error',
      })
    } finally {
      deleteProfileDeleting = false
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

{#if deleteProfileModalOpen}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-6">
    <div class="w-full max-w-lg rounded-2xl border border-red-200 bg-white p-5 shadow-xl dark:border-red-900/50 dark:bg-zinc-900">
      <div class="flex flex-col gap-4">
        <div>
          <h2 class="text-xl font-semibold text-slate-950 dark:text-zinc-50">
            Удалить профиль
          </h2>
          <p class="mt-2 text-sm leading-6 text-slate-600 dark:text-zinc-300">
            {deleteProfileWarning}
          </p>
        </div>
        <label class="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950/40 dark:text-zinc-200">
          <input
            type="checkbox"
            class="mt-1 h-4 w-4 rounded border-slate-300 text-red-600 focus:ring-red-500"
            bind:checked={deleteProfileConfirmed}
            disabled={deleteProfileDeleting}
          />
          <span>Я понимаю и подтверждаю.</span>
        </label>
        <div class="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            class="inline-flex items-center justify-center rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            on:click={closeDeleteProfileModal}
            disabled={deleteProfileDeleting}
          >
            Отмена
          </button>
          <button
            type="button"
            class="inline-flex items-center justify-center rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
            on:click={deleteSiteProfile}
            disabled={!deleteProfileConfirmed || deleteProfileDeleting}
          >
            {deleteProfileDeleting ? 'Удаляем...' : 'Удалить'}
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
  class="flex flex-col gap-4"
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
    <Section id="comuna-profile" title="Профиль Тамбур">
      <SiteProfileSettingsSection
        siteUser={$siteUser}
        bind:displayName={siteProfileDisplayName}
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
      <NotificationSettingsPanel />
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
  {#if $siteUser}
    <button
      type="button"
      class="mt-2 inline-flex w-fit items-center justify-center rounded-xl bg-red-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-red-700"
      on:click={openDeleteProfileModal}
    >
      Удалить профиль
    </button>
  {/if}
</div>
