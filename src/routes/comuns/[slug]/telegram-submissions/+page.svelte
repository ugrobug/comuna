<script lang="ts">
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import {
    buildComunTelegramSubmissionUrl,
    buildComunTelegramSubmissionsUrl,
    type BackendComun,
    type BackendComunTelegramSubmission,
  } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'

  export let data

  let comun: BackendComun | null = data?.comun ?? null
  let status = String(data?.status || 'pending')
  let items: BackendComunTelegramSubmission[] = []
  let total = 0
  let loading = false
  let savingId: number | null = null
  let errorMessage = ''

  const statusOptions = [
    { value: 'pending', label: 'На модерации' },
    { value: 'approved', label: 'Утверждено' },
    { value: 'rejected', label: 'Отклонено' },
  ]

  $: canManage = Boolean($siteToken && comun?.can_moderate)
  $: comunBackPath = comun?.slug ? `/comuns/${encodeURIComponent(comun.slug)}` : '/comuns'

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  const requestTypeLabel = (item: BackendComunTelegramSubmission) =>
    item.request_type === 'knowledge_base' ? 'База знаний' : 'Глоссарий'

  const requesterLabel = (item: BackendComunTelegramSubmission) =>
    item.requested_by?.display_name ||
    item.requested_by?.username ||
    item.telegram_username ||
    'Пользователь Telegram'

  const dateLabel = (value?: string | null) => {
    if (!value) return ''
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  }

  const loadItems = async () => {
    if (!comun?.slug || !canManage) return
    loading = true
    errorMessage = ''
    try {
      const response = await fetch(
        buildComunTelegramSubmissionsUrl(comun.slug, { status, limit: 100 }),
        { headers: authHeaders() }
      )
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload?.error || 'Не удалось загрузить заявки')
      items = (payload?.items ?? []) as BackendComunTelegramSubmission[]
      total = Number(payload?.total ?? items.length) || 0
      if (data?.focusId) {
        queueMicrotask(() => {
          document.getElementById(`submission-${data.focusId}`)?.scrollIntoView({
            behavior: 'smooth',
            block: 'center',
          })
        })
      }
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Не удалось загрузить заявки'
      toast({ content: errorMessage, type: 'error' })
    } finally {
      loading = false
    }
  }

  const setStatus = (nextStatus: string) => {
    if (status === nextStatus) return
    status = nextStatus
    void loadItems()
  }

  const reviewItem = async (
    item: BackendComunTelegramSubmission,
    action: 'approve' | 'reject'
  ) => {
    if (!comun?.slug || !canManage || savingId) return
    savingId = item.id
    errorMessage = ''
    try {
      const body =
        action === 'approve' && item.request_type === 'knowledge_base'
          ? { action, title: item.title }
          : action === 'approve'
            ? {
                action,
                glossary_term: item.glossary_term,
                glossary_definition: item.glossary_definition,
              }
            : { action }
      const response = await fetch(buildComunTelegramSubmissionUrl(comun.slug, item.id), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify(body),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) throw new Error(payload?.error || 'Не удалось обновить заявку')
      items = items.filter((candidate) => candidate.id !== item.id)
      total = Math.max(total - 1, 0)
      toast({
        content: action === 'approve' ? 'Заявка утверждена' : 'Заявка отклонена',
        type: 'success',
      })
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Не удалось обновить заявку'
      toast({ content: errorMessage, type: 'error' })
    } finally {
      savingId = null
    }
  }

  onMount(() => {
    void loadItems()
  })
</script>

<div class="flex max-w-4xl flex-col gap-6">
  <Header pageHeader>
    <div class="flex flex-col gap-2">
      <a href={comunBackPath} class="text-sm text-slate-500 hover:text-slate-800 dark:text-zinc-400 dark:hover:text-zinc-200">
        ← {comun?.name ?? 'Сообщество'}
      </a>
      <h1 class="text-2xl font-bold text-slate-950 dark:text-zinc-50">Заявки из Telegram</h1>
    </div>
  </Header>

  <div class="flex flex-wrap gap-2">
    {#each statusOptions as option}
      <button
        type="button"
        class={`rounded-full px-4 py-2 text-sm transition-colors ${
          status === option.value
            ? 'bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
            : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700'
        }`}
        on:click={() => setStatus(option.value)}
      >
        {option.label}
      </button>
    {/each}
  </div>

  {#if errorMessage}
    <div class="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-300">
      {errorMessage}
    </div>
  {/if}

  {#if loading}
    <div class="rounded-xl border border-slate-200 bg-white px-4 py-6 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
      Загружаем заявки...
    </div>
  {:else if !items.length}
    <div class="rounded-xl border border-slate-200 bg-white px-4 py-6 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
      Заявок нет.
    </div>
  {:else}
    <div class="flex flex-col gap-4">
      {#each items as item (item.id)}
        <article
          id={`submission-${item.id}`}
          class={`rounded-2xl border bg-white p-4 shadow-sm dark:bg-zinc-900 ${
            data?.focusId === item.id
              ? 'border-blue-300 ring-2 ring-blue-100 dark:border-blue-800 dark:ring-blue-950/70'
              : 'border-slate-200 dark:border-zinc-800'
          }`}
        >
          <div class="flex flex-col gap-4">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex flex-wrap items-center gap-2">
                <span class="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 dark:bg-zinc-800 dark:text-zinc-300">
                  {requestTypeLabel(item)}
                </span>
                <span class="text-sm text-slate-500 dark:text-zinc-400">
                  {requesterLabel(item)} · {dateLabel(item.created_at)}
                </span>
              </div>
              {#if item.telegram_source_url}
                <a
                  href={item.telegram_source_url}
                  target="_blank"
                  rel="noreferrer"
                  class="text-sm text-blue-600 hover:underline dark:text-blue-300"
                >
                  Telegram
                </a>
              {/if}
            </div>

            <blockquote class="whitespace-pre-wrap rounded-xl bg-slate-50 p-3 text-sm leading-relaxed text-slate-700 dark:bg-zinc-950/60 dark:text-zinc-300">
              {item.source_text}
            </blockquote>

            {#if status === 'pending' && item.request_type === 'knowledge_base'}
              <label class="flex flex-col gap-1 text-sm">
                <span class="font-medium text-slate-700 dark:text-zinc-300">Заголовок поста</span>
                <input
                  class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none focus:border-blue-400 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                  bind:value={item.title}
                  placeholder="Заголовок"
                />
              </label>
            {:else if status === 'pending'}
              <div class="grid gap-3 md:grid-cols-2">
                <label class="flex flex-col gap-1 text-sm">
                  <span class="font-medium text-slate-700 dark:text-zinc-300">Термин</span>
                  <input
                    class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none focus:border-blue-400 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                    bind:value={item.glossary_term}
                    placeholder="Термин"
                  />
                </label>
                <label class="flex flex-col gap-1 text-sm">
                  <span class="font-medium text-slate-700 dark:text-zinc-300">Расшифровка</span>
                  <textarea
                    class="min-h-24 rounded-xl border border-slate-200 bg-white px-3 py-2 text-slate-900 outline-none focus:border-blue-400 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
                    bind:value={item.glossary_definition}
                    placeholder="Расшифровка"
                  ></textarea>
                </label>
              </div>
            {/if}

            {#if status === 'pending'}
              <div class="flex flex-wrap justify-end gap-2">
                <Button
                  color="secondary"
                  disabled={savingId === item.id}
                  on:click={() => reviewItem(item, 'reject')}
                >
                  Отклонить
                </Button>
                <Button
                  disabled={savingId === item.id}
                  on:click={() => reviewItem(item, 'approve')}
                >
                  {savingId === item.id ? 'Сохраняем...' : 'Утвердить'}
                </Button>
              </div>
            {/if}
          </div>
        </article>
      {/each}
    </div>
  {/if}

  {#if total > items.length}
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      Показано {items.length} из {total}.
    </div>
  {/if}
</div>
