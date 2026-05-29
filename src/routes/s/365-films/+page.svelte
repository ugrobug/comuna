<script lang="ts">
  import { onMount } from 'svelte'
  import { Button, toast } from 'mono-svelte'
  import {
    buildSpecial1001FilmsResumeUrl,
    buildSpecial1001FilmsStartUrl,
    buildSpecial1001FilmsStatusUrl,
  } from '$lib/api/backend'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import TelegramLoginButton from '$lib/components/telegram/TelegramLoginButton.svelte'
  import { refreshSiteUser, siteToken, siteUser } from '$lib/siteAuth'
  import {
    ArrowPath,
    CalendarDays,
    CheckCircle,
    Film,
    Icon,
    LockClosed,
    Play,
  } from 'svelte-hero-icons'

  type FilmJourneyEntry = {
    position: number
    path: string
    completed_at?: string | null
    film?: {
      title: string
      original_title?: string
      year?: number
      category?: string
    }
  }

  type FilmJourneySubscription = {
    status: 'active' | 'paused' | 'completed'
    next_delivery_at: string
    completed_count: number
    total_count: number
    pause_reason?: string
    current_entry?: FilmJourneyEntry | null
  }

  type FilmJourneyStatus = {
    ok: boolean
    total_count: number
    landing_images?: LandingImage[]
    subscription?: FilmJourneySubscription | null
  }

  type LandingImage = {
    slot: string
    title: string
    image_url: string
  }

  let status: FilmJourneyStatus | null = null
  let loading = true
  let actionLoading = false
  let error = ''
  let authOpen = false
  let telegramPromptOpen = false

  const authHeaders = (): Record<string, string> =>
    $siteToken ? { Authorization: `Bearer ${$siteToken}` } : {}

  async function loadStatus() {
    loading = true
    error = ''
    try {
      const response = await fetch(buildSpecial1001FilmsStatusUrl(), {
        credentials: 'include',
        headers: authHeaders(),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось загрузить спецпроект')
      }
      status = data
    } catch (err) {
      error = (err as Error)?.message || 'Не удалось загрузить спецпроект'
    }
    loading = false
  }

  async function postAction(url: string, successMessage = 'Готово') {
    if (!$siteToken) {
      authOpen = true
      return
    }
    actionLoading = true
    try {
      const response = await fetch(url, {
        method: 'POST',
        credentials: 'include',
        headers: authHeaders(),
      })
      const data = await response.json()
      if (!response.ok || !data?.ok) {
        throw new Error(data?.error || 'Не удалось выполнить действие')
      }
      status = {
        ok: true,
        total_count: data.subscription?.total_count ?? status?.total_count ?? 0,
        subscription: data.subscription,
      }
      toast({ content: successMessage, type: 'success' })
    } catch (err) {
      toast({ content: (err as Error)?.message || 'Не удалось выполнить действие', type: 'error' })
    }
    actionLoading = false
  }

  async function startJourney() {
    if (!$siteToken || !$siteUser) {
      authOpen = true
      return
    }
    if (!$siteUser.telegram_linked) {
      telegramPromptOpen = true
      toast({
        content: 'Фильмы будут приходить в Telegram-бота и на сайт. Давайте сначала привяжем Telegram.',
        type: 'info',
      })
      return
    }
    await postAction(
      buildSpecial1001FilmsStartUrl(),
      'Маршрут запущен. Оповещения будут приходить в Telegram-бота и на сайт.',
    )
  }

  async function resumeJourney() {
    if (!$siteToken || !$siteUser) {
      authOpen = true
      return
    }
    if (!$siteUser.telegram_linked) {
      telegramPromptOpen = true
      toast({
        content: 'Чтобы продолжить с оповещениями, давайте привяжем Telegram.',
        type: 'info',
      })
      return
    }
    await postAction(
      buildSpecial1001FilmsResumeUrl(),
      'Маршрут возобновлен. Оповещения будут приходить в Telegram-бота и на сайт.',
    )
  }

  async function handleTelegramLinked() {
    await refreshSiteUser()
    telegramPromptOpen = false
    toast({
      content: 'Telegram привязан. Теперь можно начать маршрут и получать фильм дня в боте.',
      type: 'success',
    })
  }

  const formatDate = (value?: string | null) => {
    if (!value) return ''
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric',
      month: 'long',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(value))
  }

  $: subscription = status?.subscription ?? null
  $: currentEntry = subscription?.current_entry ?? null
  $: progressLabel = subscription
    ? `${subscription.completed_count} из 365`
    : '0 из 365'
  $: landingImages = ['1', '2', '3'].map((slot) => {
    return (
      status?.landing_images?.find((image) => image.slot === slot) ?? {
        slot,
        title: `Кадр ${slot}`,
        image_url: '',
      }
    )
  })

  onMount(loadStatus)
</script>

<svelte:head>
  <title>365 фильмов, которые должен посмотреть каждый</title>
  <meta
    name="description"
    content="Спецпроект Tambur: один фильм в день, секретные ссылки и общий порядок для всех участников."
  />
  <link rel="canonical" href="/s/365-films" />
</svelte:head>

<LoginModal bind:open={authOpen} initialMode="signup" />

<section class="films-page">
  <div class="hero">
    <div class="hero-copy">
      <h1>365 фильмов, которые должен посмотреть каждый</h1>
      <p class="lead">
        Это челлендж без права выбора. Каждый день — один фильм. Посмотрели, оценили,
        перешли к следующему. Пропускать нельзя, выбирать нельзя — просто смотрите
        и открывайте для себя разные жанры, культуры и эпохи.
      </p>
      <div class="actions">
        {#if loading}
          <Button size="lg" disabled>
            <Icon src={ArrowPath} size="18" mini slot="prefix" />
            Загрузка
          </Button>
        {:else if !$siteToken || !$siteUser}
          <Button size="lg" color="primary" on:click={() => (authOpen = true)}>
            <Icon src={LockClosed} size="18" mini slot="prefix" />
            Зарегистрироваться и начать
          </Button>
        {:else if !subscription}
          <Button
            size="lg"
            color="primary"
            loading={actionLoading}
            disabled={actionLoading}
            on:click={startJourney}
          >
            <Icon src={Play} size="18" mini slot="prefix" />
            Начать путешествие
          </Button>
        {:else if subscription.status === 'paused'}
          <Button
            size="lg"
            color="primary"
            loading={actionLoading}
            disabled={actionLoading}
            on:click={resumeJourney}
          >
            <Icon src={Play} size="18" mini slot="prefix" />
            Возобновить
          </Button>
        {:else if currentEntry && !currentEntry.completed_at}
          <Button size="lg" color="primary" href={currentEntry.path}>
            <Icon src={Film} size="18" mini slot="prefix" />
            Открыть текущий фильм
          </Button>
        {:else if subscription.status === 'completed'}
          <Button size="lg" disabled>
            <Icon src={CheckCircle} size="18" mini slot="prefix" />
            Маршрут завершён
          </Button>
        {:else}
          <Button size="lg" disabled>
            <Icon src={CalendarDays} size="18" mini slot="prefix" />
            Следующий фильм {formatDate(subscription.next_delivery_at)}
          </Button>
        {/if}
        {#if $siteUser?.is_staff}
          <Button size="lg" href="/s/365-films/admin">
            Управление фильмами
          </Button>
        {/if}
      </div>
      {#if $siteUser?.telegram_linked && !subscription}
        <p class="notification-note">
          После старта фильм дня будет приходить в Telegram-бота и в уведомления на сайте.
        </p>
      {/if}
      {#if telegramPromptOpen && $siteUser && !$siteUser.telegram_linked}
        <div class="telegram-callout">
          <div>
            <strong>Привяжем Telegram для оповещений</strong>
            <p>
              Секретная ссылка на новый фильм придет в Telegram-бота и останется в уведомлениях на сайте.
            </p>
          </div>
          <TelegramLoginButton
            label="Связать Telegram"
            helperText="Нужно для ежедневных ссылок и напоминаний"
            authIntent="login"
            privacyAccepted={false}
            active={telegramPromptOpen}
            onSuccess={handleTelegramLinked}
          />
        </div>
      {/if}
      {#if error}
        <p class="error">{error}</p>
      {/if}
    </div>

    <div class="project-panel" aria-label="Статус проекта">
      <div class="film-stack">
        {#each landingImages as image}
          <span class:has-image={Boolean(image.image_url)}>
            {#if image.image_url}
              <img src={image.image_url} alt={image.title || 'Кадр из фильма'} loading="lazy" />
            {/if}
          </span>
        {/each}
      </div>
      <div class="panel-grid">
        <div>
          <span>Прогресс</span>
          <strong>{progressLabel}</strong>
        </div>
      </div>
      {#if subscription}
        <div class="status-line">
          {#if subscription.status === 'paused'}
            Пауза: {subscription.pause_reason || 'ждём оценки текущего фильма'}
          {:else if subscription.status === 'completed'}
            Все доступные фильмы пройдены.
          {:else if currentEntry && !currentEntry.completed_at}
            Сейчас открыт фильм #{currentEntry.position}: {currentEntry.film?.title}
          {:else}
            Следующая выдача запланирована на {formatDate(subscription.next_delivery_at)}.
          {/if}
        </div>
      {:else}
        <div class="status-line">Каждый участник идет по одному общему маршруту.</div>
      {/if}
    </div>
  </div>
</section>

<section class="how-it-works">
  <div class="how-inner">
    <div class="how-heading">
      <p>
        Это не каталог и не рейтинг. У всех участников один и тот же порядок фильмов,
        а доступ открывается постепенно: один день, один фильм, одна короткая реакция.
        Фильмы подобрали критики из сообщества
        <a href="https://tambur.pub/comuns/after_the_credits">«После титров»</a>.
      </p>
    </div>

    <div class="steps">
      <article class="step">
        <span class="step-icon">
          <Icon src={Play} size="18" mini />
        </span>
        <h3>Присоединяйтесь</h3>
        <p>Зарегистрируйтесь и подключите Telegram-бота — так мы сможем отправлять вам новые фильмы. Это бесплатно.</p>
      </article>
      <article class="step">
        <span class="step-icon">
          <Icon src={CalendarDays} size="18" mini />
        </span>
        <h3>Получаете фильм дня</h3>
        <p>Раз в сутки приходит название и краткое описание фильма, который вам нужно посмотреть.</p>
      </article>
      <article class="step">
        <span class="step-icon">
          <Icon src={CheckCircle} size="18" mini />
        </span>
        <h3>Оцениваете и комментируете</h3>
        <p>
          Ставите оценку, пишете реакцию, читаете мнения других — и на следующий день
          получаете новый фильм.
        </p>
      </article>
    </div>

    <div class="rules">
      <p>
        Если фильм остался без реакции, через пару дней придёт напоминание — и ещё одно чуть позже.
        Если ответа не будет, подписка ставится на паузу. Вернуться можно в любой момент:
        продолжите с того места, где остановились.
      </p>
    </div>

    <div class="faq" aria-label="Частые вопросы">
      <details>
        <summary>Я могу посмотреть фильм у вас на сайте?</summary>
        <p>
          Нет. Мы даём список, а не сами фильмы. Найти их в интернете не составит труда.
        </p>
      </details>
      <details>
        <summary>Это бесплатно?</summary>
        <p>Да, полностью. Никакой рекламы, никаких донатов.</p>
      </details>
      <details>
        <summary>На все фильмы уйдёт около одного года?</summary>
        <p>
          Да, это большое кинопутешествие. Но можно делать паузы и возвращаться, когда будет настроение.
        </p>
      </details>
      <details>
        <summary>Какие фильмы я смогу увидеть в списке?</summary>
        <p>
          Критики подобрали фильмы разных жанров, эпох и школ. Список намеренно не пересекается
          с привычными топами — здесь другое кино, которое легко пропустить, но сложно забыть.
        </p>
      </details>
      <details>
        <summary>Зачем мне этот список?</summary>
        <p>
          Вы не тратите время на выбор фильма, а просто смотрите — и оцениваете увиденное.
          Короткий комментарий в конце помогает зафиксировать впечатления и сравнить их с
          впечатлениями других. Для любителей кино это способ открыть новые фильмы и не потеряться
          в бесконечных однотипных каталогах.
        </p>
      </details>
    </div>
  </div>
</section>

<style>
  .films-page {
    min-height: auto;
    margin-top: -1rem;
    background: rgb(248 250 252 / 1);
    color: #0f172a;
    padding: clamp(0.25rem, 1.2vw, 0.9rem) clamp(1rem, 4vw, 3rem) 10px;
    display: flex;
    align-items: flex-start;
  }

  .hero {
    display: grid;
    grid-template-columns: minmax(0, 1.1fr) minmax(18rem, 25rem);
    gap: clamp(1.25rem, 4vw, 3.5rem);
    align-items: center;
    max-width: 70rem;
    width: 100%;
    margin: 0 auto;
  }

  .hero-copy {
    display: flex;
    flex-direction: column;
    gap: 0.9rem;
  }

  h1 {
    max-width: 17ch;
    font-size: clamp(1.78rem, 3.68vw, 3.22rem);
    line-height: 1.02;
    letter-spacing: 0;
    font-weight: 500;
  }

  .lead {
    max-width: 42rem;
    color: #475569;
    font-size: clamp(0.98rem, 1.5vw, 1.08rem);
    line-height: 1.55;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 0.25rem;
  }

  .error {
    color: #b91c1c;
  }

  .notification-note {
    max-width: 35rem;
    color: #475569;
    font-size: 0.92rem;
    line-height: 1.45;
  }

  .telegram-callout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(16rem, 20rem);
    gap: 0.8rem;
    align-items: center;
    max-width: 42rem;
    border: 1px solid rgb(191 219 254);
    border-radius: 8px;
    background: rgb(239 246 255);
    padding: 0.85rem;
  }

  .telegram-callout strong {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: 500;
    color: #0f172a;
  }

  .telegram-callout p {
    color: #475569;
    font-size: 0.9rem;
    line-height: 1.45;
  }

  .project-panel {
    border: 1px solid rgb(203 213 225);
    border-radius: 8px;
    background: rgb(255 255 255 / 0.82);
    padding: 1rem;
    box-shadow: 0 18px 48px rgb(15 23 42 / 0.08);
    backdrop-filter: blur(18px);
  }

  .film-stack {
    position: relative;
    height: clamp(9.5rem, 26svh, 14rem);
    margin-bottom: 0.85rem;
  }

  .film-stack span {
    position: absolute;
    inset: 0;
    border-radius: 8px;
    border: 1px solid rgb(203 213 225 / 0.82);
    background:
      linear-gradient(90deg, rgb(15 23 42 / 0.1) 0 12%, transparent 12% 88%, rgb(15 23 42 / 0.1) 88%),
      linear-gradient(145deg, #e2e8f0, #f8fafc 48%, #cbd5e1);
  }

  .film-stack span:nth-child(1) {
    transform: rotate(-7deg) translate(-0.7rem, 0.6rem);
    opacity: 0.72;
  }

  .film-stack span:nth-child(2) {
    transform: rotate(5deg) translate(0.7rem, 0.2rem);
    opacity: 0.82;
  }

  .film-stack span:nth-child(3) {
    background:
      linear-gradient(90deg, rgb(15 23 42 / 0.12) 0 10%, transparent 10% 90%, rgb(15 23 42 / 0.12) 90%),
      linear-gradient(150deg, #f8fafc, rgb(11 93 215 / 0.16) 52%, #e2e8f0);
  }

  .film-stack span.has-image {
    overflow: hidden;
    background: #0f172a;
  }

  .film-stack span.has-image img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .panel-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.6rem;
  }

  .panel-grid div {
    border-radius: 8px;
    background: rgb(241 245 249);
    padding: 0.7rem;
  }

  .panel-grid span,
  .status-line {
    color: #64748b;
    font-size: 0.9rem;
  }

  .panel-grid strong {
    display: block;
    margin-top: 0.18rem;
    font-size: 1.45rem;
    font-weight: 500;
  }

  .status-line {
    margin-top: 0.75rem;
    line-height: 1.45;
  }

  .how-it-works {
    background: rgb(255 255 255);
    color: #0f172a;
    border-top: 1px solid rgb(226 232 240);
    padding: clamp(0.65rem, 1.5vw, 1.2rem) clamp(1rem, 4vw, 3rem) clamp(2rem, 5vw, 4.5rem);
  }

  .how-inner {
    max-width: 70rem;
    margin: 0 auto;
  }

  .how-heading {
    max-width: 46rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
  }

  .how-heading p,
  .step p,
  .rules p,
  .faq p {
    color: #475569;
    line-height: 1.6;
  }

  .how-heading a {
    color: var(--btn-primary-background);
    font-weight: 500;
    text-decoration: underline;
    text-underline-offset: 0.16em;
  }

  .steps {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.85rem;
    margin-top: clamp(0.8rem, 2vw, 1.35rem);
  }

  .step {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: rgb(248 250 252);
    padding: 1rem;
  }

  .step-icon {
    width: 2rem;
    height: 2rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    color: var(--btn-primary-background);
    background: rgb(219 234 254);
    margin-bottom: 0.9rem;
  }

  .step h3 {
    font-size: 1.05rem;
    font-weight: 500;
    margin-bottom: 0.45rem;
  }

  .rules {
    margin-top: 0.85rem;
    border-radius: 8px;
    border: 1px solid rgb(203 213 225);
    padding: 1rem;
    background: rgb(255 255 255);
  }

  .faq {
    margin-top: 1rem;
    display: grid;
    gap: 0.6rem;
  }

  .faq details {
    border: 1px solid rgb(226 232 240);
    border-radius: 8px;
    background: rgb(248 250 252);
    padding: 0.9rem 1rem;
  }

  .faq summary {
    cursor: pointer;
    color: #0f172a;
    font-size: 1rem;
    font-weight: 500;
    line-height: 1.35;
  }

  .faq summary::marker {
    color: var(--btn-primary-background);
  }

  .faq p {
    margin-top: 0.65rem;
  }

  :global(.dark) .films-page {
    background: rgb(9 9 11 / 1);
    color: #fafafa;
  }

  :global(.dark) .lead,
  :global(.dark) .notification-note,
  :global(.dark) .how-heading p,
  :global(.dark) .step p,
  :global(.dark) .rules p,
  :global(.dark) .faq p,
  :global(.dark) .panel-grid span,
  :global(.dark) .status-line {
    color: #a1a1aa;
  }

  :global(.dark) .how-heading a {
    color: #93c5fd;
  }

  :global(.dark) .telegram-callout {
    border-color: rgb(30 64 175 / 0.75);
    background: rgb(30 58 138 / 0.22);
  }

  :global(.dark) .telegram-callout strong {
    color: #fafafa;
  }

  :global(.dark) .telegram-callout p {
    color: #cbd5e1;
  }

  :global(.dark) .project-panel {
    border-color: rgb(39 39 42);
    background: rgb(9 9 11 / 0.8);
    box-shadow: 0 18px 48px rgb(0 0 0 / 0.24);
  }

  :global(.dark) .panel-grid div {
    background: rgb(24 24 27);
  }

  :global(.dark) .film-stack span {
    border-color: rgb(39 39 42 / 0.9);
    background:
      linear-gradient(90deg, rgb(255 255 255 / 0.08) 0 12%, transparent 12% 88%, rgb(255 255 255 / 0.08) 88%),
      linear-gradient(145deg, #18181b, #27272a 48%, #09090b);
  }

  :global(.dark) .film-stack span:nth-child(3) {
    background:
      linear-gradient(90deg, rgb(255 255 255 / 0.09) 0 10%, transparent 10% 90%, rgb(255 255 255 / 0.09) 90%),
      linear-gradient(150deg, #09090b, rgb(37 99 235 / 0.36) 52%, #18181b);
  }

  :global(.dark) .film-stack span.has-image {
    background: #0f172a;
  }

  :global(.dark) .how-it-works {
    background: rgb(9 9 11);
    color: #fafafa;
    border-top-color: rgb(39 39 42);
  }

  :global(.dark) .step {
    border-color: rgb(39 39 42);
    background: rgb(24 24 27);
  }

  :global(.dark) .step-icon {
    background: rgb(30 58 138 / 0.45);
    color: #93c5fd;
  }

  :global(.dark) .rules {
    border-color: rgb(39 39 42);
    background: rgb(9 9 11);
  }

  :global(.dark) .faq details {
    border-color: rgb(39 39 42);
    background: rgb(24 24 27);
  }

  :global(.dark) .faq summary {
    color: #fafafa;
  }

  :global(.dark) .faq summary::marker {
    color: #93c5fd;
  }

  @media (max-width: 820px) {
    .films-page {
      min-height: auto;
      align-items: flex-start;
      padding: 1rem 1rem 1.5rem;
    }

    .hero {
      grid-template-columns: 1fr;
      gap: 1rem;
    }

    h1 {
      max-width: 18ch;
      font-size: clamp(1.55rem, 5.46vw, 2.07rem);
      line-height: 1.02;
    }

    .lead {
      font-size: 0.94rem;
      line-height: 1.45;
    }

    .film-stack {
      height: min(20svh, 8.5rem);
    }

    .project-panel {
      padding: 0.7rem;
    }

    .panel-grid div {
      padding: 0.55rem 0.65rem;
    }

    .panel-grid strong {
      font-size: 1.18rem;
    }

    .status-line {
      font-size: 0.82rem;
      margin-top: 0.55rem;
    }

    .telegram-callout {
      grid-template-columns: 1fr;
    }

    .how-it-works {
      padding: 2rem 1rem;
    }

    .steps {
      grid-template-columns: 1fr;
    }
  }

  @media (min-width: 560px) and (max-width: 820px) {
    .films-page {
      align-items: center;
    }

    .hero {
      grid-template-columns: minmax(0, 1fr) 13.5rem;
      gap: 1rem;
    }

    h1 {
      max-width: 16ch;
      font-size: clamp(1.44rem, 4.25vw, 1.84rem);
    }

    .lead {
      max-width: 30rem;
      font-size: 0.9rem;
    }

    .film-stack {
      height: min(28svh, 10.5rem);
    }
  }
</style>
