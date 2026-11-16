<script lang="ts">
  import { onMount } from 'svelte'
  import { goto } from '$app/navigation'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import HobbyPicker from '$lib/components/explore/HobbyPicker.svelte'
  import { ExploreApi } from '$lib/explore/api'
  import type { ExploreData, ExploreNode } from '$lib/explore/types'
  import { loadBackendFeedSettings } from '$lib/settings'

  const api = new ExploreApi()
  let data: ExploreData | undefined
  let error = '', loginOpen = false, pendingTitle = '', busy: number | null = null

  async function load() {
    error = ''
    try { data = await api.graph() }
    catch { error = 'Не удалось загрузить увлечения. Проверьте соединение и попробуйте ещё раз.' }
  }

  function createCommunity(title: string) {
    if (!$siteToken) { pendingTitle = title; loginOpen = true; return }
    void goto('/comuns?' + new URLSearchParams({create: '1', name: title}))
  }

  async function subscribe(node: ExploreNode) {
    if (!$siteToken) { pendingTitle = ''; loginOpen = true; return }
    if (!data || busy !== null) return
    busy = node.id; error = ''
    try {
      const result = await api.subscribe(node.id, true)
      data = {...data, nodes: data.nodes.map(n => n.id === node.id ? {...n, subscribed: result.subscribed, subscribers_count: result.subscribers_count ?? n.subscribers_count} : n)}
      await loadBackendFeedSettings($siteToken)
    } catch { error = 'Не удалось подписаться. Попробуйте ещё раз.' }
    finally { busy = null }
  }

  function authenticated() {
    const title = pendingTitle; pendingTitle = ''
    if (title) createCommunity(title)
    else void load()
  }

  onMount(() => { void load() })
</script>

<svelte:head><title>Подобрать хобби | Тамбур</title></svelte:head>
{#if data}
  <HobbyPicker {data} account={$siteUser?.id ?? null} suspended={loginOpen} {busy} {error}
    onClose={() => goto('/explore')} {subscribe} {createCommunity} />
{:else}
  <main class="p-5"><h1 class="text-xl font-bold">Подобрать хобби</h1>
    {#if error}<p role="alert">{error}</p><button on:click={load}>Повторить</button>
    {:else}<p role="status">Загружаем увлечения…</p>{/if}
  </main>
{/if}
<LoginModal bind:open={loginOpen} registrationSource="explore" registrationPath="/hobbies" on:success={authenticated} />
