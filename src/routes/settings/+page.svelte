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
  import { buildRubricsUrl } from '$lib/api/backend'
  import { onMount } from 'svelte'
  import { colorScheme, inDarkColorScheme } from '$lib/ui/colors'
  let importing = false
  let importText = ''
  let myFeedRubrics: Array<{ name: string; slug: string }> = []
  let myFeedRubricsLoading = false
  let manualBlacklistTag = ''
  $: blacklistedTags = Object.entries($userSettings.tagRules ?? {})
    .filter(([, rule]) => rule === 'hide')
    .map(([tag]) => tag)

  const removeBlacklistedTag = (tag: string) => {
    const nextRules = { ...($userSettings.tagRules ?? {}) }
    delete nextRules[tag]
    $userSettings = { ...$userSettings, tagRules: nextRules }
  }

  const addBlacklistedTag = () => {
    const normalized = manualBlacklistTag.trim().toLowerCase()
    if (!normalized) return
    $userSettings = {
      ...$userSettings,
      tagRules: { ...($userSettings.tagRules ?? {}), [normalized]: 'hide' },
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

  const toggleMyFeedRubric = (slug: string) => {
    const current = new Set($userSettings.myFeedRubrics ?? [])
    if (current.has(slug)) {
      current.delete(slug)
    } else {
      current.add(slug)
    }
    $userSettings = { ...$userSettings, myFeedRubrics: Array.from(current) }
  }

  onMount(() => {
    loadMyFeedRubrics()
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
