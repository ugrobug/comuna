<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import { Eye, Icon } from 'svelte-hero-icons'
  import { t } from '$lib/translations'
  import type { HiddenContentReasonKind } from '$lib/postVisibility'

  export let reason: HiddenContentReasonKind | 'settings' = 'settings'
  export let label = ''

  const dispatch = createEventDispatcher<{
    showonce: void
    showalways: void
  }>()

  $: messageKey = `site.hiddenContent.${reason}`
  $: message = $t(messageKey, { label })
</script>

<section
  class="flex flex-col gap-4 rounded-lg border border-amber-200 bg-amber-50 p-4 text-slate-900 dark:border-amber-900/70 dark:bg-amber-950/30 dark:text-zinc-100 sm:flex-row sm:items-center sm:justify-between"
  role="status"
>
  <div class="flex min-w-0 items-start gap-3">
    <span class="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200">
      <Icon src={Eye} size="20" />
    </span>
    <div class="min-w-0">
      <div class="font-semibold">{message}</div>
      <div class="mt-1 text-sm text-slate-600 dark:text-zinc-300">
        {$t('site.hiddenContent.description')}
      </div>
    </div>
  </div>

  <div class="flex shrink-0 flex-wrap gap-2 sm:justify-end">
    <button
      type="button"
      class="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
      on:click={() => dispatch('showonce')}
    >
      {$t('site.hiddenContent.showOnce')}
    </button>
    <button
      type="button"
      class="rounded-md bg-sky-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-sky-700"
      on:click={() => dispatch('showalways')}
    >
      {$t('site.hiddenContent.showAlways')}
    </button>
  </div>
</section>
