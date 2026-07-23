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
  import { locale } from '$lib/translations'
  import { normalizeInterfaceLanguage } from '$lib/postLanguages'

  const PAGE_SIZE = 20
  const copyByLanguage = {
    ru: { locale: 'ru-RU', title: 'История оповещений', description: 'Здесь хранится вся история. В меню показываются только последние записи.', markAll: 'Прочитать все', marking: 'Отмечаем...', loading: 'Загружаем оповещения...', empty: 'Пока оповещений нет.', fresh: 'Новое', more: 'Показать еще', loadingMore: 'Загружаем...', loadError: 'Не удалось загрузить историю оповещений', markError: 'Не удалось отметить оповещения прочитанными' },
    en: { locale: 'en-US', title: 'Notification history', description: 'Your full history is stored here. The menu shows only the latest items.', markAll: 'Mark all as read', marking: 'Marking...', loading: 'Loading notifications...', empty: 'No notifications yet.', fresh: 'New', more: 'Show more', loadingMore: 'Loading...', loadError: 'Could not load notification history', markError: 'Could not mark notifications as read' },
    de: { locale: 'de-DE', title: 'Benachrichtigungsverlauf', description: 'Hier wird der gesamte Verlauf gespeichert. Das Menue zeigt nur die neuesten Eintraege.', markAll: 'Alle als gelesen markieren', marking: 'Wird markiert...', loading: 'Benachrichtigungen werden geladen...', empty: 'Noch keine Benachrichtigungen.', fresh: 'Neu', more: 'Mehr anzeigen', loadingMore: 'Wird geladen...', loadError: 'Benachrichtigungsverlauf konnte nicht geladen werden', markError: 'Benachrichtigungen konnten nicht als gelesen markiert werden' },
    es: { locale: 'es-ES', title: 'Historial de notificaciones', description: 'Aqui se guarda todo el historial. El menu solo muestra las entradas mas recientes.', markAll: 'Marcar todo como leido', marking: 'Marcando...', loading: 'Cargando notificaciones...', empty: 'Todavia no hay notificaciones.', fresh: 'Nuevo', more: 'Mostrar mas', loadingMore: 'Cargando...', loadError: 'No se pudo cargar el historial de notificaciones', markError: 'No se pudieron marcar las notificaciones como leidas' },
    fr: { locale: 'fr-FR', title: 'Historique des notifications', description: 'Tout l’historique est conserve ici. Le menu affiche uniquement les elements recents.', markAll: 'Tout marquer comme lu', marking: 'Marquage...', loading: 'Chargement des notifications...', empty: 'Aucune notification pour le moment.', fresh: 'Nouveau', more: 'Afficher plus', loadingMore: 'Chargement...', loadError: 'Impossible de charger l’historique des notifications', markError: 'Impossible de marquer les notifications comme lues' },
    pt: { locale: 'pt-PT', title: 'Historico de notificacoes', description: 'Todo o historico fica guardado aqui. O menu mostra apenas os itens mais recentes.', markAll: 'Marcar tudo como lido', marking: 'A marcar...', loading: 'A carregar notificacoes...', empty: 'Ainda nao existem notificacoes.', fresh: 'Novo', more: 'Mostrar mais', loadingMore: 'A carregar...', loadError: 'Nao foi possivel carregar o historico de notificacoes', markError: 'Nao foi possivel marcar as notificacoes como lidas' },
    tr: { locale: 'tr-TR', title: 'Bildirim gecmisi', description: 'Tum gecmis burada saklanir. Menude yalnizca en yeni kayitlar gosterilir.', markAll: 'Tumunu okundu isaretle', marking: 'Isaretleniyor...', loading: 'Bildirimler yukleniyor...', empty: 'Henuz bildirim yok.', fresh: 'Yeni', more: 'Daha fazla goster', loadingMore: 'Yukleniyor...', loadError: 'Bildirim gecmisi yuklenemedi', markError: 'Bildirimler okundu olarak isaretlenemedi' },
    id: { locale: 'id-ID', title: 'Riwayat notifikasi', description: 'Semua riwayat disimpan di sini. Menu hanya menampilkan item terbaru.', markAll: 'Tandai semua sudah dibaca', marking: 'Menandai...', loading: 'Memuat notifikasi...', empty: 'Belum ada notifikasi.', fresh: 'Baru', more: 'Tampilkan lainnya', loadingMore: 'Memuat...', loadError: 'Riwayat notifikasi tidak dapat dimuat', markError: 'Notifikasi tidak dapat ditandai sudah dibaca' },
  }

  let items: SiteNotificationItem[] = []
  let loading = false
  let loadingMore = false
  let markAllLoading = false
  let unreadCount = 0
  let totalCount = 0
  let lastTokenValue: string | null = null
  $: copy = copyByLanguage[normalizeInterfaceLanguage($locale) ?? 'ru']

  const formatTime = (value: string) => {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return date.toLocaleString(copy.locale, {
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
        content: (error as Error)?.message ?? copy.loadError,
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
        content: (error as Error)?.message ?? copy.markError,
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
        {copy.title}
      </div>
      <div class="text-xs text-slate-500 dark:text-zinc-400">
        {copy.description}
      </div>
    </div>
    <Button
      size="sm"
      color="ghost"
      on:click={markEverythingRead}
      disabled={!unreadCount || markAllLoading}
    >
      {markAllLoading ? copy.marking : copy.markAll}
    </Button>
  </div>

  {#if loading}
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      {copy.loading}
    </div>
  {:else if !items.length}
    <div class="rounded-xl border border-dashed border-slate-200 dark:border-zinc-800 px-4 py-5 text-sm text-slate-500 dark:text-zinc-400">
      {copy.empty}
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
                    {copy.fresh}
                  </span>
                {/if}
              </div>
              {#if item.message}
                <div class="mt-1 text-sm text-slate-600 dark:text-zinc-300 break-words whitespace-pre-line">
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
        {loadingMore ? copy.loadingMore : copy.more}
      </Button>
    </div>
  {/if}
</div>
