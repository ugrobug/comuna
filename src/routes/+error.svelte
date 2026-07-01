<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { browser } from '$app/environment'
  import { errorMessage } from '$lib/lemmy/error'
  import { userSettings } from '$lib/settings.js'
  import { aliases, loadTranslations, locale, t } from '$lib/translations'
  import { Button } from 'mono-svelte'
  import { Icon, XMark } from 'svelte-hero-icons'
  import { onMount } from 'svelte'

  const errorTranslationKeys: Record<string, string> = {
    'Автор не найден': 'site.errors.authorNotFound',
    'Пост не найден': 'site.errors.postNotFound',
    'Пользователь не найден': 'site.errors.userNotFound',
    'Сообщество не найдено': 'site.errors.communityNotFound',
    'Тег не найден': 'site.errors.tagNotFound',
    'Не удалось загрузить посты': 'site.errors.postsLoadFailed',
  }

  onMount(() => {
    if (!browser) return
    const selectedLocale = aliases.get($userSettings.language) ?? $userSettings.language
    if (selectedLocale && selectedLocale !== $locale) {
      loadTranslations(selectedLocale)
    }
  })

  function getError(message: string): { string: string; code: boolean } {
    const translationKey = message.startsWith('site.errors.')
      ? message
      : errorTranslationKeys[message]
    if (translationKey) {
      return { string: $t(translationKey), code: false }
    }

    try {
      return { string: errorMessage(JSON.parse(message)), code: false }
    } catch (e) {
      return { string: message, code: true }
    }
  }
</script>

<div
  class="flex flex-col gap-4 my-auto h-full justify-center max-w-md w-full mx-auto"
>
  <h1
    class="text-primary-900 dark:text-primary-100 text-6xl font-black flex items-center flex-row gap-2
    font-display border-b pb-4 border-slate-200 dark:border-zinc-800"
  >
    {$page.status}
  </h1>
  {#if $page?.error?.message}
    {@const error = getError($page?.error?.message)}
    {#if error.code}
      <code class="rounded-md dark:!bg-zinc-950 px-2 py-1 min-w-48">
        {error.string}
      </code>
    {:else}
      <p class="text-lg">
        {error.string}
      </p>
    {/if}
  {/if}
  <div class="flex items-center gap-2">
    <Button
      rounding="xl"
      on:click={() => goto($page.url, { invalidateAll: true })}
    >
      {$t('message.retry')}
    </Button>
    <Button rounding="xl" href="/">
      {$t('nav.home')}
    </Button>
  </div>
</div>
