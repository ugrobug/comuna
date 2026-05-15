<script lang="ts">
  import { Button, toast } from 'mono-svelte'
  import {
    fetchSiteNotifications,
    markAllSiteNotificationsRead,
    markSiteNotificationRead,
    siteToken,
    siteUser,
    type SiteNotificationItem,
  } from '$lib/siteAuth'

  const PAGE_SIZE = 20

  let items: SiteNotificationItem[] = []
  let loading = false
  let loadingMore = false
  let markAllLoading = false
  let unreadCount = 0
  let totalCount = 0
  let lastTokenValue: string | null = null

  const formatTime = (value: string) => {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  const loadNotifications = async (reset = false) => {
    if (!$siteToken || !$siteUser) {
      items = []
      unreadCount = 0
      totalCount = 0
      return
    }

    if (reset) {
      loading = true
    } else {
      loadingMore = true
    }

    try {
      const offset = reset ? 0 : items.length
      const data = await fetchSiteNotifications(PAGE_SIZE, false, offset)
      const nextItems = data.items ?? []
      items = reset ? nextItems : [...items, ...nextItems]
      unreadCount = data.unread_count
      totalCount = data.total_count
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось загрузить историю уведомлений',
        type: 'error',
      })
    } finally {
      loading = false
      loadingMore = false
    }
  }

  const markOneRead = async (item: SiteNotificationItem) => {
    if (item.is_read) return

    items = items.map((current) =>
      current.id === item.id
        ? { ...current, is_read: true, read_at: new Date().toISOString() }
        : current
    )
    unreadCount = Math.max(0, unreadCount - 1)

    try {
      const data = await markSiteNotificationRead(item.id)
      unreadCount = data.unread_count
      if (data.item) {
        items = items.map((current) => (current.id === item.id ? data.item : current))
      }
    } catch (error) {
      loadNotifications(true).catch(() => {})
    }
  }

  const markEverythingRead = async () => {
    if (!unreadCount) return
    markAllLoading = true
    try {
      await markAllSiteNotificationsRead()
      items = items.map((item) =>
        item.is_read ? item : { ...item, is_read: true, read_at: new Date().toISOString() }
      )
      unreadCount = 0
    } catch (error) {
      toast({
        content: (error as Error)?.message ?? 'Не удалось отметить уведомления прочитанными',
        type: 'error',
      })
    } finally {
      markAllLoading = false
    }
  }

  $: hasMore = items.length < totalCount

  $: if ($siteToken !== lastTokenValue) {
    lastTokenValue = $siteToken
    if ($siteToken) {
      loadNotifications(true).catch(() => {})
    } else {
      items = []
      unreadCount = 0
      totalCount = 0
    }
  }
</script>

<div class="flex flex-col gap-4" id="notifications-history">
  <div class="flex flex-wrap items-center justify-between gap-2">
    <div>
      <div class="text-base font-medium text-slate-900 dark:text-zinc-100">
        История оповещений
      </div>
      <div class="text-xs text-slate-500 dark:text-zinc-400">
        Хранится вся история. В колокольчике показываются только последние записи.
      </div>
    </div>
    <Button
      size="sm"
      color="ghost"
      on:click={markEverythingRead}
      disabled={!unreadCount || markAllLoading}
    >
      {markAllLoading ? 'Отмечаем...' : 'Прочитать все'}
    </Button>
  </div>

  {#if loading}
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      Загружаем историю уведомлений...
    </div>
  {:else if !items.length}
    <div class="rounded-xl border border-dashed border-slate-200 dark:border-zinc-800 px-4 py-5 text-sm text-slate-500 dark:text-zinc-400">
      Пока уведомлений нет.
    </div>
  {:else}
    <div class="flex flex-col gap-2">
      {#each items as item}
        <a
          href={item.link_url || '/settings#notifications'}
          class="block rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 px-4 py-3 transition-colors hover:bg-slate-50 dark:hover:bg-zinc-800/70"
          on:click={() => {
            markOneRead(item).catch(() => {})
          }}
        >
          <div class="flex items-start gap-3">
            <div class="pt-1">
              <span
                class="block h-2.5 w-2.5 rounded-full {item.is_read ? 'bg-slate-300 dark:bg-zinc-700' : 'bg-blue-500'}"
              ></span>
            </div>
            <div class="min-w-0 flex-1">
              <div class="flex flex-wrap items-center gap-2">
                <div class="text-sm font-medium text-slate-900 dark:text-zinc-100">
                  {item.title}
                  {#if (item.group_count || 1) > 1}
                    <span class="ml-1 text-xs font-normal text-slate-500 dark:text-zinc-400">
                      ({item.group_count})
                    </span>
                  {/if}
                </div>
                {#if !item.is_read}
                  <span class="rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-950/40 dark:text-blue-300">
                    Новое
                  </span>
                {/if}
              </div>
              {#if item.message}
                <div class="mt-1 text-sm text-slate-600 dark:text-zinc-300 break-words">
                  {item.message}
                </div>
              {/if}
              <div class="mt-2 text-xs text-slate-500 dark:text-zinc-400">
                {formatTime(item.updated_at || item.created_at)}
              </div>
            </div>
          </div>
        </a>
      {/each}
    </div>
  {/if}

  {#if hasMore}
    <div class="flex justify-center">
      <Button size="sm" on:click={() => loadNotifications(false)} disabled={loadingMore}>
        {loadingMore ? 'Загружаем...' : 'Показать ещё'}
      </Button>
    </div>
  {/if}
</div>
