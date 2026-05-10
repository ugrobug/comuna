<script lang="ts">
  import { onMount, tick } from 'svelte'
  import { browser } from '$app/environment'
  import { env } from '$env/dynamic/public'
  import { toast } from 'mono-svelte'
  import { loginTelegram, type TelegramAuthPayload } from '$lib/siteAuth'

  export let onSuccess: (() => void) | null = null
  export let label = 'Продолжить с Telegram'
  export let helperText = ''
  export let active = true
  export let disabled = false
  export let privacyAccepted = false

  let container: HTMLDivElement | null = null
  let loading = false
  let scriptLoaded = false
  let scriptFailed = false
  let lastActive = active
  let lastDisabled = disabled
  let lastPrivacyAccepted = privacyAccepted
  const botName = (env.PUBLIC_TELEGRAM_LOGIN_BOT || '').replace(/^@/, '')

  const mountWidget = () => {
    if (!browser || !container || !botName || disabled) return
    scriptLoaded = false
    scriptFailed = false
    container.innerHTML = ''

    const script = document.createElement('script')
    script.async = true
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botName)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-radius', '8')
    script.setAttribute('data-onauth', 'onTelegramAuth(user)')
    script.setAttribute('data-request-access', 'write')
    script.onload = () => {
      scriptLoaded = true
    }
    script.onerror = () => {
      scriptLoaded = false
      scriptFailed = true
    }
    container.appendChild(script)
  }

  const remountWhenVisible = async () => {
    if (!browser || !active || disabled) return
    await tick()
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        mountWidget()
      })
    })
  }

  onMount(() => {
    if (!browser) return
    ;(window as any).onTelegramAuth = async (user: TelegramAuthPayload) => {
      loading = true
      try {
        await loginTelegram({ ...user, privacy_accepted: privacyAccepted })
        toast({ content: 'Вы успешно вошли через Telegram', type: 'success' })
        onSuccess?.()
      } catch (error) {
        toast({
          content: (error as Error)?.message ?? 'Не удалось войти через Telegram',
          type: 'error',
        })
      } finally {
        loading = false
      }
    }

    remountWhenVisible()

    return () => {
      if ((window as any).onTelegramAuth) {
        delete (window as any).onTelegramAuth
      }
    }
  })

  $: if (browser && active !== lastActive) {
    lastActive = active
    if (active) {
      remountWhenVisible()
    }
  }

  $: if (browser && (disabled !== lastDisabled || privacyAccepted !== lastPrivacyAccepted)) {
    lastDisabled = disabled
    lastPrivacyAccepted = privacyAccepted
    if (active) {
      remountWhenVisible()
    }
  }
</script>

{#if !botName}
  <button
    type="button"
    disabled
    class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-500"
    title="Telegram-вход временно недоступен"
  >
    <span class="flex items-center gap-3">
      <span class="flex h-9 w-9 items-center justify-center rounded-full bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
        <img src="/img/logos/telegram_logo.svg" alt="" class="h-5 w-5 object-contain" />
      </span>
      <span class="font-medium">Telegram недоступен</span>
    </span>
  </button>
{:else}
  <div class="flex flex-col gap-2">
    <div class="relative">
      <div
        class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition dark:border-zinc-700 dark:bg-zinc-900"
        class:opacity-60={disabled}
        class:hover:border-slate-300={!disabled}
        class:hover:bg-slate-50={!disabled}
        class:dark:hover:border-zinc-600={!disabled}
        class:dark:hover:bg-zinc-800={!disabled}
        title={label}
        aria-hidden="true"
      >
        <span class="flex items-center gap-3">
          <span class="flex h-9 w-9 items-center justify-center rounded-full bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
            <img src="/img/logos/telegram_logo.svg" alt="" class="h-5 w-5 object-contain" />
          </span>
          <span class="flex min-w-0 flex-col">
            <span class="text-sm font-semibold text-slate-900 dark:text-zinc-100">{label}</span>
            {#if helperText}
              <span class="text-xs text-slate-500 dark:text-zinc-400">{helperText}</span>
            {/if}
          </span>
        </span>
      </div>

      <div
        bind:this={container}
        class="telegram-widget-host"
        class:is-loading={loading}
        class:is-disabled={disabled}
        aria-label={label}
      />
    </div>

    {#if loading}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Вход через Telegram…</p>
    {:else if disabled}
      <p class="text-xs text-slate-500 dark:text-zinc-400">
        Сначала примите политику обработки персональных данных.
      </p>
    {:else if scriptFailed}
      <p class="text-xs text-slate-500 dark:text-zinc-400">
        Не удалось загрузить Telegram-вход. Проверьте блокировщики в браузере.
      </p>
    {:else if !scriptLoaded}
      <p class="text-xs text-slate-500 dark:text-zinc-400">
        Загрузка Telegram-входа… Если кнопка не появилась, обновите страницу.
      </p>
    {/if}
  </div>
{/if}

<style>
  .telegram-widget-host {
    position: absolute;
    inset: 0;
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    pointer-events: none;
  }

  .telegram-widget-host.is-loading {
    pointer-events: none;
  }

  .telegram-widget-host.is-disabled {
    pointer-events: none;
  }

  .telegram-widget-host :global(iframe) {
    opacity: 0.02;
    width: 100% !important;
    height: 100% !important;
    border-radius: 0.75rem;
    cursor: pointer;
    pointer-events: auto;
  }

  .telegram-widget-host :global(button),
  .telegram-widget-host :global(a) {
    opacity: 0;
    width: 100%;
    height: 100%;
    display: block;
    cursor: pointer;
    pointer-events: auto;
  }
</style>
