<script lang="ts">
  import { goto } from '$app/navigation'
  import { browser } from '$app/environment'
  import { onMount } from 'svelte'
  import { loginTelegram, type TelegramAuthPayload } from '$lib/siteAuth'
  import {
    consumeTelegramAuthContext,
    TELEGRAM_AUTH_COMPLETE_EVENT,
    type TelegramAuthContext,
  } from '$lib/telegramAuthContext'

  let title = 'Завершаем вход через Telegram'
  let message = 'Проверяем ответ Telegram и авторизуем вас на сайте.'
  let isError = false

  const parseSearchParams = (value: string) => {
    const normalized = value.replace(/^[?#]/, '')
    return new URLSearchParams(normalized)
  }

  const collectCallbackParams = () => {
    const params = new URLSearchParams()
    parseSearchParams(window.location.search).forEach((value, key) => params.set(key, value))

    const hash = window.location.hash.replace(/^#/, '')
    if (hash.includes('=')) {
      parseSearchParams(hash).forEach((value, key) => params.set(key, value))
    } else if (hash) {
      params.set('result', hash)
    }

    return params
  }

  const isJwt = (value: string | null | undefined) => Boolean(value && value.split('.').length === 3)

  const tryParseJsonResult = (value: string | null) => {
    if (!value) return null
    try {
      return JSON.parse(value)
    } catch {
      try {
        return JSON.parse(decodeURIComponent(value))
      } catch {
        return null
      }
    }
  }

  const extractIdToken = (params: URLSearchParams) => {
    for (const key of ['id_token', 'result', 'token', 'tgAuthResult', 'auth_result']) {
      const value = params.get(key)
      if (isJwt(value)) return value
      const parsed = tryParseJsonResult(value)
      const candidate = parsed?.id_token || parsed?.result || parsed?.token
      if (isJwt(candidate)) return candidate
    }
    return ''
  }

  const buildLegacyPayload = (params: URLSearchParams): TelegramAuthPayload | null => {
    const id = params.get('id')
    const hash = params.get('hash')
    if (!id || !hash) return null
    return {
      id: Number(id),
      first_name: params.get('first_name') || undefined,
      last_name: params.get('last_name') || undefined,
      username: params.get('username') || undefined,
      photo_url: params.get('photo_url') || undefined,
      auth_date: Number(params.get('auth_date') || 0),
      hash,
    }
  }

  const finishInOpener = (ok: boolean, context: TelegramAuthContext, error = '') => {
    if (!window.opener || window.opener.closed) return false
    window.opener.postMessage(
      {
        type: TELEGRAM_AUTH_COMPLETE_EVENT,
        ok,
        error,
        returnTo: context.returnTo,
      },
      window.location.origin,
    )
    window.setTimeout(() => window.close(), 250)
    return true
  }

  const redirectBack = async (context: TelegramAuthContext) => {
    await goto(context.returnTo || '/', { replaceState: true })
  }

  onMount(async () => {
    if (!browser) return

    const context = consumeTelegramAuthContext()
    const params = collectCallbackParams()
    const telegramError = params.get('error') || params.get('error_description')

    try {
      if (telegramError) {
        throw new Error(telegramError)
      }

      const idToken = extractIdToken(params)
      const payload = idToken ? { id_token: idToken } : buildLegacyPayload(params)
      if (!payload) {
        throw new Error('Telegram не вернул данные авторизации')
      }

      await loginTelegram({
        ...payload,
        auth_intent: context.authIntent,
        privacy_accepted: context.privacyAccepted,
      })

      title = 'Вход выполнен'
      message = 'Возвращаем вас на сайт.'
      if (!finishInOpener(true, context)) {
        await redirectBack(context)
      }
    } catch (error) {
      const text = (error as Error)?.message || 'Не удалось войти через Telegram'
      isError = true
      title = 'Не удалось войти через Telegram'
      message = text
      if (!finishInOpener(false, context, text)) {
        window.setTimeout(() => {
          redirectBack(context)
        }, 2500)
      }
    }
  })
</script>

<svelte:head>
  <title>{title}</title>
</svelte:head>

<main class="telegram-callback">
  <section class:error={isError} class="telegram-callback__card">
    <div class="telegram-callback__logo">
      <img src="/img/logos/telegram_logo.svg" alt="" />
    </div>
    <h1>{title}</h1>
    <p>{message}</p>
  </section>
</main>

<style>
  .telegram-callback {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 24px;
    background:
      radial-gradient(circle at 50% 0%, rgba(14, 165, 233, 0.14), transparent 34rem),
      #f8fafc;
  }

  .telegram-callback__card {
    width: min(100%, 420px);
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.92);
    box-shadow: 0 24px 70px rgba(15, 23, 42, 0.12);
    padding: 32px;
    text-align: center;
    color: #0f172a;
  }

  .telegram-callback__card.error {
    border-color: rgba(220, 38, 38, 0.28);
  }

  .telegram-callback__logo {
    width: 56px;
    height: 56px;
    display: inline-grid;
    place-items: center;
    border-radius: 999px;
    background: #e0f2fe;
    margin-bottom: 18px;
  }

  .telegram-callback__logo img {
    width: 30px;
    height: 30px;
  }

  h1 {
    margin: 0;
    font-size: 1.35rem;
    line-height: 1.25;
  }

  p {
    margin: 12px 0 0;
    color: #475569;
    line-height: 1.5;
  }
</style>
