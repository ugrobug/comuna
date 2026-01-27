<script lang="ts">
  import { onMount } from 'svelte'
  import { browser } from '$app/environment'
  import { env } from '$env/dynamic/public'
  import { toast } from 'mono-svelte'
  import { loginTelegram, type TelegramAuthPayload } from '$lib/siteAuth'

  export let onSuccess: (() => void) | null = null

  let container: HTMLDivElement | null = null
  let loading = false
  let scriptLoaded = false
  const botName = (env.PUBLIC_TELEGRAM_LOGIN_BOT || '').replace(/^@/, '')

  const mountWidget = () => {
    if (!browser || !container || !botName) return
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
  <p class="text-sm text-slate-500 dark:text-zinc-400">
    Telegram‑вход временно недоступен.
  </p>
{:else}
  <div class="flex flex-col gap-2">
    <div bind:this={container} />
    {#if loading}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Вход через Telegram…</p>
    {:else if !scriptLoaded}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Загрузка виджета Telegram…</p>
    {/if}
  </div>
{/if}
