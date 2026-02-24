<script lang="ts">
  import { onMount } from 'svelte'
  import { browser } from '$app/environment'
  import { env } from '$env/dynamic/public'
  import { toast } from 'mono-svelte'
  import { loginTelegram, type TelegramAuthPayload } from '$lib/siteAuth'

  export let onSuccess: (() => void) | null = null
  export let label = 'Продолжить с Telegram'
  export let helperText = ''

  let container: HTMLDivElement | null = null
  let loading = false
  let scriptLoaded = false
  const botName = (env.PUBLIC_TELEGRAM_LOGIN_BOT || '').replace(/^@/, '')
  let authUrl = ''

  const mountWidget = () => {
    if (!browser || !container || !botName) return
    if (!authUrl) {
      const origin = env.PUBLIC_SITE_URL || window.location.origin
      const next = `${window.location.pathname}${window.location.search}`
      authUrl = `${origin.replace(/\/$/, '')}/api/auth/telegram/?next=${encodeURIComponent(next)}`
    }
    container.innerHTML = ''

    const script = document.createElement('script')
    script.async = true
    script.src = 'https://telegram.org/js/telegram-widget.js?22'
    script.setAttribute('data-telegram-login', botName)
    script.setAttribute('data-size', 'large')
    script.setAttribute('data-radius', '8')
    script.setAttribute('data-auth-url', authUrl)
    script.setAttribute('data-request-access', 'write')
    script.onload = () => {
      scriptLoaded = true
    }
    container.appendChild(script)
  }

  onMount(() => {
    if (!browser) return
    ;(window as any).onTelegramAuth = async (user: TelegramAuthPayload) => {
      loading = true
      try {
        await loginTelegram(user)
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

    mountWidget()

    return () => {
      if ((window as any).onTelegramAuth) {
        delete (window as any).onTelegramAuth
      }
    }
  })

</script>

{#if !botName}
  <button
    type="button"
    disabled
    class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-500"
    title="Telegram‑вход временно недоступен"
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
        class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
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
        class:is-loading={!scriptLoaded || loading}
        aria-label={label}
      />
    </div>

    {#if loading}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Вход через Telegram…</p>
    {:else if !scriptLoaded}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Загрузка Telegram‑входа…</p>
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
  }

  .telegram-widget-host.is-loading {
    pointer-events: none;
  }

  .telegram-widget-host :global(iframe) {
    opacity: 0;
    width: 100% !important;
    height: 100% !important;
    border-radius: 0.75rem;
    cursor: pointer;
  }

  .telegram-widget-host :global(button),
  .telegram-widget-host :global(a) {
    opacity: 0;
    width: 100%;
    height: 100%;
    display: block;
    cursor: pointer;
  }
</style>
