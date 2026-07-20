<script lang="ts">
  import { browser } from '$app/environment'
  import { onMount } from 'svelte'
  import {
    buildComunAnalyticsUrl,
    type BackendComunAnalytics,
    type BackendComunAnalyticsPeriod,
  } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import { locale } from '$lib/translations'

  export let data

  type Language = 'ru' | 'en' | 'de' | 'es' | 'fr' | 'pt' | 'tr' | 'id'
  type Copy = {
    pageTitle: string
    title: string
    back: string
    allTime: string
    today: string
    week: string
    month: string
    views: string
    comments: string
    subscribers: string
    current: string
    gained: string
    lost: string
    net: string
    activityTitle: string
    activityDescription: string
    subscribersTitle: string
    subscribersDescription: string
    loading: string
    authRequired: string
    forbidden: string
    loadError: string
    collectionStarted: string
  }

  const copyByLanguage: Record<Language, Copy> = {
    ru: { pageTitle: 'Статистика сообщества', title: 'Статистика', back: 'В сообщество', allTime: 'За всё время', today: 'Сегодня', week: '7 дней', month: '30 дней', views: 'Просмотры постов', comments: 'Комментарии', subscribers: 'Подписчики', current: 'Сейчас', gained: 'Новые', lost: 'Отписались', net: 'Изменение', activityTitle: 'Активность за 30 дней', activityDescription: 'Просмотры постов и новые комментарии по дням', subscribersTitle: 'Динамика подписчиков', subscribersDescription: 'Подписки и отписки по дням', loading: 'Загружаем статистику…', authRequired: 'Войдите в аккаунт администратора сообщества.', forbidden: 'Статистика доступна только создателю и модераторам сообщества.', loadError: 'Не удалось загрузить статистику.', collectionStarted: 'Разбивка просмотров по дням и изменения подписчиков учитываются с' },
    en: { pageTitle: 'Community analytics', title: 'Analytics', back: 'Back to community', allTime: 'All time', today: 'Today', week: '7 days', month: '30 days', views: 'Post views', comments: 'Comments', subscribers: 'Subscribers', current: 'Current', gained: 'Gained', lost: 'Lost', net: 'Net change', activityTitle: 'Activity over 30 days', activityDescription: 'Daily post views and new comments', subscribersTitle: 'Subscriber dynamics', subscribersDescription: 'Daily subscriptions and unsubscriptions', loading: 'Loading analytics…', authRequired: 'Sign in with a community administrator account.', forbidden: 'Analytics are available only to the community creator and moderators.', loadError: 'Could not load analytics.', collectionStarted: 'Daily view breakdown and subscriber changes are tracked since' },
    de: { pageTitle: 'Community-Statistik', title: 'Statistik', back: 'Zur Community', allTime: 'Gesamt', today: 'Heute', week: '7 Tage', month: '30 Tage', views: 'Beitragsaufrufe', comments: 'Kommentare', subscribers: 'Abonnenten', current: 'Aktuell', gained: 'Neu', lost: 'Verloren', net: 'Veränderung', activityTitle: 'Aktivität der letzten 30 Tage', activityDescription: 'Tägliche Beitragsaufrufe und neue Kommentare', subscribersTitle: 'Abonnentenentwicklung', subscribersDescription: 'Tägliche Abonnements und Abmeldungen', loading: 'Statistik wird geladen…', authRequired: 'Melde dich mit einem Community-Administratorkonto an.', forbidden: 'Die Statistik ist nur für Ersteller und Moderatoren verfügbar.', loadError: 'Statistik konnte nicht geladen werden.', collectionStarted: 'Die tägliche Aufschlüsselung und Abonnentenänderungen werden erfasst seit' },
    es: { pageTitle: 'Estadísticas de la comunidad', title: 'Estadísticas', back: 'Volver a la comunidad', allTime: 'Todo el tiempo', today: 'Hoy', week: '7 días', month: '30 días', views: 'Vistas de publicaciones', comments: 'Comentarios', subscribers: 'Suscriptores', current: 'Actuales', gained: 'Nuevos', lost: 'Bajas', net: 'Cambio neto', activityTitle: 'Actividad de 30 días', activityDescription: 'Vistas y nuevos comentarios por día', subscribersTitle: 'Dinámica de suscriptores', subscribersDescription: 'Suscripciones y bajas por día', loading: 'Cargando estadísticas…', authRequired: 'Inicia sesión con una cuenta administradora.', forbidden: 'Las estadísticas solo están disponibles para el creador y los moderadores.', loadError: 'No se pudieron cargar las estadísticas.', collectionStarted: 'El desglose diario de vistas y los cambios de suscriptores se registran desde' },
    fr: { pageTitle: 'Statistiques de la communauté', title: 'Statistiques', back: 'Retour à la communauté', allTime: 'Depuis toujours', today: "Aujourd'hui", week: '7 jours', month: '30 jours', views: 'Vues des publications', comments: 'Commentaires', subscribers: 'Abonnés', current: 'Actuels', gained: 'Nouveaux', lost: 'Perdus', net: 'Variation nette', activityTitle: 'Activité sur 30 jours', activityDescription: 'Vues et nouveaux commentaires par jour', subscribersTitle: 'Évolution des abonnés', subscribersDescription: 'Abonnements et désabonnements par jour', loading: 'Chargement des statistiques…', authRequired: 'Connectez-vous avec un compte administrateur.', forbidden: 'Les statistiques sont réservées au créateur et aux modérateurs.', loadError: 'Impossible de charger les statistiques.', collectionStarted: 'La répartition quotidienne des vues et les changements d’abonnés sont suivis depuis le' },
    pt: { pageTitle: 'Estatísticas da comunidade', title: 'Estatísticas', back: 'Voltar à comunidade', allTime: 'Todo o período', today: 'Hoje', week: '7 dias', month: '30 dias', views: 'Visualizações dos posts', comments: 'Comentários', subscribers: 'Assinantes', current: 'Atuais', gained: 'Novos', lost: 'Perdidos', net: 'Variação líquida', activityTitle: 'Atividade em 30 dias', activityDescription: 'Visualizações e novos comentários por dia', subscribersTitle: 'Dinâmica de assinantes', subscribersDescription: 'Inscrições e cancelamentos por dia', loading: 'Carregando estatísticas…', authRequired: 'Entre com uma conta administradora da comunidade.', forbidden: 'As estatísticas estão disponíveis apenas para o criador e moderadores.', loadError: 'Não foi possível carregar as estatísticas.', collectionStarted: 'A divisão diária de visualizações e as mudanças de assinantes são registradas desde' },
    tr: { pageTitle: 'Topluluk istatistikleri', title: 'İstatistikler', back: 'Topluluğa dön', allTime: 'Tüm zamanlar', today: 'Bugün', week: '7 gün', month: '30 gün', views: 'Gönderi görüntülemeleri', comments: 'Yorumlar', subscribers: 'Aboneler', current: 'Mevcut', gained: 'Yeni', lost: 'Ayrılan', net: 'Net değişim', activityTitle: '30 günlük etkinlik', activityDescription: 'Günlük gönderi görüntülemeleri ve yeni yorumlar', subscribersTitle: 'Abone dinamikleri', subscribersDescription: 'Günlük abonelikler ve ayrılmalar', loading: 'İstatistikler yükleniyor…', authRequired: 'Topluluk yöneticisi hesabıyla giriş yapın.', forbidden: 'İstatistikler yalnızca topluluk sahibi ve moderatörler içindir.', loadError: 'İstatistikler yüklenemedi.', collectionStarted: 'Günlük görüntüleme dökümü ve abone değişiklikleri şu tarihten itibaren izleniyor:' },
    id: { pageTitle: 'Statistik komunitas', title: 'Statistik', back: 'Kembali ke komunitas', allTime: 'Sepanjang waktu', today: 'Hari ini', week: '7 hari', month: '30 hari', views: 'Tampilan postingan', comments: 'Komentar', subscribers: 'Pelanggan', current: 'Saat ini', gained: 'Baru', lost: 'Berhenti', net: 'Perubahan bersih', activityTitle: 'Aktivitas 30 hari', activityDescription: 'Tampilan postingan dan komentar baru per hari', subscribersTitle: 'Dinamika pelanggan', subscribersDescription: 'Langganan dan berhenti berlangganan per hari', loading: 'Memuat statistik…', authRequired: 'Masuk dengan akun administrator komunitas.', forbidden: 'Statistik hanya tersedia untuk pembuat dan moderator komunitas.', loadError: 'Statistik tidak dapat dimuat.', collectionStarted: 'Rincian tampilan harian dan perubahan pelanggan dilacak sejak' },
  }

  const slug = String(data?.slug ?? '')
  let analytics: BackendComunAnalytics | null = null
  let loading = true
  let error = ''
  let loadedToken: string | null | undefined
  let periodCards: Array<{ label: string; rows: Array<{ label: string; value: number; signed?: boolean }> }> = []

  $: localeLanguage = String($locale || 'ru').split('-')[0]
  $: language = (['ru', 'en', 'de', 'es', 'fr', 'pt', 'tr', 'id'].includes(localeLanguage) ? localeLanguage : 'ru') as Language
  $: copy = copyByLanguage[language]
  $: numberFormatter = new Intl.NumberFormat(language)
  $: dateFormatter = new Intl.DateTimeFormat(language, { day: 'numeric', month: 'short' })
  $: maxActivity = Math.max(1, ...(analytics?.series ?? []).map((row) => Math.max(row.views, row.comments)))
  $: maxSubscriberChange = Math.max(1, ...(analytics?.series ?? []).map((row) => Math.max(row.subscribers_gained, row.subscribers_lost)))
  $: periodCards = analytics
    ? [
        {
          label: copy.allTime,
          rows: [
            { label: copy.views, value: analytics.periods.all_time.views },
            { label: copy.comments, value: analytics.periods.all_time.comments },
            { label: copy.subscribers, value: analytics.comun.subscribers_count },
          ],
        },
        { label: copy.today, rows: periodRows(analytics.periods.day) },
        { label: copy.week, rows: periodRows(analytics.periods.week) },
        { label: copy.month, rows: periodRows(analytics.periods.month) },
      ]
    : []

  const formatNumber = (value: number | null | undefined) => numberFormatter.format(Number(value ?? 0))
  const formatDate = (value: string) => dateFormatter.format(new Date(`${value}T12:00:00`))
  const periodRows = (period: BackendComunAnalyticsPeriod | undefined) => [
    { label: copy.views, value: period?.views ?? 0 },
    { label: copy.comments, value: period?.comments ?? 0 },
    { label: copy.net, value: period?.subscribers_net ?? 0, signed: true },
  ]
  const signedNumber = (value: number) => `${value > 0 ? '+' : ''}${formatNumber(value)}`
  const barHeight = (value: number, max: number) => `${Math.max(value ? 4 : 0, (value / max) * 100)}%`

  const loadAnalytics = async (token: string | null) => {
    loadedToken = token
    analytics = null
    error = ''
    if (!token) {
      loading = false
      error = copy.authRequired
      return
    }
    loading = true
    try {
      const response = await fetch(buildComunAnalyticsUrl(slug), {
        headers: { Authorization: `Bearer ${token}` },
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        error = response.status === 403 ? copy.forbidden : copy.loadError
        return
      }
      analytics = payload as BackendComunAnalytics
    } catch (loadError) {
      console.error('Failed to load community analytics', loadError)
      error = copy.loadError
    } finally {
      loading = false
    }
  }

  onMount(() => loadAnalytics($siteToken))
  $: if (browser && loadedToken !== undefined && loadedToken !== $siteToken) {
    loadAnalytics($siteToken)
  }
</script>

<svelte:head>
  <title>{analytics?.comun.name ? `${copy.title} · ${analytics.comun.name}` : copy.pageTitle}</title>
</svelte:head>

<main class="mx-auto w-full max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
  {#if loading}
    <div class="py-20 text-center text-sm text-slate-500 dark:text-zinc-400">{copy.loading}</div>
  {:else if error}
    <section class="border-y border-slate-200 py-12 text-center dark:border-zinc-800">
      <p class="text-sm text-slate-600 dark:text-zinc-300">{error}</p>
      <a class="mt-4 inline-flex text-sm font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400" href={`/comuns/${encodeURIComponent(slug)}`}>{copy.back}</a>
    </section>
  {:else if analytics}
    <header class="flex flex-col gap-3 border-b border-slate-200 pb-5 dark:border-zinc-800 sm:flex-row sm:items-end sm:justify-between">
      <div class="min-w-0">
        <h1 class="text-2xl font-bold text-slate-950 dark:text-zinc-50">{copy.title}</h1>
        <p class="mt-1 truncate text-sm text-slate-500 dark:text-zinc-400">{analytics.comun.name}</p>
      </div>
      <a class="text-sm font-semibold text-blue-600 hover:text-blue-700 dark:text-blue-400" href={`/comuns/${encodeURIComponent(slug)}`}>{copy.back}</a>
    </header>

    <section class="grid gap-x-6 border-b border-slate-200 dark:border-zinc-800 sm:grid-cols-2 lg:grid-cols-4">
      {#each periodCards as card}
        <div class="py-5">
          <h2 class="text-xs font-bold uppercase text-slate-500 dark:text-zinc-400">{card.label}</h2>
          <dl class="mt-4 space-y-3">
            {#each card.rows as row}
              <div class="flex items-baseline justify-between gap-4">
                <dt class="text-sm text-slate-600 dark:text-zinc-400">{row.label}</dt>
                <dd class:positive={row.signed && row.value > 0} class:negative={row.signed && row.value < 0} class="text-lg font-bold tabular-nums text-slate-950 dark:text-zinc-50">{row.signed ? signedNumber(row.value) : formatNumber(row.value)}</dd>
              </div>
            {/each}
          </dl>
        </div>
      {/each}
    </section>

    <section class="border-b border-slate-200 py-6 dark:border-zinc-800">
      <div class="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 class="text-lg font-bold text-slate-950 dark:text-zinc-50">{copy.activityTitle}</h2>
          <p class="text-sm text-slate-500 dark:text-zinc-400">{copy.activityDescription}</p>
        </div>
        <div class="flex gap-4 text-xs font-medium text-slate-600 dark:text-zinc-300">
          <span class="legend legend-views">{copy.views}</span>
          <span class="legend legend-comments">{copy.comments}</span>
        </div>
      </div>
      <div class="mt-5 overflow-x-auto pb-2">
        <div class="chart-grid min-w-[760px]" aria-label={copy.activityTitle}>
          {#each analytics.series as row, index (row.date)}
            <div class="chart-column" title={`${formatDate(row.date)} · ${copy.views}: ${formatNumber(row.views)} · ${copy.comments}: ${formatNumber(row.comments)}`}>
              <div class="activity-bars">
                <span class="activity-bar views-bar" style={`height:${barHeight(row.views, maxActivity)}`}></span>
                <span class="activity-bar comments-bar" style={`height:${barHeight(row.comments, maxActivity)}`}></span>
              </div>
              <span class="chart-date">{index % 5 === 0 || index === analytics.series.length - 1 ? formatDate(row.date) : ''}</span>
            </div>
          {/each}
        </div>
      </div>
      <p class="mt-2 text-xs text-slate-500 dark:text-zinc-500">{copy.collectionStarted} {formatDate(analytics.tracking.started_at.slice(0, 10))}</p>
    </section>

    <section class="py-6">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 class="text-lg font-bold text-slate-950 dark:text-zinc-50">{copy.subscribersTitle}</h2>
          <p class="text-sm text-slate-500 dark:text-zinc-400">{copy.subscribersDescription}</p>
        </div>
        <div class="text-right">
          <div class="text-xs font-medium text-slate-500 dark:text-zinc-400">{copy.current}</div>
          <div class="text-2xl font-bold tabular-nums text-slate-950 dark:text-zinc-50">{formatNumber(analytics.comun.subscribers_count)}</div>
        </div>
      </div>
      <div class="mt-5 overflow-x-auto pb-2">
        <div class="subscriber-chart min-w-[760px]">
          {#each analytics.series as row, index (row.date)}
            <div class="subscriber-column" title={`${formatDate(row.date)} · ${copy.gained}: ${formatNumber(row.subscribers_gained)} · ${copy.lost}: ${formatNumber(row.subscribers_lost)}`}>
              <div class="subscriber-half subscriber-positive"><span style={`height:${barHeight(row.subscribers_gained, maxSubscriberChange)}`}></span></div>
              <div class="subscriber-half subscriber-negative"><span style={`height:${barHeight(row.subscribers_lost, maxSubscriberChange)}`}></span></div>
              <span class="chart-date">{index % 5 === 0 || index === analytics.series.length - 1 ? formatDate(row.date) : ''}</span>
            </div>
          {/each}
        </div>
      </div>
      <div class="mt-3 flex gap-4 text-xs font-medium text-slate-600 dark:text-zinc-300">
        <span class="legend legend-gained">{copy.gained}</span>
        <span class="legend legend-lost">{copy.lost}</span>
      </div>
    </section>
  {/if}
</main>

<style>
  .positive { color: #15803d; }
  .negative { color: #dc2626; }
  .legend { display: inline-flex; align-items: center; gap: 0.4rem; }
  .legend::before { width: 0.55rem; height: 0.55rem; border-radius: 2px; content: ''; }
  .legend-views::before { background: #2563eb; }
  .legend-comments::before { background: #0f766e; }
  .legend-gained::before { background: #16a34a; }
  .legend-lost::before { background: #dc2626; }
  .chart-grid { display: grid; grid-template-columns: repeat(30, minmax(18px, 1fr)); height: 230px; border-bottom: 1px solid rgb(203 213 225); background-image: linear-gradient(to bottom, rgb(226 232 240 / 0.65) 1px, transparent 1px); background-size: 100% 25%; }
  .chart-column { display: grid; grid-template-rows: 1fr 24px; min-width: 0; }
  .activity-bars { display: flex; align-items: end; justify-content: center; gap: 2px; padding: 0 2px; }
  .activity-bar { width: min(9px, 42%); min-height: 0; border-radius: 2px 2px 0 0; transition: height 180ms ease; }
  .views-bar { background: #2563eb; }
  .comments-bar { background: #0f766e; }
  .chart-date { overflow: visible; white-space: nowrap; padding-top: 7px; font-size: 10px; color: #64748b; }
  .subscriber-chart { display: grid; grid-template-columns: repeat(30, minmax(18px, 1fr)); height: 250px; }
  .subscriber-column { display: grid; grid-template-rows: 104px 104px 28px; min-width: 0; }
  .subscriber-half { display: flex; justify-content: center; padding: 0 4px; }
  .subscriber-half span { width: min(12px, 72%); min-height: 0; }
  .subscriber-positive { align-items: end; border-bottom: 1px solid rgb(148 163 184); }
  .subscriber-positive span { background: #16a34a; border-radius: 2px 2px 0 0; }
  .subscriber-negative { align-items: start; background-image: linear-gradient(to bottom, rgb(226 232 240 / 0.55) 1px, transparent 1px); background-size: 100% 50%; }
  .subscriber-negative span { background: #dc2626; border-radius: 0 0 2px 2px; }
  @media (prefers-color-scheme: dark) {
    .chart-grid { border-color: rgb(63 63 70); background-image: linear-gradient(to bottom, rgb(63 63 70 / 0.6) 1px, transparent 1px); }
    .subscriber-positive { border-color: rgb(82 82 91); }
    .subscriber-negative { background-image: linear-gradient(to bottom, rgb(63 63 70 / 0.55) 1px, transparent 1px); }
  }
</style>
