<script lang="ts">
  import { onMount } from 'svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import { fetchSiteChats, siteToken } from '$lib/siteAuth'
  import type { BackendSiteChat } from '$lib/api/backend'

  let chats: BackendSiteChat[] = []
  let loading = false
  let error = ''
  let loginModalOpen = false

  const participantName = (chat: BackendSiteChat) =>
    (chat.participant.display_name || '').trim() || `@${chat.participant.username}`

  const lastMessagePreview = (chat: BackendSiteChat) => {
    const message = (chat.last_message?.body || '').replace(/\s+/g, ' ').trim()
    if (!message) return 'Пока нет сообщений'
    return message.length > 120 ? `${message.slice(0, 120).trim()}...` : message
  }

  const formatDate = (value?: string | null) => {
    if (!value) return ''
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  }

  const loadChats = async () => {
    if (!$siteToken) return
    loading = true
    error = ''
    try {
      const payload = await fetchSiteChats(50, 0)
      chats = payload.chats
    } catch (err) {
      error = (err as Error)?.message ?? 'Не удалось загрузить чаты'
    } finally {
      loading = false
    }
  }

  onMount(() => {
    void loadChats()
  })
</script>

<LoginModal bind:open={loginModalOpen} />

<div class="mx-auto flex w-full max-w-3xl flex-col gap-5">
  <div class="flex items-center justify-between gap-3">
    <div>
      <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100">Чаты</h1>
      <p class="mt-1 text-sm text-slate-500 dark:text-zinc-400">
        Личные диалоги с пользователями Тамбура.
      </p>
    </div>
    {#if $siteToken}
      <button
        type="button"
        class="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-50 disabled:opacity-60 dark:border-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-900"
        on:click={loadChats}
        disabled={loading}
      >
        Обновить
      </button>
    {/if}
  </div>

  {#if !$siteToken}
    <div class="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
      <div class="font-medium text-slate-900 dark:text-zinc-100">Нужна авторизация</div>
      <div class="mt-1">Войдите, чтобы видеть свои чаты и писать пользователям.</div>
      <button
        type="button"
        class="mt-4 rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        on:click={() => (loginModalOpen = true)}
      >
        Войти
      </button>
    </div>
  {:else if loading && !chats.length}
    <div class="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
      Загружаем чаты...
    </div>
  {:else if error}
    <div class="rounded-2xl border border-red-200 bg-white p-5 text-sm text-red-600 dark:border-red-900/50 dark:bg-zinc-900 dark:text-red-300">
      {error}
    </div>
  {:else if chats.length}
    <div class="divide-y divide-slate-200 overflow-hidden rounded-2xl border border-slate-200 bg-white dark:divide-zinc-800 dark:border-zinc-800 dark:bg-zinc-900">
      {#each chats as chat (chat.id)}
        <a
          href={`/chats/${chat.id}`}
          class="flex gap-3 px-4 py-4 transition hover:bg-slate-50 dark:hover:bg-zinc-800/70"
        >
          <Avatar
            url={chat.participant.avatar_url || undefined}
            alt={participantName(chat)}
            width={44}
          />
          <div class="min-w-0 flex-1">
            <div class="flex items-center justify-between gap-3">
              <div class="truncate font-medium text-slate-900 dark:text-zinc-100">
                {participantName(chat)}
              </div>
              <div class="shrink-0 text-xs text-slate-400 dark:text-zinc-500">
                {formatDate(chat.last_message_at || chat.updated_at)}
              </div>
            </div>
            <div class="mt-1 truncate text-sm text-slate-500 dark:text-zinc-400">
              {lastMessagePreview(chat)}
            </div>
          </div>
          {#if chat.unread_count}
            <div class="mt-1 flex h-6 min-w-6 items-center justify-center rounded-full bg-sky-600 px-2 text-xs font-semibold text-white">
              {chat.unread_count}
            </div>
          {/if}
        </a>
      {/each}
    </div>
  {:else}
    <div class="rounded-2xl border border-slate-200 bg-white p-5 text-sm text-slate-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
      Чатов пока нет. Откройте профиль пользователя и нажмите «Написать».
    </div>
  {/if}
</div>
