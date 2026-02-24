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
    <div class="relative">
      <div
        class="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-left transition hover:border-slate-300 hover:bg-slate-50 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
        title={label}
        aria-hidden="true"
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
      </div>

      <div
        bind:this={container}
        class="vk-widget-host"
        class:is-loading={!scriptLoaded || loading}
        aria-label={label}
      />
    </div>

    {#if loading}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Вход через VK…</p>
    {:else if !scriptLoaded}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Загрузка VK виджета…</p>
    {/if}
  </div>
{/if}

<style>
  .vk-widget-host {
    position: absolute;
    inset: 0;
    z-index: 2;
    overflow: hidden;
  }

  .vk-widget-host.is-loading {
    pointer-events: none;
  }

  .vk-widget-host :global(iframe) {
    opacity: 0;
    width: 100% !important;
    height: 100% !important;
    cursor: pointer;
  }

  .vk-widget-host :global(button),
  .vk-widget-host :global(a),
  .vk-widget-host :global([role='button']) {
    opacity: 0;
    width: 100%;
    height: 100%;
    display: block;
    cursor: pointer;
  }
</style>
