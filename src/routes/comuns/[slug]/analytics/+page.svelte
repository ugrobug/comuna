<script lang="ts">
  import { browser } from '$app/environment'
  import { onMount } from 'svelte'
  import {
    buildComunAnalyticsUrl,
    type BackendComunAnalytics,
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
  let activeActivityIndex: number | null = null
  let activeSubscriberIndex: number | null = null

  $: localeLanguage = String($locale || 'ru').split('-')[0]
  $: language = (['ru', 'en', 'de', 'es', 'fr', 'pt', 'tr', 'id'].includes(localeLanguage) ? localeLanguage : 'ru') as Language
  $: copy = copyByLanguage[language]
  $: numberFormatter = new Intl.NumberFormat(language)
  $: dateFormatter = new Intl.DateTimeFormat(language, { day: 'numeric', month: 'short' })
  $: maxActivity = Math.max(1, ...(analytics?.series ?? []).map((row) => Math.max(row.views, row.comments)))
  $: maxSubscriberChange = Math.max(1, ...(analytics?.series ?? []).map((row) => Math.max(row.subscribers_gained, row.subscribers_lost)))
  $: activityAxisMax = axisMaximum(maxActivity, 4)
  $: activityTicks = axisTicks(activityAxisMax, 4)
  $: subscriberAxisMax = axisMaximum(maxSubscriberChange, 2)
  $: subscriberTicks = [subscriberAxisMax, subscriberAxisMax / 2, 0, -(subscriberAxisMax / 2), -subscriberAxisMax]

  const formatNumber = (value: number | null | undefined) => numberFormatter.format(Number(value ?? 0))
  const formatDate = (value: string) => dateFormatter.format(new Date(`${value}T12:00:00`))
  const axisMaximum = (value: number, intervalCount: number) => {
    const safeValue = Math.max(0, Number(value) || 0)
    return Math.max(intervalCount, Math.ceil(safeValue / intervalCount) * intervalCount)
  }
  const axisTicks = (maximum: number, intervalCount: number) =>
    Array.from({ length: intervalCount + 1 }, (_, index) => maximum - (maximum / intervalCount) * index)
  const activityBarHeight = (value: number) => `${Math.max(0, (value / activityAxisMax) * 100)}%`
  const subscriberBarHeight = (value: number) => `${Math.max(0, (value / subscriberAxisMax) * 50)}%`
  const tooltipPosition = (index: number) => `${((index + 0.5) / 30) * 100}%`

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

<main class="analytics-dashboard">
  {#if loading}
    <div class="loading-state">{copy.loading}</div>
  {:else if error}
    <section class="notice-section">
      <p>{error}</p>
      <a href={`/comuns/${encodeURIComponent(slug)}`}>{copy.back}</a>
    </section>
  {:else if analytics}
    <header class="dashboard-header">
      <div>
        <p class="eyebrow">{analytics.comun.name}</p>
        <h1>{copy.title}</h1>
      </div>
      <a class="back-link" href={`/comuns/${encodeURIComponent(slug)}`}>{copy.back}</a>
    </header>

    <section class="chart-card">
      <div class="section-header">
        <div>
          <p class="section-label">{copy.title}</p>
          <h2>{copy.activityTitle}</h2>
          <p class="section-description">{copy.activityDescription}</p>
        </div>
        <div class="chart-legend">
          <span class="legend legend-views">{copy.views}</span>
          <span class="legend legend-comments">{copy.comments}</span>
        </div>
      </div>

      <div class="chart-scroll">
        <div class="scaled-chart" aria-label={copy.activityTitle}>
          <div class="y-axis" aria-hidden="true">
            {#each activityTicks as tick}
              <span>{formatNumber(tick)}</span>
            {/each}
          </div>
          <div class="chart-plot">
            <div class="grid-lines" aria-hidden="true">
              {#each activityTicks as _}<span></span>{/each}
            </div>
            <div class="chart-columns">
              {#each analytics.series as row, index (row.date)}
                <button
                  type="button"
                  class="chart-column"
                  aria-label={`${formatDate(row.date)}. ${copy.views}: ${formatNumber(row.views)}. ${copy.comments}: ${formatNumber(row.comments)}`}
                  on:mouseenter={() => (activeActivityIndex = index)}
                  on:mouseleave={() => (activeActivityIndex = null)}
                  on:focus={() => (activeActivityIndex = index)}
                  on:blur={() => (activeActivityIndex = null)}
                >
                  <span class="activity-bar views-bar" style={`height:${activityBarHeight(row.views)}`}></span>
                  <span class="activity-bar comments-bar" style={`height:${activityBarHeight(row.comments)}`}></span>
                </button>
              {/each}
            </div>
            {#if activeActivityIndex !== null && analytics.series[activeActivityIndex]}
              {@const row = analytics.series[activeActivityIndex]}
              <div class="chart-tooltip" role="tooltip" style={`--tooltip-position:${tooltipPosition(activeActivityIndex)}`}>
                <strong>{formatDate(row.date)}</strong>
                <span><i class="tooltip-swatch views-swatch"></i>{copy.views}<b>{formatNumber(row.views)}</b></span>
                <span><i class="tooltip-swatch comments-swatch"></i>{copy.comments}<b>{formatNumber(row.comments)}</b></span>
              </div>
            {/if}
          </div>
          <div class="x-axis" aria-hidden="true">
            {#each analytics.series as row, index (row.date)}
              <span>{index % 5 === 0 || index === analytics.series.length - 1 ? formatDate(row.date) : ''}</span>
            {/each}
          </div>
        </div>
      </div>
      <p class="tracking-note">{copy.collectionStarted} {formatDate(analytics.tracking.started_at.slice(0, 10))}</p>
    </section>

    <section class="chart-card">
      <div class="section-header">
        <div>
          <p class="section-label">{copy.title}</p>
          <h2>{copy.subscribersTitle}</h2>
          <p class="section-description">{copy.subscribersDescription}</p>
        </div>
        <div class="chart-legend">
          <span class="legend legend-gained">{copy.gained}</span>
          <span class="legend legend-lost">{copy.lost}</span>
        </div>
      </div>

      <div class="chart-scroll">
        <div class="scaled-chart" aria-label={copy.subscribersTitle}>
          <div class="y-axis" aria-hidden="true">
            {#each subscriberTicks as tick}
              <span>{formatNumber(tick)}</span>
            {/each}
          </div>
          <div class="chart-plot subscriber-plot">
            <div class="grid-lines" aria-hidden="true">
              {#each subscriberTicks as _}<span></span>{/each}
            </div>
            <div class="chart-columns">
              {#each analytics.series as row, index (row.date)}
                <button
                  type="button"
                  class="chart-column subscriber-column"
                  aria-label={`${formatDate(row.date)}. ${copy.gained}: ${formatNumber(row.subscribers_gained)}. ${copy.lost}: ${formatNumber(row.subscribers_lost)}`}
                  on:mouseenter={() => (activeSubscriberIndex = index)}
                  on:mouseleave={() => (activeSubscriberIndex = null)}
                  on:focus={() => (activeSubscriberIndex = index)}
                  on:blur={() => (activeSubscriberIndex = null)}
                >
                  <span class="subscriber-bar gained-bar" style={`height:${subscriberBarHeight(row.subscribers_gained)}`}></span>
                  <span class="subscriber-bar lost-bar" style={`height:${subscriberBarHeight(row.subscribers_lost)}`}></span>
                </button>
              {/each}
            </div>
            {#if activeSubscriberIndex !== null && analytics.series[activeSubscriberIndex]}
              {@const row = analytics.series[activeSubscriberIndex]}
              <div class="chart-tooltip" role="tooltip" style={`--tooltip-position:${tooltipPosition(activeSubscriberIndex)}`}>
                <strong>{formatDate(row.date)}</strong>
                <span><i class="tooltip-swatch gained-swatch"></i>{copy.gained}<b>{formatNumber(row.subscribers_gained)}</b></span>
                <span><i class="tooltip-swatch lost-swatch"></i>{copy.lost}<b>{formatNumber(row.subscribers_lost)}</b></span>
                <span class="net-row">{copy.net}<b>{row.subscribers_net > 0 ? '+' : ''}{formatNumber(row.subscribers_net)}</b></span>
              </div>
            {/if}
          </div>
          <div class="x-axis" aria-hidden="true">
            {#each analytics.series as row, index (row.date)}
              <span>{index % 5 === 0 || index === analytics.series.length - 1 ? formatDate(row.date) : ''}</span>
            {/each}
          </div>
        </div>
      </div>
    </section>
  {/if}
</main>

<style>
  .analytics-dashboard {
    width: min(1120px, calc(100% - 32px));
    margin: 0 auto;
    padding: 20px 0;
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .dashboard-header,
  .section-header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: 18px;
  }

  .dashboard-header {
    padding: 8px 0 4px;
  }

  .eyebrow,
  .section-label,
  .section-description,
  .tracking-note {
    margin: 0;
    color: rgb(100 116 139);
  }

  .eyebrow,
  .section-label {
    margin-bottom: 4px;
    font-size: 13px;
  }

  h1,
  h2 {
    margin: 0;
    color: rgb(15 23 42);
    font-weight: 600;
    letter-spacing: 0;
  }

  h1 {
    font-size: 32px;
    line-height: 1.12;
  }

  h2 {
    font-size: 22px;
    line-height: 1.2;
  }

  .section-description {
    margin-top: 6px;
    font-size: 14px;
    line-height: 1.45;
  }

  .back-link {
    min-height: 38px;
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    padding: 0 14px;
    background: white;
    color: rgb(51 65 85);
    display: inline-flex;
    align-items: center;
    font-size: 14px;
    font-weight: 600;
  }

  .back-link:hover {
    border-color: rgb(148 163 184);
    color: rgb(15 23 42);
  }

  .chart-card,
  .notice-section {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: white;
    padding: 18px;
  }

  .notice-section {
    text-align: center;
  }

  .notice-section p {
    margin: 0;
    color: rgb(71 85 105);
  }

  .notice-section a {
    margin-top: 14px;
    color: rgb(2 132 199);
    display: inline-flex;
    font-weight: 600;
  }

  .loading-state {
    padding: 80px 0;
    color: rgb(100 116 139);
    text-align: center;
    font-size: 14px;
  }

  .chart-legend {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: 16px;
    color: rgb(71 85 105);
    font-size: 12px;
    font-weight: 600;
  }

  .legend {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
  }

  .legend::before,
  .tooltip-swatch {
    width: 9px;
    height: 9px;
    border-radius: 2px;
    content: '';
    flex: 0 0 auto;
  }

  .legend-views::before,
  .views-bar,
  .views-swatch {
    background: rgb(37 99 235);
  }

  .legend-comments::before,
  .comments-bar,
  .comments-swatch {
    background: rgb(13 148 136);
  }

  .legend-gained::before,
  .gained-bar,
  .gained-swatch {
    background: rgb(22 163 74);
  }

  .legend-lost::before,
  .lost-bar,
  .lost-swatch {
    background: rgb(220 38 38);
  }

  .chart-scroll {
    margin-top: 22px;
    overflow-x: auto;
    padding-bottom: 4px;
  }

  .scaled-chart {
    min-width: 760px;
    display: grid;
    grid-template-columns: 54px minmax(0, 1fr);
    grid-template-rows: 240px 32px;
  }

  .y-axis {
    grid-column: 1;
    grid-row: 1;
    padding-right: 10px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    color: rgb(100 116 139);
    font-size: 11px;
    line-height: 1;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }

  .y-axis span {
    transform: translateY(-50%);
  }

  .y-axis span:last-child {
    transform: translateY(50%);
  }

  .chart-plot {
    grid-column: 2;
    grid-row: 1;
    position: relative;
    min-width: 0;
  }

  .grid-lines,
  .chart-columns {
    position: absolute;
    inset: 0;
  }

  .grid-lines {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    pointer-events: none;
  }

  .grid-lines span {
    width: 100%;
    border-top: 1px solid rgb(226 232 240);
  }

  .grid-lines span:last-child {
    border-color: rgb(148 163 184);
  }

  .chart-columns,
  .x-axis {
    display: grid;
    grid-template-columns: repeat(30, minmax(18px, 1fr));
  }

  .chart-column {
    min-width: 0;
    border: 0;
    padding: 0 3px;
    background: transparent;
    color: inherit;
    display: flex;
    align-items: flex-end;
    justify-content: center;
    gap: 3px;
    position: relative;
    outline: none;
    font: inherit;
    cursor: default;
  }

  .chart-column:hover,
  .chart-column:focus-visible {
    background: rgb(239 246 255 / 0.72);
  }

  .activity-bar {
    width: min(10px, 42%);
    min-height: 0;
    border-radius: 2px 2px 0 0;
    transition: height 180ms ease, opacity 120ms ease;
  }

  .chart-column:hover .activity-bar,
  .chart-column:focus-visible .activity-bar,
  .chart-column:hover .subscriber-bar,
  .chart-column:focus-visible .subscriber-bar {
    opacity: 0.78;
  }

  .x-axis {
    grid-column: 2;
    grid-row: 2;
    color: rgb(100 116 139);
    font-size: 10px;
  }

  .x-axis span {
    min-width: 0;
    padding-top: 8px;
    white-space: nowrap;
  }

  .subscriber-column {
    display: block;
  }

  .subscriber-bar {
    width: min(12px, calc(100% - 8px));
    min-height: 0;
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    transition: height 180ms ease, opacity 120ms ease;
  }

  .gained-bar {
    bottom: 50%;
    border-radius: 2px 2px 0 0;
  }

  .lost-bar {
    top: 50%;
    border-radius: 0 0 2px 2px;
  }

  .subscriber-plot .grid-lines span:nth-child(3) {
    border-color: rgb(100 116 139);
  }

  .chart-tooltip {
    --tooltip-position: 50%;
    width: 228px;
    min-height: 0;
    position: absolute;
    z-index: 3;
    top: 12px;
    left: clamp(114px, var(--tooltip-position), calc(100% - 114px));
    transform: translateX(-50%);
    border: 1px solid rgb(203 213 225);
    border-radius: 8px;
    background: white;
    padding: 11px 12px;
    box-shadow: 0 8px 24px rgb(15 23 42 / 0.13);
    color: rgb(51 65 85);
    display: grid;
    gap: 7px;
    pointer-events: none;
    font-size: 12px;
  }

  .chart-tooltip strong {
    color: rgb(15 23 42);
    font-size: 13px;
  }

  .chart-tooltip span {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 7px;
  }

  .chart-tooltip .net-row {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .chart-tooltip b {
    color: rgb(15 23 42);
    font-weight: 650;
    font-variant-numeric: tabular-nums;
  }

  .tracking-note {
    margin-top: 10px;
    padding-left: 54px;
    font-size: 12px;
  }

  :global(.dark) h1,
  :global(.dark) h2,
  :global(.dark) .chart-tooltip strong,
  :global(.dark) .chart-tooltip b {
    color: white;
  }

  :global(.dark) .chart-card,
  :global(.dark) .notice-section,
  :global(.dark) .back-link,
  :global(.dark) .chart-tooltip {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27);
  }

  :global(.dark) .back-link,
  :global(.dark) .chart-legend,
  :global(.dark) .chart-tooltip,
  :global(.dark) .notice-section p {
    color: rgb(212 212 216);
  }

  :global(.dark) .grid-lines span {
    border-color: rgb(63 63 70);
  }

  :global(.dark) .grid-lines span:last-child,
  :global(.dark) .subscriber-plot .grid-lines span:nth-child(3) {
    border-color: rgb(113 113 122);
  }

  :global(.dark) .chart-column:hover,
  :global(.dark) .chart-column:focus-visible {
    background: rgb(39 39 42 / 0.8);
  }

  @media (max-width: 700px) {
    .analytics-dashboard {
      width: min(100% - 24px, 1120px);
      padding-top: 12px;
    }

    .dashboard-header,
    .section-header {
      align-items: stretch;
      flex-direction: column;
    }

    h1 {
      font-size: 28px;
    }

    h2 {
      font-size: 19px;
    }

    .back-link {
      align-self: flex-start;
    }

    .chart-legend {
      justify-content: flex-start;
    }

    .chart-card {
      padding: 16px;
    }
  }
</style>
