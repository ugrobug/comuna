<script lang="ts">
  import { onMount } from 'svelte'

  const storageKey = 'tambur_cookie_notice_accepted'

  let visible = false

  onMount(() => {
    try {
      visible = localStorage.getItem(storageKey) !== '1'
    } catch {
      visible = true
    }
  })

  const accept = () => {
    try {
      localStorage.setItem(storageKey, '1')
    } catch {
      // The banner can still close even if browser storage is unavailable.
    }
    visible = false
  }
</script>

{#if visible}
  <div class="fixed inset-x-0 bottom-4 z-[500] flex justify-center px-4 pointer-events-none">
    <div
      class="pointer-events-auto flex w-full max-w-md items-center justify-between gap-4 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 shadow-lg shadow-slate-900/10 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100 dark:shadow-black/30"
    >
      <span class="min-w-0">Мы используем Cookie</span>
      <button
        type="button"
        class="shrink-0 rounded-md bg-slate-950 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-slate-400 dark:bg-zinc-100 dark:text-zinc-950 dark:hover:bg-zinc-200"
        on:click={accept}
      >
        Ок
      </button>
    </div>
  </div>
{/if}
