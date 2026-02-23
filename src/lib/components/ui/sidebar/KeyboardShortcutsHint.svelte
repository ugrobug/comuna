<script lang="ts">
  import { browser } from '$app/environment'
  import { siteUser } from '$lib/siteAuth'

  export let enabled = true

  const AUTH_DISMISS_PREFIX = 'comuna.keyboard-shortcuts-hint.dismissed.user.'
  const GUEST_DISMISS_KEY = 'comuna.keyboard-shortcuts-hint.dismissed.guest'

  const shortcuts = [
    { key: 'W', hint: 'Плюсануть пост' },
    { key: 'S', hint: 'Минусануть пост' },
    { key: 'A', hint: 'Предыдущий пост' },
    { key: 'D', hint: 'Следующий пост' },
    { key: 'F', hint: 'Развернуть или свернуть пост' },
  ] as const

  let dismissed = false
  let initializedForIdentity: string | null = null

  const currentIdentity = () => ($siteUser?.id ? `user:${$siteUser.id}` : 'guest')

  const readDismissed = () => {
    if (!browser) return false
    try {
      if ($siteUser?.id) {
        return localStorage.getItem(`${AUTH_DISMISS_PREFIX}${$siteUser.id}`) === '1'
      }
      return sessionStorage.getItem(GUEST_DISMISS_KEY) === '1'
    } catch {
      return false
    }
  }

  const writeDismissed = () => {
    if (!browser) return
    try {
      if ($siteUser?.id) {
        localStorage.setItem(`${AUTH_DISMISS_PREFIX}${$siteUser.id}`, '1')
      } else {
        sessionStorage.setItem(GUEST_DISMISS_KEY, '1')
      }
    } catch {
      // ignore storage failures (private mode / blocked storage)
    }
  }

  function dismissHint() {
    writeDismissed()
    dismissed = true
  }

  $: if (browser) {
    const identity = currentIdentity()
    if (identity !== initializedForIdentity) {
      initializedForIdentity = identity
      dismissed = readDismissed()
    }
  }
</script>

{#if enabled && !dismissed}
  <div class="rounded-xl border border-slate-200/80 dark:border-zinc-800 bg-white/90 dark:bg-zinc-900/90 p-4 shadow-sm">
    <div class="flex flex-col gap-2">
      <h3 class="text-sm font-semibold text-slate-900 dark:text-zinc-100">
        Управлять можно с клавиатуры
      </h3>
      <p class="text-xs text-slate-600 dark:text-zinc-400">
        Работает в лентах: голосование, переход между постами и разворот текста.
      </p>

      <div class="mt-1 flex flex-wrap gap-2">
        {#each shortcuts as shortcut}
          <div>
            <kbd
              class="inline-flex items-center justify-center min-w-[2rem] h-8 px-2 rounded-lg border border-slate-300 dark:border-zinc-700 bg-slate-50 dark:bg-zinc-800 text-sm font-semibold text-slate-900 dark:text-zinc-100 shadow-sm"
              title={shortcut.hint}
              aria-label={`${shortcut.key}: ${shortcut.hint}`}
            >
              {shortcut.key}
            </kbd>
          </div>
        {/each}
      </div>

      <button
        type="button"
        class="mt-1 self-start text-xs font-medium text-slate-500 hover:text-slate-900 dark:text-zinc-400 dark:hover:text-zinc-100 underline underline-offset-2"
        on:click={dismissHint}
      >
        Больше не показывать
      </button>
    </div>
  </div>
{/if}
