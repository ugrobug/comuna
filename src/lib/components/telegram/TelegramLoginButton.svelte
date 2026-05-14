<script lang="ts">
  import { onMount, tick } from 'svelte'
  import { browser } from '$app/environment'
  import { env } from '$env/dynamic/public'
  import { toast } from 'mono-svelte'
  import { loginTelegram, refreshSiteUser, type TelegramAuthPayload } from '$lib/siteAuth'
  import {
    forgetTelegramAuthContext,
    rememberTelegramAuthContext,
    TELEGRAM_AUTH_COMPLETE_EVENT,
  } from '$lib/telegramAuthContext'

  export let onSuccess: (() => void) | null = null
  export let label = 'Продолжить с Telegram'
  export let helperText = ''
  export let active = true
  export let disabled = false
  export let privacyAccepted = false
  export let authIntent: 'login' | 'signup' = 'login'

  let container: HTMLDivElement | null = null
  let loading = false
  let scriptLoaded = false
  let scriptFailed = false
  let oidcLoading = false
  let oidcReady = false
  let oidcLoadError = ''
  let lastActive = active
  let lastDisabled = disabled
  let lastPrivacyAccepted = privacyAccepted
  const disabledMessage = 'Сначала примите политику обработки персональных данных.'
  const botName = (env.PUBLIC_TELEGRAM_LOGIN_BOT || '').replace(/^@/, '')
  const oidcClientId = env.PUBLIC_TELEGRAM_OIDC_CLIENT_ID || env.PUBLIC_TELEGRAM_LOGIN_CLIENT_ID || ''
  const oidcRedirectUri = env.PUBLIC_TELEGRAM_REDIRECT_URI || env.PUBLIC_TELEGRAM_OIDC_REDIRECT_URI || ''
  const useOidc = Boolean(oidcClientId)
  const oidcScriptSources = [
    'https://telegram.org/js/telegram-login.js?3',
    'https://oauth.telegram.org/js/telegram-login.js?3',
  ]

  type TelegramOidcResult = {
    id_token?: string
    error?: string
  }

  type TelegramLoginGlobal = {
    Login?: {
      auth?: (
        options: {
          client_id: number
          request_access?: Array<'phone' | 'write'>
          lang?: string
        },
        callback: (result: TelegramOidcResult) => void,
      ) => void
    }
  }

  let oidcScriptPromise: Promise<TelegramLoginGlobal> | null = null

  const currentTelegramLogin = () =>
    ((window as any).Telegram as TelegramLoginGlobal | undefined)?.Login?.auth
      ? ((window as any).Telegram as TelegramLoginGlobal)
      : null

  const loadOidcScriptSource = (src: string) =>
    new Promise<TelegramLoginGlobal>((resolve, reject) => {
      const current = currentTelegramLogin()
      if (current) {
        resolve(current)
        return
      }

      const script = document.createElement('script')
      const timeout = window.setTimeout(() => {
        script.onload = null
        script.onerror = null
        script.remove()
        reject(new Error('Telegram Login не загрузился'))
      }, 10000)

      script.async = true
      script.src = src
      script.dataset.telegramOidcLogin = 'true'
      script.onload = () => {
        window.clearTimeout(timeout)
        const loaded = currentTelegramLogin()
        loaded ? resolve(loaded) : reject(new Error('Telegram Login не загрузился'))
      }
      script.onerror = () => {
        window.clearTimeout(timeout)
        script.remove()
        reject(new Error('Telegram Login не загрузился'))
      }
      document.head.appendChild(script)
    })

  const loadOidcScript = async () => {
    if (!browser) {
      return Promise.reject(new Error('Telegram Login недоступен'))
    }
    const current = currentTelegramLogin()
    if (current) {
      return Promise.resolve(current)
    }

    oidcScriptPromise ??= (async () => {
      let lastError: unknown = null
      document.querySelectorAll<HTMLScriptElement>('script[data-telegram-oidc-login]').forEach((script) => {
        if (!script.dataset.telegramOidcLoaded) {
          script.remove()
        }
      })
      for (const source of oidcScriptSources) {
        try {
          const loaded = await loadOidcScriptSource(source)
          document
            .querySelectorAll<HTMLScriptElement>('script[data-telegram-oidc-login]')
            .forEach((script) => {
              if (script.src === source) {
                script.dataset.telegramOidcLoaded = 'true'
              }
            })
          return loaded
        } catch (error) {
          lastError = error
        }
      }
      throw lastError instanceof Error ? lastError : new Error('Telegram Login не загрузился')
    })()
    return oidcScriptPromise
  }

  const prepareOidcLogin = async () => {
    if (!useOidc || !browser || oidcLoading || oidcReady) return
    oidcLoading = true
    oidcLoadError = ''
    scriptFailed = false
    try {
      await loadOidcScript()
      oidcReady = true
      scriptLoaded = true
    } catch (error) {
      oidcScriptPromise = null
      oidcReady = false
      scriptLoaded = false
      scriptFailed = true
      oidcLoadError = (error as Error)?.message || 'Telegram Login не загрузился'
    } finally {
      oidcLoading = false
    }
  }

  const mountWidget = () => {
    if (useOidc || !browser || !container || !botName || disabled) return
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
    if (useOidc || !browser || !active || disabled) return
    await tick()
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        mountWidget()
      })
    })
  }

  const getTelegramRedirectUri = () => {
    const fallback = `${window.location.origin}/auth/telegram/callback`
    const configured = oidcRedirectUri.trim()
    if (!configured) return fallback
    try {
      return new URL(configured, window.location.origin).toString()
    } catch {
      return fallback
    }
  }

  const withTelegramPopupCompatibility = (openAuth: () => void) => {
    const originalOpen = window.open.bind(window)
    window.open = ((url?: string | URL, target?: string, features?: string) => {
      let nextUrl = url
      const rawUrl = typeof url === 'string' ? url : url?.toString()
      if (rawUrl?.startsWith('https://oauth.telegram.org/auth')) {
        try {
          const authUrl = new URL(rawUrl)
          const redirectUri = getTelegramRedirectUri()
          authUrl.searchParams.set('redirect_uri', redirectUri)
          authUrl.searchParams.set('origin', window.location.origin)
          if (!authUrl.searchParams.get('return_to')) {
            authUrl.searchParams.set('return_to', redirectUri)
          }
          nextUrl = authUrl.toString()
        } catch {
          nextUrl = url
        }
      }
      return originalOpen(nextUrl as string | URL | undefined, target, features)
    }) as typeof window.open

    try {
      openAuth()
    } finally {
      window.open = originalOpen as typeof window.open
    }
  }

  onMount(() => {
    if (!browser) return
    const handleTelegramAuthComplete = async (event: MessageEvent) => {
      if (event.origin !== window.location.origin) return
      if (event.data?.type !== TELEGRAM_AUTH_COMPLETE_EVENT) return
      if (event.data?.ok) {
        await refreshSiteUser()
        toast({ content: 'Вы успешно вошли через Telegram', type: 'success' })
        onSuccess?.()
        return
      }
      toast({
        content: event.data?.error || 'Не удалось войти через Telegram',
        type: 'error',
      })
    }
    window.addEventListener('message', handleTelegramAuthComplete)

    ;(window as any).onTelegramAuth = async (user: TelegramAuthPayload) => {
      loading = true
      try {
        await loginTelegram({
          ...user,
          auth_intent: authIntent,
          privacy_accepted: privacyAccepted,
        })
        forgetTelegramAuthContext()
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

    if (useOidc) {
      prepareOidcLogin()
    } else {
      remountWhenVisible()
    }

    return () => {
      if ((window as any).onTelegramAuth) {
        delete (window as any).onTelegramAuth
      }
      window.removeEventListener('message', handleTelegramAuthComplete)
    }
  })

  $: if (browser && active !== lastActive) {
    lastActive = active
    if (!useOidc && active) {
      remountWhenVisible()
    }
  }

  $: if (browser && (disabled !== lastDisabled || privacyAccepted !== lastPrivacyAccepted)) {
    lastDisabled = disabled
    lastPrivacyAccepted = privacyAccepted
    if (!useOidc && active) {
      remountWhenVisible()
    }
  }

  const handleOidcLogin = async () => {
    if (!browser || loading || !oidcClientId) return
    if (disabled) {
      toast({ content: disabledMessage, type: 'info' })
      return
    }
    const clientId = Number(oidcClientId)
    if (!Number.isFinite(clientId)) {
      toast({ content: 'Telegram Login настроен неверно', type: 'error' })
      return
    }
    const telegram = currentTelegramLogin()
    if (!telegram?.Login?.auth) {
      if (!oidcLoading) {
        prepareOidcLogin()
      }
      toast({
        content: oidcLoadError || 'Telegram Login загружается, попробуйте еще раз через пару секунд',
        type: oidcLoadError ? 'error' : 'info',
      })
      return
    }
    const telegramAuth = telegram.Login.auth
    rememberTelegramAuthContext({
      authIntent,
      privacyAccepted,
      returnTo: `${window.location.pathname}${window.location.search}${window.location.hash}`,
    })
    loading = true
    try {
      const result = await new Promise<TelegramOidcResult>((resolve) => {
        withTelegramPopupCompatibility(() => {
          telegramAuth(
            {
              client_id: clientId,
              request_access: ['write', 'phone'],
              lang: 'ru',
            },
            resolve,
          )
        })
      })
      if (result.error) {
        throw new Error(
          result.error === 'missing id_token'
            ? 'Telegram не вернул id_token. Проверьте настройки Telegram Login для tambur.pub.'
            : result.error,
        )
      }
      if (!result.id_token) {
        throw new Error('Telegram не вернул id_token')
      }
      await loginTelegram({
        auth_intent: authIntent,
        id_token: result.id_token,
        privacy_accepted: privacyAccepted,
      })
      forgetTelegramAuthContext()
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
</script>

{#if !botName && !oidcClientId}
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
{:else if useOidc}
  <div class="flex flex-col gap-2">
    <button
      type="button"
      disabled={loading}
      class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition dark:border-zinc-700 dark:bg-zinc-900"
      class:cursor-not-allowed={disabled}
      class:opacity-60={disabled || loading}
      class:hover:border-slate-300={!disabled && !loading}
      class:hover:bg-slate-50={!disabled && !loading}
      class:dark:hover:border-zinc-600={!disabled && !loading}
      class:dark:hover:bg-zinc-800={!disabled && !loading}
      title={label}
      on:click={handleOidcLogin}
    >
      <span class="flex items-center gap-3">
        <span class="flex h-9 w-9 items-center justify-center rounded-full bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300">
          <img src="/img/logos/telegram_logo.svg" alt="" class="h-5 w-5 object-contain" />
        </span>
        <span class="flex min-w-0 flex-col">
          <span class="text-sm font-semibold text-slate-900 dark:text-zinc-100">{label}</span>
          <span class="text-xs text-slate-500 dark:text-zinc-400">
            {helperText || 'Telegram запросит номер телефона и разрешение на уведомления'}
          </span>
        </span>
      </span>
    </button>

    {#if loading}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Вход через Telegram…</p>
    {:else if oidcLoading && !oidcReady}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Загружаем Telegram Login…</p>
    {:else if oidcLoadError}
      <p class="text-xs text-red-600 dark:text-red-400">{oidcLoadError}</p>
    {/if}
  </div>
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
        on:click={() => {
          if (disabled && !loading) {
            toast({ content: disabledMessage, type: 'info' })
          }
        }}
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
      ></div>
    </div>

    {#if loading}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Вход через Telegram…</p>
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
