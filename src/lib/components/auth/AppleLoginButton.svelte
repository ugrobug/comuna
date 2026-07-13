<script lang="ts">
  import { browser } from '$app/environment'
  import { env } from '$env/dynamic/public'
  import { onMount } from 'svelte'
  import { toast } from 'mono-svelte'
  import { loginSocial } from '$lib/siteAuth'
  import { t } from '$lib/translations'

  export let onSuccess: (() => void) | null = null
  export let label = ''
  export let active = true
  export let disabled = false
  export let privacyAccepted = false
  export let authIntent: 'login' | 'signup' = 'login'
  export let registrationSource = ''
  export let registrationPath = ''

  let mounted = false
  let ready = false
  let loading = false
  let loadFailed = false
  let expectedState = ''
  const clientId = String(env.PUBLIC_APPLE_CLIENT_ID || '').trim()
  let scriptPromise: Promise<any> | null = null

  const currentApple = () => (window as any).AppleID?.auth

  const redirectUri = () =>
    String(env.PUBLIC_APPLE_REDIRECT_URI || `${window.location.origin}/auth/apple/callback`).trim()

  const loadAppleScript = () => {
    const current = currentApple()
    if (current) return Promise.resolve(current)
    scriptPromise ??= new Promise((resolve, reject) => {
      const existing = document.querySelector<HTMLScriptElement>('script[data-apple-signin]')
      const script = existing || document.createElement('script')
      const timeout = window.setTimeout(() => reject(new Error('Apple Sign In timeout')), 10000)
      script.async = true
      script.src = 'https://appleid.cdn-apple.com/appleauth/static/jsapi/appleid/1/en_US/appleid.auth.js'
      script.dataset.appleSignin = 'true'
      script.onload = () => {
        window.clearTimeout(timeout)
        const loaded = currentApple()
        loaded ? resolve(loaded) : reject(new Error('Apple Sign In unavailable'))
      }
      script.onerror = () => {
        window.clearTimeout(timeout)
        reject(new Error('Apple Sign In unavailable'))
      }
      if (!existing) document.head.appendChild(script)
    })
    return scriptPromise
  }

  const prepare = async () => {
    if (!browser || !mounted || !active || ready || !clientId) return
    loadFailed = false
    try {
      const apple = await loadAppleScript()
      expectedState = crypto.randomUUID()
      apple.init({
        clientId,
        scope: 'name email',
        redirectURI: redirectUri(),
        state: expectedState,
        usePopup: true,
      })
      ready = true
    } catch (error) {
      console.error('Failed to load Sign in with Apple', error)
      scriptPromise = null
      loadFailed = true
    }
  }

  const handleClick = async () => {
    if (disabled) {
      toast({ content: $t('site.authModal.acceptPrivacyFirst'), type: 'info' })
      return
    }
    if (loading) return
    await prepare()
    const apple = currentApple()
    if (!ready || !apple) {
      toast({ content: $t('site.authModal.appleLoginError'), type: 'error' })
      return
    }
    loading = true
    try {
      const result = await apple.signIn()
      const returnedState = String(result?.authorization?.state || '').trim()
      if (!expectedState || returnedState !== expectedState) {
        throw new Error($t('site.authModal.appleLoginError'))
      }
      const credential = String(result?.authorization?.id_token || '').trim()
      if (!credential) throw new Error($t('site.authModal.appleLoginError'))
      await loginSocial('apple', {
        auth_intent: authIntent,
        credential,
        user: result?.user,
        privacy_accepted: privacyAccepted,
        registration_source: registrationSource,
        registration_path: registrationPath,
      })
      toast({ content: $t('site.authModal.appleLoginSuccess'), type: 'success' })
      onSuccess?.()
    } catch (error) {
      if ((error as any)?.error === 'popup_closed_by_user') return
      toast({
        content: (error as Error)?.message || $t('site.authModal.appleLoginError'),
        type: 'error',
      })
    } finally {
      loading = false
    }
  }

  onMount(() => {
    mounted = true
    void prepare()
    return () => {
      mounted = false
    }
  })

  $: if (mounted && active) void prepare()
</script>

<button
  type="button"
  class="apple-login"
  class:opacity-60={disabled || loading}
  disabled={!disabled && (loading || loadFailed || !clientId)}
  on:click={handleClick}
>
  <span class="apple-login__badge">Apple</span>
  <span>{loading ? $t('site.authModal.appleSigningIn') : label || $t('site.authModal.continueApple')}</span>
</button>

<style>
  .apple-login {
    display: flex;
    min-height: 48px;
    width: 100%;
    align-items: center;
    gap: 12px;
    border: 1px solid #000;
    border-radius: 8px;
    background: #000;
    padding: 10px 16px;
    color: #fff;
    font-size: 14px;
    font-weight: 500;
    text-align: left;
    transition: opacity 150ms ease;
  }

  .apple-login:not(:disabled):hover {
    opacity: 0.9;
  }

  .apple-login__badge {
    display: flex;
    min-width: 38px;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
  }

  :global(.dark) .apple-login {
    border-color: rgb(113 113 122);
    background: #fff;
    color: #000;
  }
</style>
