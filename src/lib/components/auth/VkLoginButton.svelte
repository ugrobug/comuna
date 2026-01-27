<script lang="ts">
  import { onMount } from 'svelte'
  import { browser } from '$app/environment'
  import { env } from '$env/dynamic/public'
  import { toast } from 'mono-svelte'
  import { loginVK } from '$lib/siteAuth'

  export let onSuccess: (() => void) | null = null

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
  <p class="text-sm text-slate-500 dark:text-zinc-400">
    VK‑вход временно недоступен.
  </p>
{:else}
  <div class="flex flex-col gap-2">
    <div bind:this={container} />
    {#if loading}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Вход через VK…</p>
    {:else if !scriptLoaded}
      <p class="text-xs text-slate-500 dark:text-zinc-400">Загрузка VK виджета…</p>
    {/if}
  </div>
{/if}
