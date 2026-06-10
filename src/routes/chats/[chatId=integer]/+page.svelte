<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { onDestroy, onMount, tick } from 'svelte'
  import { Icon, PaperAirplane } from 'svelte-hero-icons'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import {
    fetchSiteChat,
    reportAndBlockSiteChat,
    sendSiteChatMessage,
    siteToken,
    siteUser,
  } from '$lib/siteAuth'
  import type { BackendSiteChat, BackendSiteChatMessage } from '$lib/api/backend'

  let chat: BackendSiteChat | null = null
  let messages: BackendSiteChatMessage[] = []
  let loading = false
  let sending = false
  let reporting = false
  let error = ''
  let body = ''
  let loginModalOpen = false
  let messagesEl: HTMLDivElement | null = null
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  $: chatId = Number($page.params.chatId || 0)

  const participantName = (value: BackendSiteChat | null) =>
    (value?.participant.display_name || '').trim() || (value?.participant.username ? `@${value.participant.username}` : 'Чат')

  const formatMessageTime = (value: string) =>
    new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))

  const scrollToBottom = async () => {
    await tick()
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight
    }
  }

  const loadChat = async (showLoader = true) => {
    if (!$siteToken || !chatId) return
    if (showLoader) loading = true
    error = ''
    try {
      const payload = await fetchSiteChat(chatId, 80)
      chat = payload.chat
      messages = payload.messages
      await scrollToBottom()
    } catch (err) {
      error = (err as Error)?.message ?? 'Не удалось загрузить чат'
    } finally {
      loading = false
    }
  }

  const sendMessage = async () => {
    const normalized = body.trim()
    if (!normalized || sending || !chatId) return
    sending = true
    error = ''
    try {
      const payload = await sendSiteChatMessage(chatId, normalized)
      chat = payload.chat
      messages = [...messages, payload.message]
      body = ''
      await scrollToBottom()
    } catch (err) {
      error = (err as Error)?.message ?? 'Не удалось отправить сообщение'
    } finally {
      sending = false
    }
  }

  const reportAndBlock = async () => {
    if (!$siteToken || reporting || !chatId) return
    const confirmed = confirm(
      'Пожаловаться на пользователя и заблокировать чат? Чат исчезнет из вашего списка.'
    )
    if (!confirmed) return
    reporting = true
    error = ''
    try {
      await reportAndBlockSiteChat(chatId)
      await goto('/chats')
    } catch (err) {
      error = (err as Error)?.message ?? 'Не удалось заблокировать чат'
    } finally {
      reporting = false
    }
  }

  const onTextKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendMessage()
    }
  }

  onMount(() => {
    void loadChat()
    refreshTimer = setInterval(() => {
      void loadChat(false)
    }, 8000)
  })

  onDestroy(() => {
    if (refreshTimer) clearInterval(refreshTimer)
  })
</script>

<LoginModal bind:open={loginModalOpen} />

<div class="mx-auto flex h-[calc(100vh-7rem)] min-h-[540px] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
  <div class="flex items-center gap-3 border-b border-slate-200 px-4 py-3 dark:border-zinc-800">
    <a
      href="/chats"
      class="rounded-full px-3 py-1.5 text-sm text-slate-600 transition hover:bg-slate-100 dark:text-zinc-300 dark:hover:bg-zinc-800"
    >
      Назад
    </a>
    {#if chat}
      <Avatar
        url={chat.participant.avatar_url || undefined}
        alt={participantName(chat)}
        width={38}
      />
    {/if}
    <div class="min-w-0">
      <div class="truncate font-semibold text-slate-900 dark:text-zinc-100">
        {participantName(chat)}
      </div>
      {#if chat?.participant.profile_url}
        <a
          href={chat.participant.profile_url}
          class="text-xs text-slate-500 transition hover:text-slate-900 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          @{chat.participant.username}
        </a>
      {/if}
    </div>
    {#if chat}
      <button
        type="button"
        class="ml-auto rounded-full border border-red-200 px-3 py-1.5 text-xs font-medium text-red-700 transition hover:border-red-300 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/60 dark:text-red-300 dark:hover:bg-red-950/40"
        disabled={reporting}
        on:click={reportAndBlock}
      >
        {reporting ? 'Отправляем жалобу' : 'Пожаловаться и заблокировать'}
      </button>
    {/if}
  </div>

  {#if !$siteToken}
    <div class="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center text-sm text-slate-500 dark:text-zinc-400">
      <div class="font-medium text-slate-900 dark:text-zinc-100">Нужна авторизация</div>
      <button
        type="button"
        class="rounded-full bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        on:click={() => (loginModalOpen = true)}
      >
        Войти
      </button>
    </div>
  {:else if loading && !messages.length}
    <div class="flex flex-1 items-center justify-center p-6 text-sm text-slate-500 dark:text-zinc-400">
      Загружаем чат...
    </div>
  {:else}
    <div bind:this={messagesEl} class="flex-1 overflow-y-auto px-4 py-5">
      {#if messages.length}
        <div class="flex flex-col gap-3">
          {#each messages as message (message.id)}
            {@const mine = message.sender_id === $siteUser?.id}
            <div class={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
              <div class={`max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow-sm ${
                mine
                  ? 'bg-slate-900 text-white dark:bg-zinc-100 dark:text-zinc-900'
                  : 'bg-slate-100 text-slate-900 dark:bg-zinc-800 dark:text-zinc-100'
              }`}>
                <div class="whitespace-pre-wrap break-words">{message.body}</div>
                <div class={`mt-1 text-[11px] ${mine ? 'text-white/70 dark:text-zinc-500' : 'text-slate-500 dark:text-zinc-400'}`}>
                  {formatMessageTime(message.created_at)}
                </div>
              </div>
            </div>
          {/each}
        </div>
      {:else}
        <div class="flex h-full items-center justify-center text-center text-sm text-slate-500 dark:text-zinc-400">
          Сообщений пока нет. Напишите первым.
        </div>
      {/if}
    </div>

    {#if error}
      <div class="border-t border-red-100 px-4 py-2 text-sm text-red-600 dark:border-red-900/50 dark:text-red-300">
        {error}
      </div>
    {/if}

    <form class="flex gap-2 border-t border-slate-200 p-3 dark:border-zinc-800" on:submit|preventDefault={sendMessage}>
      <textarea
        bind:value={body}
        rows="2"
        maxlength="5000"
        class="min-h-11 flex-1 resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:border-zinc-500"
        placeholder="Напишите сообщение..."
        on:keydown={onTextKeydown}
        disabled={sending}
      ></textarea>
      <button
        type="submit"
        class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-slate-900 text-white transition hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
        disabled={sending || !body.trim()}
        aria-label="Отправить"
        title="Отправить"
      >
        <Icon src={PaperAirplane} size="18" micro />
      </button>
    </form>
  {/if}
</div>
