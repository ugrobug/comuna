<script lang="ts">
  import { browser } from '$app/environment'
  import { env } from '$env/dynamic/public'
  import { onMount, tick } from 'svelte'
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

  let container: HTMLDivElement | null = null
  let mounted = false
  let loading = false
  let initialized = false
  let loadFailed = false
  const clientId = String(env.PUBLIC_GOOGLE_CLIENT_ID || '').trim()

  type GoogleCredentialResponse = { credential?: string }
  type GoogleAccounts = {
    id: {
      initialize: (options: Record<string, unknown>) => void
      renderButton: (element: HTMLElement, options: Record<string, unknown>) => void
    }
  }

  let scriptPromise: Promise<GoogleAccounts> | null = null

  const currentGoogle = () => (window as any).google?.accounts as GoogleAccounts | undefined

  const loadGoogleScript = () => {
    const current = currentGoogle()
    if (current) return Promise.resolve(current)
    scriptPromise ??= new Promise<GoogleAccounts>((resolve, reject) => {
      const existing = document.querySelector<HTMLScriptElement>('script[data-google-identity]')
      const script = existing || document.createElement('script')
      const timeout = window.setTimeout(() => reject(new Error('Google Identity timeout')), 10000)
      script.async = true
      script.src = 'https://accounts.google.com/gsi/client'
      script.dataset.googleIdentity = 'true'
      script.onload = () => {
        window.clearTimeout(timeout)
        const loaded = currentGoogle()
        loaded ? resolve(loaded) : reject(new Error('Google Identity unavailable'))
      }
      script.onerror = () => {
        window.clearTimeout(timeout)
        reject(new Error('Google Identity unavailable'))
      }
      if (!existing) document.head.appendChild(script)
    })
    return scriptPromise
  }

  const handleCredential = async (response: GoogleCredentialResponse) => {
    const credential = String(response?.credential || '').trim()
    if (!credential || loading) return
    loading = true
    try {
      await loginSocial('google', {
        auth_intent: authIntent,
        credential,
        privacy_accepted: privacyAccepted,
        registration_source: registrationSource,
        registration_path: registrationPath,
      })
      toast({ content: $t('site.authModal.googleLoginSuccess'), type: 'success' })
      onSuccess?.()
    } catch (error) {
      toast({
        content: (error as Error)?.message || $t('site.authModal.googleLoginError'),
        type: 'error',
      })
    } finally {
      loading = false
    }
  }

  const prepare = async () => {
    if (!browser || !mounted || !active || disabled || initialized || !clientId || !container) return
    loadFailed = false
    try {
      const google = await loadGoogleScript()
      await tick()
      if (!container) return
      google.id.initialize({ client_id: clientId, callback: handleCredential })
      container.innerHTML = ''
      google.id.renderButton(container, {
        type: 'standard',
        theme: 'outline',
        size: 'large',
        shape: 'rectangular',
        text: authIntent === 'signup' ? 'signup_with' : 'signin_with',
        width: Math.min(400, Math.max(260, Math.floor(container.getBoundingClientRect().width))),
      })
      initialized = true
    } catch (error) {
      console.error('Failed to load Google Identity Services', error)
      scriptPromise = null
      loadFailed = true
    }
  }

  const handleDisabledClick = () => {
    if (disabled) {
      toast({ content: $t('site.authModal.acceptPrivacyFirst'), type: 'info' })
    }
  }

  onMount(() => {
    mounted = true
    void prepare()
    return () => {
      mounted = false
    }
  })

  $: if (mounted && active && !disabled) void prepare()
</script>

<div class="google-login" class:opacity-60={disabled || loading}>
  <div bind:this={container} class="google-login__widget"></div>
  {#if !initialized}
    <button
      type="button"
      class="google-login__fallback"
      disabled={!disabled && (loading || loadFailed || !clientId)}
      on:click={handleDisabledClick}
    >
      <span class="google-login__badge">G</span>
      <span>{label || $t('site.authModal.continueGoogle')}</span>
    </button>
  {/if}
  {#if disabled && initialized}
    <button
      type="button"
      class="google-login__overlay"
      aria-label={$t('site.authModal.acceptPrivacyFirst')}
      on:click={handleDisabledClick}
    ></button>
  {/if}
</div>

<style>
  .google-login {
    position: relative;
    min-height: 44px;
    width: 100%;
  }

  .google-login__widget {
    display: flex;
    min-height: 44px;
    width: 100%;
    align-items: center;
    justify-content: center;
  }

  .google-login__fallback {
    display: flex;
    min-height: 48px;
    width: 100%;
    align-items: center;
    gap: 12px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: white;
    padding: 10px 16px;
    color: rgb(15 23 42);
    font-size: 14px;
    font-weight: 500;
    text-align: left;
  }

  .google-login__fallback:disabled {
    color: rgb(100 116 139);
  }

  .google-login__badge {
    display: flex;
    height: 28px;
    width: 28px;
    flex: 0 0 28px;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: #fff;
    color: #4285f4;
    font-size: 18px;
    font-weight: 700;
  }

  .google-login__overlay {
    position: absolute;
    inset: 0;
    cursor: pointer;
    border: 0;
    background: transparent;
  }

  :global(.dark) .google-login__fallback {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27);
    color: rgb(244 244 245);
  }
</style>
