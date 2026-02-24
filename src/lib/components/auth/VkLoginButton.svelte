<script lang="ts">
  import { onMount } from 'svelte'
  import { browser } from '$app/environment'
  import { env } from '$env/dynamic/public'
  import { toast } from 'mono-svelte'
  import { loginVK } from '$lib/siteAuth'

  export let onSuccess: (() => void) | null = null
  export let label = 'Продолжить с VK'
  export let helperText = ''

  let container: HTMLDivElement | null = null
  let loading = false
  let scriptLoaded = false
  let showFallbackWidget = false
  const appId = env.PUBLIC_VK_APP_ID

  const renderWidget = () => {
    if (!browser || !container || !appId) return
    const VKID = (window as any).VKIDSDK
    if (!VKID) return

    VKID.Config.init({
      app: Number(appId),
      redirectUrl: env.PUBLIC_VK_REDIRECT_URL || window.location.origin,
      responseMode: VKID.ConfigResponseMode.Callback,
      source: VKID.ConfigSource.LOWCODE,
      scope: '',
    })

    const oneTap = new VKID.OneTap()
    oneTap
      .render({
        container,
        showAlternativeLogin: true,
      })
      .on(VKID.WidgetEvents.ERROR, (error: any) => {
        console.error('VKID error', error)
        toast({ content: 'Ошибка VK', type: 'error' })
      })
      .on(VKID.OneTapInternalEvents.LOGIN_SUCCESS, (payload: any) => {
        const code = payload?.code
        const deviceId = payload?.device_id
        if (!code || !deviceId) {
          toast({ content: 'Не удалось получить код VK', type: 'error' })
          return
        }
        loading = true
        VKID.Auth.exchangeCode(code, deviceId)
          .then(async (data: any) => {
            await loginVK({
              access_token: data.access_token,
              expires_in: data.expires_in,
              user_id: data.user_id,
              id_token: data.id_token,
            })
            toast({ content: 'Вы успешно вошли через VK', type: 'success' })
            onSuccess?.()
          })
          .catch((error: any) => {
            console.error('VKID exchange error', error)
            toast({ content: 'Не удалось войти через VK', type: 'error' })
          })
          .finally(() => {
            loading = false
          })
      })
  }

  onMount(() => {
    if (!browser || !container || !appId) return

    if ((window as any).VKIDSDK) {
      scriptLoaded = true
      renderWidget()
      return
    }

    const script = document.createElement('script')
    script.async = true
    script.src = 'https://unpkg.com/@vkid/sdk@<3.0.0/dist-sdk/umd/index.js'
    script.onload = () => {
      scriptLoaded = true
      renderWidget()
    }
    script.onerror = () => {
      toast({ content: 'Не удалось загрузить VK виджет', type: 'error' })
    }
    document.head.appendChild(script)
  })

  function findWidgetTarget(): HTMLElement | null {
    if (!container) return null
    return (
      (container.querySelector('iframe') as HTMLElement | null) ??
      (container.querySelector('button') as HTMLElement | null) ??
      (container.querySelector('a') as HTMLElement | null) ??
      (container.querySelector('[role=\"button\"]') as HTMLElement | null) ??
      (container.firstElementChild as HTMLElement | null)
    )
  }

  export function triggerLogin() {
    if (!appId) return
    if (loading) return
    const target = findWidgetTarget()
    if (!target) {
      if (!scriptLoaded) {
        toast({ content: 'Загрузка VK‑входа…', type: 'info' })
      } else {
        showFallbackWidget = true
        toast({ content: 'Нажмите кнопку VK ниже', type: 'info' })
      }
      return
    }
    target.click()
  }
</script>

{#if !appId}
  <button
    type="button"
    disabled
    class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-500"
    title="VK‑вход временно недоступен"
  >
    <span class="flex items-center gap-3">
      <span class="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-blue-700 font-semibold dark:bg-blue-900/40 dark:text-blue-300">
        VK
      </span>
      <span class="font-medium">VK недоступен</span>
    </span>
  </button>
{:else}
  <div class="flex flex-col gap-2">
    <button
      type="button"
      class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
      on:click={triggerLogin}
      disabled={loading}
      title={label}
    >
      <span class="flex items-center gap-3">
        <span class="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-blue-700 font-semibold dark:bg-blue-900/40 dark:text-blue-300">
          VK
        </span>
        <span class="flex min-w-0 flex-col">
          <span class="text-sm font-semibold text-slate-900 dark:text-zinc-100">{label}</span>
          {#if helperText}
            <span class="text-xs text-slate-500 dark:text-zinc-400">{helperText}</span>
          {/if}
        </span>
      </span>
    </button>

    <div
      bind:this={container}
      class:hidden-native-widget={!showFallbackWidget}
      class="vk-widget-host"
      aria-hidden={!showFallbackWidget}
    />

    {#if loading}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Вход через VK…</p>
    {:else if !scriptLoaded}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Загрузка VK виджета…</p>
    {:else if showFallbackWidget}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Если окно не открылось, нажмите кнопку VK ниже.</p>
    {/if}
  </div>
{/if}

<style>
  .hidden-native-widget {
    position: absolute;
    left: -99999px;
    width: 1px;
    height: 1px;
    overflow: hidden;
  }

  .vk-widget-host:not(.hidden-native-widget) {
    width: 100%;
    min-height: 56px;
  }
</style>
