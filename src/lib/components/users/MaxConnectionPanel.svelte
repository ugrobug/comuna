<script lang="ts">
  import { onMount } from 'svelte'
  import { siteToken } from '$lib/siteAuth'
  import { getBackendBaseUrl } from '$lib/api/backend'
  import { Button } from 'mono-svelte'

  export let comunSlug = ''
  let loading = false
  let error = ''
  let code = ''
  let status: any = null
  let linkedChats: any[] = []
  let submissions: any[] = []
  let selected = ''
  const url = (path: string) => `${getBackendBaseUrl()}${path}`
  async function request(path: string, method = 'GET', data?: unknown) {
    const response = await fetch(url(path), {
      method, headers: { Authorization: `Bearer ${$siteToken}`, 'Content-Type': 'application/json' },
      ...(data ? { body: JSON.stringify(data) } : {}),
    })
    const result = await response.json()
    if (!response.ok) throw new Error(result.error || 'Не удалось выполнить действие')
    return result
  }
  async function refresh() {
    loading = true
    error = ''
    try {
      status = await request('/api/max/account/')
      if (status?.account) code = ''
      if (comunSlug) {
        const community = await request(`/api/comuns/${encodeURIComponent(comunSlug)}/max/`)
        linkedChats = community.chats
        submissions = community.submissions || []
      }
    } catch (e) { error = (e as Error).message }
    finally { loading = false }
  }
  async function getCode() {
    loading = true
    error = ''
    try { code = (await request('/api/max/account/', 'POST')).code }
    catch (e) { error = (e as Error).message }
    finally { loading = false }
  }
  async function linkChat(id: string | number, method = 'POST') {
    loading = true
    error = ''
    try {
      await request(`/api/comuns/${encodeURIComponent(comunSlug)}/max/`, method, { id: Number(id) })
      selected = ''
      await refresh()
    } catch (e) { error = (e as Error).message }
    finally { loading = false }
  }
  async function unlinkAccount() {
    loading = true
    error = ''
    try { await request('/api/max/account/', 'DELETE'); code = ''; await refresh() }
    catch (e) { error = (e as Error).message }
    finally { loading = false }
  }
  async function reviewSubmission(id: number, action: 'approve' | 'reject') {
    loading = true
    error = ''
    try {
      await request(`/api/comuns/${encodeURIComponent(comunSlug)}/max/`, 'POST', { id, action })
      await refresh()
    } catch (e) { error = (e as Error).message }
    finally { loading = false }
  }
  onMount(refresh)
</script>

<div class="flex flex-col gap-4 rounded-xl border border-slate-200 p-4 dark:border-zinc-800">
  <h3 class="text-base font-semibold">MAX</h3>
  <p class="text-sm text-slate-500 dark:text-zinc-400">
    Сначала создайте сообщество на сайте. Затем привяжите аккаунт MAX кодом, добавьте бота администратором существующего канала или чата и выберите его в настройках сообщества.
  </p>
  {#if status?.account}
    <p class="text-sm">Аккаунт MAX привязан{status.account.name ? `: ${status.account.name}` : ''}.</p>
    <div><Button size="sm" disabled={loading} on:click={unlinkAccount}>Отвязать аккаунт MAX</Button></div>
    {#if !status.account.active}<p class="text-sm text-amber-600">Откройте бота и нажмите «Начать», чтобы возобновить работу.</p>{/if}
  {:else}
    <div><Button size="sm" color="primary" loading={loading} on:click={getCode}>Получить код привязки MAX</Button></div>
  {/if}
  {#if code}
    <div class="rounded-lg bg-slate-100 p-3 dark:bg-zinc-900">
      <code class="break-all select-all">{code}</code>
      <p class="mt-2 text-xs text-slate-500">Отправьте код боту одним сообщением. Код действует 15 минут.</p>
    </div>
  {/if}
  <div class="flex flex-wrap items-center gap-3 text-sm">
    <a class="text-blue-600 hover:underline dark:text-blue-400" href={status?.bot_url || 'https://max.ru/se14353168_bot'} target="_blank" rel="noopener noreferrer">Открыть бота в MAX</a>
    <Button size="sm" disabled={loading} on:click={refresh}>Обновить</Button>
    {#if !comunSlug}<a class="text-blue-600 hover:underline dark:text-blue-400" href="/comuns">Выбрать сообщество</a>{/if}
  </div>
  {#if comunSlug}
    {#if submissions.length}
      <h4 class="font-medium">Предложения из MAX</h4>
      {#each submissions as item}
        <div class="rounded-lg border border-slate-200 p-3 dark:border-zinc-800">
          <p class="text-xs text-slate-500">{item.request_type === 'kb' ? 'База знаний' : 'Глоссарий'}</p>
          <p class="my-2 whitespace-pre-wrap break-words text-sm">{item.source_text}</p>
          <div class="flex gap-2">
            <Button size="sm" disabled={loading} on:click={() => reviewSubmission(item.id, 'approve')}>Принять</Button>
            <Button size="sm" disabled={loading} on:click={() => reviewSubmission(item.id, 'reject')}>Отклонить</Button>
          </div>
        </div>
      {/each}
    {/if}
    {#each linkedChats as chat}
      <div class="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 p-3 text-sm dark:border-zinc-800">
        <span>{chat.title} · {chat.type === 'channel' ? 'Канал' : 'Групповой чат'}</span>
        <Button size="sm" disabled={loading} on:click={() => linkChat(chat.id, 'DELETE')}>Отвязать</Button>
      </div>
    {/each}
    {#if status?.account}
      <label class="flex flex-col gap-2 text-sm">
        Подтверждённый канал или чат MAX
        <select bind:value={selected} class="rounded-lg border border-slate-300 bg-white p-2 dark:border-zinc-700 dark:bg-zinc-900">
          <option value="">Выберите канал или чат</option>
          {#each (status?.chats ?? []).filter((chat: any) => !chat.comun_slug) as chat}
            <option value={chat.id}>{chat.title}</option>
          {/each}
        </select>
      </label>
      <div><Button size="sm" color="primary" disabled={!selected || loading} on:click={() => linkChat(selected)}>Привязать к сообществу</Button></div>
      <p class="text-xs text-slate-500">Если канала нет в списке, добавьте бота администратором или перешлите ему пост из этого канала. Режим и задержка публикации настраиваются в боте.</p>
    {/if}
  {/if}
  {#if error}<p role="alert" class="text-sm text-red-600">{error}</p>{/if}
</div>
