<script lang="ts">
  import { onDestroy, onMount } from 'svelte'
  import { Menu } from 'mono-svelte'
  import { Bell, ArrowPath, Icon } from 'svelte-hero-icons'
  import {
    fetchSiteNotifications,
    markAllSiteNotificationsRead,
    markSiteNotificationRead,
    siteUser,
    type SiteNotificationItem,
  } from '$lib/siteAuth'

  let open = false
  let loading = false
  let items: SiteNotificationItem[] = []
  let unreadCount = 0
  let errorMessage = ''
  let pollTimer: ReturnType<typeof setInterval> | null = null

  const formatTime = (value: string) => {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const syncFromApi = async (options?: { silent?: boolean; limit?: number }) => {
    if (!$siteUser) {
      items = []
      unreadCount = 0
      errorMessage = ''
      return
    }
    const silent = options?.silent ?? false
    const limit = options?.limit ?? 8
    if (!silent) {
      loading = true
    }
    try {
      const data = await fetchSiteNotifications(limit)
      items = data.items
      unreadCount = data.unread_count
      errorMessage = ''
    } catch (error) {
      if (!silent) {
        errorMessage = (error as Error)?.message ?? 'Не удалось загрузить уведомления'
      }
    } finally {
      if (!silent) {
        loading = false
      }
    }
  }

  const startPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
    pollTimer = setInterval(() => {
      if (!$siteUser) return
      if (open) return
      syncFromApi({ silent: true, limit: 6 }).catch(() => {})
    }, 30000)
  }

  const stopPolling = () => {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  const onMarkRead = async (item: SiteNotificationItem) => {
    if (item.is_read) return

    items = items.map((current) =>
      current.id === item.id ? { ...current, is_read: true, read_at: new Date().toISOString() } : current
    )
    unreadCount = Math.max(0, unreadCount - 1)

    try {
      const data = await markSiteNotificationRead(item.id)
      unreadCount = data.unread_count
      if (data.item) {
        items = items.map((current) => (current.id === item.id ? data.item : current))
      }
    } catch (error) {
      syncFromApi({ silent: true }).catch(() => {})
    }
  }

  const onMarkAllRead = async () => {
    if (!unreadCount) return
    try {
      loading = true
      await markAllSiteNotificationsRead()
      items = items.map((item) =>
        item.is_read ? item : { ...item, is_read: true, read_at: new Date().toISOString() }
      )
      unreadCount = 0
    } catch (error) {
      errorMessage = (error as Error)?.message ?? 'Не удалось отметить все уведомления'
    } finally {
      loading = false
    }
  }

  $: if (open && $siteUser) {
    syncFromApi({ limit: 10 }).catch(() => {})
  }

  $: if (!$siteUser) {
    items = []
    unreadCount = 0
    errorMessage = ''
    open = false
  }

  onMount(() => {
    if ($siteUser) {
      syncFromApi({ silent: true, limit: 6 }).catch(() => {})
    }
    startPolling()
  })

  onDestroy(() => {
    stopPolling()
  })
</script>

<Menu placement="bottom-end" bind:open>
  <button
    slot="target"
    type="button"
    class="relative w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
    aria-label="Оповещения"
    title="Оповещения"
  >
    <Icon src={Bell} size="18" class="w-4 h-4 md:w-[18px] md:h-[18px]" />
    {#if unreadCount > 0}
      <span
        class="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-white text-[10px] leading-[18px] font-semibold text-center"
        aria-label={`Непрочитанных: ${unreadCount}`}
      >
        {unreadCount > 99 ? '99+' : unreadCount}
      </span>
    {/if}
  </button>

  <div class="w-full min-w-0 flex flex-col">
    <div class="flex items-center justify-between gap-2 px-1 pb-1">
      <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">Оповещения</div>
      <div class="flex items-center gap-1">
        <button
          type="button"
          class="w-7 h-7 rounded-full grid place-items-center hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
          title="Обновить"
          on:click={() => syncFromApi({ limit: 10 }).catch(() => {})}
        >
          <Icon src={ArrowPath} size="14" />
        </button>
        <button
          type="button"
          class="text-xs px-2 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors disabled:opacity-50"
          disabled={!unreadCount || loading}
          on:click={onMarkAllRead}
        >
          Прочитать все
        </button>
      </div>
    </div>

    {#if loading && !items.length}
      <div class="px-2 py-4 text-sm text-slate-500 dark:text-zinc-400">
        Загружаем уведомления...
      </div>
    {:else if errorMessage && !items.length}
      <div class="px-2 py-4 text-sm text-red-600 dark:text-red-400">{errorMessage}</div>
    {:else if !items.length}
      <div class="px-2 py-4 text-sm text-slate-500 dark:text-zinc-400">
        Пока уведомлений нет.
      </div>
    {:else}
      <div class="flex flex-col gap-1">
        {#each items as item}
          <a
            href={item.link_url || '/settings#notifications'}
            class="block rounded-lg px-2 py-2 transition-colors hover:bg-slate-100 dark:hover:bg-zinc-800 {item.is_read ? '' : 'bg-blue-50/70 dark:bg-blue-950/30'}"
            on:click={() => {
              onMarkRead(item).catch(() => {})
            }}
          >
            <div class="flex items-start gap-2">
              <div class="pt-1">
                <span
                  class="block w-2 h-2 rounded-full {item.is_read ? 'bg-slate-300 dark:bg-zinc-700' : 'bg-blue-500'}"
                />
              </div>
              <div class="min-w-0 flex-1">
                <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                  {item.title}
                </div>
                {#if item.message}
                  <div class="text-xs text-slate-600 dark:text-zinc-300 break-words">
                    {item.message}
                  </div>
                {/if}
                <div class="mt-1 text-[11px] text-slate-500 dark:text-zinc-400">
                  {formatTime(item.created_at)}
                </div>
              </div>
            </div>
          </a>
        {/each}
      </div>
    {/if}

    <div class="pt-1 mt-1 border-t border-slate-200 dark:border-zinc-800">
      <a
        href="/settings#notifications"
        class="block rounded-lg px-2 py-2 text-sm text-slate-700 dark:text-zinc-200 hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
      >
        Настройки оповещений
      </a>
    </div>
  </div>
</Menu>
