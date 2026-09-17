<script lang="ts">
  import { onMount } from 'svelte'
  import { goto } from '$app/navigation'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { siteToken } from '$lib/siteAuth'
  import type { CompanionTemplate } from '$lib/postTemplates'
  import type { BackendSiteChatUser } from '$lib/api/backend'
  import CompanionMap from './CompanionMap.svelte'

  export let template: CompanionTemplate
  export let postId: number
  export let full = false
  type State = { is_owner: boolean; closed: boolean; expired: boolean; has_responded: boolean; chat_id: number | null; responses: { id: number; user: BackendSiteChatUser; message: string }[] }
  let state: State | null = null
  let loginOpen = false
  let busy = false
  let error = ''
  let message = ''
  let mounted = false
  let requestNumber = 0
  $: date = template.data.starts_at ? new Date(template.data.starts_at) : null
  $: dateLabel = date && !Number.isNaN(date.getTime()) ? date.toLocaleString('ru-RU', { dateStyle: 'long', timeStyle: 'short' }) : ''
  $: if (mounted && full) void loadState(postId, $siteToken)

  async function loadState(id: number, token: string | null) {
    const number = ++requestNumber
    try {
      const response = await fetch(`/api/posts/${id}/companion/`, { credentials: 'include', headers: token ? { Authorization: `Bearer ${token}` } : {} })
      const payload = await response.json()
      if (number !== requestNumber) return
      if (!response.ok) throw new Error(payload.error || 'Не удалось загрузить отклики.')
      state = payload.companion
      error = ''
    } catch (e) { if (number === requestNumber) error = (e as Error).message }
  }
  async function act(action: string, responseId?: number) {
    if (!$siteToken) {
      loginOpen = true
      return
    }
    if (busy) return
    busy = true; error = ''
    try {
      const response = await fetch(`/api/posts/${postId}/companion/`, {
        method: 'POST', credentials: 'include',
        headers: { Authorization: `Bearer ${$siteToken}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, response_id: responseId, message }),
      })
      const payload = await response.json()
      if (!response.ok) throw new Error(payload.error || 'Не удалось сохранить отклик.')
      state = payload.companion
      if (action === 'approve' && state?.chat_id) await goto(`/chats/${state.chat_id}`)
    } catch (e) { error = (e as Error).message }
    finally { busy = false }
  }
  onMount(() => { mounted = true; return () => { requestNumber++ } })
</script>

<LoginModal bind:open={loginOpen} />

<section class="mb-4 space-y-3 rounded-2xl border border-violet-200 bg-violet-50/50 p-4 text-slate-900 dark:border-violet-900 dark:bg-violet-950/20 dark:text-zinc-100" aria-label="Поиск спутника">
  <span class="text-xs font-semibold uppercase tracking-wide text-violet-700 dark:text-violet-300">Поиск спутника</span>
  <p class="whitespace-pre-wrap break-words">{template.data.description}</p>
  <p class="text-sm font-medium"><time datetime={template.data.starts_at}>{dateLabel}</time></p>
  {#if template.data.place}<p class="text-sm">{template.data.place}</p>{/if}
  {#if template.data.radius_m}<p class="text-sm text-slate-500 dark:text-zinc-400">В радиусе {template.data.radius_m.toLocaleString('ru-RU')} м от точки</p>{/if}
  {#if full}
    <CompanionMap lat={template.data.lat} lng={template.data.lng} radius={template.data.radius_m} />
    {#if error}<p role="alert" class="text-sm text-red-600 dark:text-red-300">{error}</p>{/if}
    {#if state?.closed}
      <p class="font-medium">Спутник выбран. Встреча подтверждена.</p>
      <a class="inline-block rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white" href={`/chats/${state.chat_id}`}>Перейти в чат</a>
    {:else if state?.is_owner}
      <div class="flex items-center justify-between gap-2">
        <h3 class="font-semibold">Отклики ({state.responses.length})</h3>
        <button class="text-sm text-violet-700 dark:text-violet-300" on:click={() => loadState(postId, $siteToken)} disabled={busy}>Обновить</button>
      </div>
      {#if state.expired}<p class="text-sm">Встреча уже началась. Приём откликов завершён.</p>{/if}
      {#each state.responses as response (response.id)}
        <div class="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-white p-3 dark:bg-zinc-900">
          <div class="min-w-0 flex-1">
            <a class="font-medium hover:underline" href={response.user.profile_url || `/users/${response.user.username}`}>{response.user.display_name || response.user.username}</a>
            {#if response.message}<p class="mt-1 whitespace-pre-wrap break-words text-sm text-slate-500 dark:text-zinc-400">{response.message}</p>{/if}
          </div>
          <button class="rounded-xl bg-violet-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50" disabled={busy || state.expired} on:click={() => act('approve', response.id)}>Выбрать спутника</button>
        </div>
      {:else}<p class="text-sm text-slate-500 dark:text-zinc-400">Пока никто не откликнулся. Мы уведомим вас о новых откликах.</p>{/each}
      <p class="text-xs text-slate-500 dark:text-zinc-400">После выбора объявление закроется. Место и время встречи сохранятся в чате.</p>
    {:else if state?.expired}
      <p class="text-sm">Встреча уже началась. Приём откликов завершён.</p>
    {:else if state?.has_responded}
      <p class="text-sm font-medium">Вы откликнулись. Когда автор выберет вас, встреча появится в общем чате.</p>
      <button class="text-sm underline disabled:opacity-50" disabled={busy} on:click={() => act('withdraw')}>Отозвать отклик</button>
    {:else if state}
      {#if $siteToken}<label class="block text-sm">Сообщение автору (необязательно)
        <textarea class="mt-1 w-full rounded-xl border border-slate-300 bg-white p-3 dark:border-zinc-700 dark:bg-zinc-900" maxlength="500" rows="2" bind:value={message}></textarea>
      </label>{/if}
      <button class="rounded-xl bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50" disabled={busy} on:click={() => act('respond')}>{busy ? 'Сохраняем…' : 'Откликнуться'}</button>
      {#if !$siteToken}<p class="text-xs text-slate-500 dark:text-zinc-400">Чтобы откликнуться, войдите или зарегистрируйтесь.</p>{/if}
    {:else if !error}<p class="text-sm text-slate-500">Загружаем отклики…</p>{/if}
  {:else}<a class="inline-block text-sm font-medium text-violet-700 hover:underline dark:text-violet-300" href={`/b/post/${postId}`} data-sveltekit-preload-data="off">Посмотреть приглашение →</a>{/if}
</section>
