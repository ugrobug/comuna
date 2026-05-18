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
    ? `${subscription.completed_count} из 1001`
    : '0 из 1001'
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
  <title>1001 фильм, который должен посмотреть каждый</title>
  <meta
    name="description"
    content="Спецпроект Tambur: один фильм в день, секретные ссылки и общий порядок для всех участников."
  />
  <link rel="canonical" href="/s/1001-films" />
</svelte:head>

<LoginModal bind:open={authOpen} initialMode="signup" />

<section class="films-page">
  <div class="hero-shapes" aria-hidden="true">
    <span></span>
    <span></span>
    <span></span>
  </div>
  <div class="hero">
    <div class="hero-copy">
      <h1>1001 фильм, который должен посмотреть каждый</h1>
      <p class="lead">
        Каждый день вы получаете один фильм, только посмотрев и оценив его вы переходите
        к следующему, пропускать нельзя, выбирать нельзя — погрузиться в мир разных жанров,
        культур и эпох — нужно!
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
          <Button size="lg" href="/s/1001-films/admin">
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
        <h3>Стартуете подписку</h3>
        <p>Нужно зарегистрироваться и подключить телеграм бота, чтобы мы могли отправлять вам новые фильмы. Это бесплатно.</p>
      </article>
      <article class="step">
        <span class="step-icon">
          <Icon src={CalendarDays} size="18" mini />
        </span>
        <h3>Получаете фильм дня</h3>
        <p>Раз в сутки приходит информация, какой фильм вам нужно посмотреть, и краткое описание. Вы смотрите этот фильм.</p>
      </article>
      <article class="step">
        <span class="step-icon">
          <Icon src={CheckCircle} size="18" mini />
        </span>
        <h3>Оцениваете и комментируете</h3>
        <p>
          Вы ставите оценку фильму, комментируете, читаете мнение сообщества,
          обсуждаете и после этого на следующий день получите ссылку на новый.
        </p>
      </article>
    </div>

    <div class="rules">
      <p>
        Если фильм завис без реакции, через пару дней придёт напоминание, потом ещё одно.
        После этого подписка ставится на паузу. Вернуться можно в любой момент: проект продолжит
        с того места, где вы остановились.
      </p>
    </div>

    <div class="faq" aria-label="Частые вопросы">
      <details>
        <summary>Я могу посмотреть фильм у вас на сайте?</summary>
        <p>
          Нет, мы только предоставляем сервис выдающий вам список фильмов для просмотра.
          Мы не даем сами фильмы, но они без проблем доступны в интернете.
        </p>
      </details>
      <details>
        <summary>Это бесплатно?</summary>
        <p>Да, сервис полностью бесплатен и не содержит никаких рекламных элементов.</p>
      </details>
      <details>
        <summary>У меня займет посмотреть все фильмы около 2,5 лет?</summary>
        <p>
          Да, это большое кинопутешествие, но вы можете делать паузы и возвращаться к нему
          когда будет настроение.
        </p>
      </details>
      <details>
        <summary>Какие фильмы я смогу увидеть в списке?</summary>
        <p>
          Критики подобрали фильмы абсолютно разных жанров, эпох и школ. Мы постарались собрать
          список, чтобы он не пересекался с известными топами, то есть тут будут преимущественно
          другие фильмы, но более интересные!
        </p>
      </details>
      <details>
        <summary>Зачем мне этот список?</summary>
        <p>
          Это интересный опыт, когда вы не выбираете фильм совсем, только выбираете смотреть его
          сегодня или нет. А наш призыв дать комментарий про фильм в конце дает вам ощущение более
          вдумчивого просмотра. Этот список для любителей кино и возможность погрузиться в
          увлекательное путешествие.
        </p>
      </details>
    </div>
  </div>
</section>

<style>
  .films-page {
    --play-ink: #19130f;
    --play-red: #d83a2f;
    --play-yellow: #f8c847;
    --play-cream: #fff2cf;
    --play-mint: #39b7a5;
    --play-blue: #2578bd;
    --play-shadow: #060606;

    position: relative;
    overflow: hidden;
    min-height: auto;
    margin-top: -1rem;
    background:
      radial-gradient(circle at 1rem 1rem, rgb(25 19 15 / 0.12) 0 0.08rem, transparent 0.1rem) 0 0 / 1rem 1rem,
      linear-gradient(112deg, rgb(216 58 47 / 0.16) 0 10rem, transparent 10rem 100%),
      linear-gradient(246deg, rgb(57 183 165 / 0.2) 0 15rem, transparent 15rem 100%),
      linear-gradient(90deg, rgb(25 19 15 / 0.06) 1px, transparent 1px) 0 0 / 3.5rem 100%,
      linear-gradient(135deg, #fff2cf 0, #fff8e6 48%, #dff6f0 100%);
    color: var(--play-ink);
    padding: clamp(0.75rem, 1.8vw, 1.35rem) clamp(1rem, 4vw, 3rem) 10px;
    display: flex;
    align-items: flex-start;
  }

  .films-page::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
      linear-gradient(rgb(255 255 255 / 0.18), transparent 0.18rem) 0 0 / 100% 0.46rem,
      radial-gradient(circle, rgb(25 19 15 / 0.12) 0 0.05rem, transparent 0.07rem) 0.2rem 0.3rem / 0.8rem 0.8rem;
    mix-blend-mode: multiply;
    opacity: 0.32;
  }

  .hero-shapes {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .hero-shapes span {
    position: absolute;
    border: 3px solid var(--play-shadow);
    border-radius: 8px;
    opacity: 0.95;
  }

  .hero-shapes span:nth-child(1) {
    width: 10rem;
    height: 1.25rem;
    left: max(1rem, calc(50% - 34rem));
    top: 1.1rem;
    background: repeating-linear-gradient(90deg, var(--play-red) 0 0.9rem, var(--play-cream) 0.9rem 1.3rem);
    box-shadow: 0.34rem 0.34rem 0 var(--play-shadow);
    transform: rotate(-6deg);
  }

  .hero-shapes span:nth-child(2) {
    width: 7.25rem;
    height: 7.25rem;
    right: max(0.5rem, calc(50% - 38rem));
    bottom: -3.2rem;
    border-width: 0.95rem;
    background:
      radial-gradient(circle, rgb(25 19 15 / 0.18) 0 0.12rem, transparent 0.14rem) 0 0 / 0.8rem 0.8rem,
      var(--play-yellow);
    box-shadow: -0.36rem 0.36rem 0 var(--play-shadow);
    transform: rotate(14deg);
  }

  .hero-shapes span:nth-child(3) {
    width: 10rem;
    height: 1.25rem;
    right: max(2rem, calc(50% - 33rem));
    top: 2.7rem;
    background: linear-gradient(90deg, var(--play-mint), var(--play-yellow), var(--play-blue), var(--play-red));
    box-shadow: 0.34rem 0.34rem 0 var(--play-shadow);
    transform: rotate(8deg);
  }

  .hero {
    position: relative;
    z-index: 1;
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
    font-weight: 800;
    color: var(--play-ink);
    text-shadow:
      0.05em 0.05em 0 var(--play-yellow),
      0.1em 0.1em 0 rgb(216 58 47 / 0.85);
  }

  .lead {
    max-width: 42rem;
    color: #4a3426;
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
    border: 3px solid var(--play-shadow);
    border-radius: 8px;
    background: #dff6f0;
    padding: 0.85rem;
    box-shadow: 0.34rem 0.34rem 0 var(--play-shadow);
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
    position: relative;
    overflow: hidden;
    border: 4px solid var(--play-shadow);
    border-radius: 8px;
    background:
      radial-gradient(circle, rgb(25 19 15 / 0.12) 0 0.08rem, transparent 0.1rem) 0.2rem 0.2rem / 0.78rem 0.78rem,
      linear-gradient(135deg, rgb(255 242 207 / 0.96), rgb(255 248 230 / 0.88)),
      linear-gradient(135deg, rgb(216 58 47 / 0.18), rgb(248 200 71 / 0.22) 45%, rgb(57 183 165 / 0.2));
    padding: 1rem;
    box-shadow:
      0.55rem 0.55rem 0 var(--play-shadow),
      0 22px 58px rgb(15 23 42 / 0.14);
    backdrop-filter: blur(18px);
  }

  .project-panel::before {
    content: "";
    position: absolute;
    inset: 0 0 auto;
    height: 0.62rem;
    background: repeating-linear-gradient(
      90deg,
      var(--play-red) 0 1.1rem,
      var(--play-yellow) 1.1rem 2.2rem,
      var(--play-mint) 2.2rem 3.3rem,
      var(--play-blue) 3.3rem 4.4rem
    );
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
    border: 4px solid var(--play-shadow);
    background:
      radial-gradient(circle, #fff8e6 0 0.14rem, transparent 0.16rem) 0.46rem 0.46rem / 1rem 1rem repeat-y,
      radial-gradient(circle, #fff8e6 0 0.14rem, transparent 0.16rem) calc(100% - 0.46rem) 0.46rem / 1rem 1rem repeat-y,
      linear-gradient(90deg, rgb(25 19 15 / 0.24) 0 12%, transparent 12% 88%, rgb(25 19 15 / 0.24) 88%),
      linear-gradient(145deg, var(--play-yellow), #fff8e6 48%, #bfeee6);
    box-shadow: 0.4rem 0.4rem 0 var(--play-shadow);
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
      radial-gradient(circle, #fff8e6 0 0.14rem, transparent 0.16rem) 0.46rem 0.46rem / 1rem 1rem repeat-y,
      radial-gradient(circle, #fff8e6 0 0.14rem, transparent 0.16rem) calc(100% - 0.46rem) 0.46rem / 1rem 1rem repeat-y,
      linear-gradient(90deg, rgb(25 19 15 / 0.26) 0 10%, transparent 10% 90%, rgb(25 19 15 / 0.26) 90%),
      linear-gradient(150deg, #fff2cf, rgb(37 120 189 / 0.26) 46%, rgb(216 58 47 / 0.24) 74%, #dff6f0);
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

  .film-stack span.has-image::after {
    content: "";
    position: absolute;
    inset: 0;
    background:
      radial-gradient(circle, rgb(255 242 207 / 0.38) 0 0.07rem, transparent 0.09rem) 0.3rem 0.3rem / 0.72rem 0.72rem,
      linear-gradient(90deg, rgb(25 19 15 / 0.38) 0 10%, transparent 10% 90%, rgb(25 19 15 / 0.38) 90%),
      linear-gradient(180deg, transparent 55%, rgb(25 19 15 / 0.32));
    pointer-events: none;
  }

  .panel-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.6rem;
  }

  .panel-grid div {
    border-radius: 8px;
    background: #fff8e6;
    border: 3px solid var(--play-shadow);
    padding: 0.7rem;
    box-shadow: 0.25rem 0.25rem 0 var(--play-shadow);
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
    font-weight: 800;
    color: var(--play-red);
  }

  .status-line {
    margin-top: 0.75rem;
    line-height: 1.45;
  }

  .how-it-works {
    --play-ink: #19130f;
    --play-red: #d83a2f;
    --play-yellow: #f8c847;
    --play-cream: #fff2cf;
    --play-mint: #39b7a5;
    --play-blue: #2578bd;
    --play-shadow: #060606;

    background:
      radial-gradient(circle at 0.5rem 0.5rem, rgb(25 19 15 / 0.11) 0 0.07rem, transparent 0.09rem) 0 0 / 0.95rem 0.95rem,
      linear-gradient(102deg, rgb(216 58 47 / 0.11) 0 8rem, transparent 8rem 100%),
      linear-gradient(258deg, rgb(37 120 189 / 0.12) 0 10rem, transparent 10rem 100%),
      linear-gradient(90deg, transparent 0 calc(100% - 1px), rgb(25 19 15 / 0.055) calc(100% - 1px)) 0 0 / 3.5rem 100%,
      linear-gradient(180deg, #fff8e6, #fff2cf);
    color: var(--play-ink);
    border-top: 4px solid var(--play-shadow);
    padding: clamp(0.65rem, 1.5vw, 1.2rem) clamp(1rem, 4vw, 3rem) clamp(2rem, 5vw, 4.5rem);
  }

  .how-inner {
    max-width: 70rem;
    margin: 0 auto;
  }

  .how-heading {
    max-width: 49rem;
    display: flex;
    flex-direction: column;
    gap: 0.8rem;
    border-left: 5px solid var(--play-red);
    border-image: linear-gradient(var(--play-red), var(--play-yellow), var(--play-mint)) 1;
    padding-left: 1rem;
  }

  .how-heading p,
  .step p,
  .rules p,
  .faq p {
    color: #4a3426;
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
    position: relative;
    overflow: hidden;
    border: 3px solid var(--play-shadow);
    border-radius: 8px;
    background: var(--play-cream);
    padding: 1rem;
    box-shadow: 0.36rem 0.36rem 0 var(--play-shadow);
  }

  .step::before {
    content: "";
    position: absolute;
    inset: 0 0 auto;
    height: 0.42rem;
    background: var(--play-blue);
  }

  .step:nth-child(1) {
    background: linear-gradient(160deg, #ffe1d6, #fff8e6 62%);
  }

  .step:nth-child(2) {
    background: linear-gradient(160deg, #dff6f0, #fff8e6 62%);
  }

  .step:nth-child(3) {
    background: linear-gradient(160deg, #ffef9c, #fff8e6 62%);
  }

  .step:nth-child(1)::before {
    background: var(--play-red);
  }

  .step:nth-child(3)::before {
    background: var(--play-yellow);
  }

  .step-icon {
    width: 2rem;
    height: 2rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    color: #fff8e6;
    background: var(--play-shadow);
    border: 2px solid var(--play-shadow);
    box-shadow: 0.18rem 0.18rem 0 var(--play-red);
    margin-bottom: 0.9rem;
  }

  .step:nth-child(1) .step-icon {
    color: #fecdd3;
  }

  .step:nth-child(2) .step-icon {
    color: #bfdbfe;
  }

  .step:nth-child(3) .step-icon {
    color: #fde68a;
  }

  .step h3 {
    font-size: 1.05rem;
    font-weight: 800;
    margin-bottom: 0.45rem;
    color: var(--play-ink);
  }

  .rules {
    margin-top: 0.85rem;
    border-radius: 8px;
    border: 3px solid var(--play-shadow);
    padding: 1rem;
    background:
      radial-gradient(circle, rgb(25 19 15 / 0.12) 0 0.08rem, transparent 0.1rem) 0.22rem 0.28rem / 0.78rem 0.78rem,
      linear-gradient(135deg, #dff6f0, #fff8e6);
    box-shadow: 0.36rem 0.36rem 0 var(--play-shadow);
  }

  .faq {
    margin-top: 1rem;
    display: grid;
    gap: 0.6rem;
  }

  .faq details {
    border: 3px solid var(--play-shadow);
    border-radius: 8px;
    background: #fff8e6;
    padding: 0.9rem 1rem;
    box-shadow: 0.3rem 0.3rem 0 var(--play-shadow);
  }

  .faq details:nth-child(3n + 1) {
    background: #ffe1d6;
  }

  .faq details:nth-child(3n + 2) {
    background: #dff6f0;
  }

  .faq details:nth-child(3n + 3) {
    background: #ffef9c;
  }

  .faq details[open] {
    border-color: var(--play-shadow);
    background: #fff8e6;
  }

  .faq summary {
    cursor: pointer;
    color: var(--play-ink);
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.35;
  }

  .faq summary::marker {
    color: var(--play-red);
  }

  .faq p {
    margin-top: 0.65rem;
  }

  :global(.dark) .films-page {
    background:
      linear-gradient(115deg, rgb(225 29 72 / 0.12) 0 10rem, transparent 10rem 100%),
      linear-gradient(245deg, rgb(250 204 21 / 0.08) 0 14rem, transparent 14rem 100%),
      linear-gradient(90deg, rgb(255 255 255 / 0.035) 1px, transparent 1px) 0 0 / 3.5rem 100%,
      rgb(9 9 11 / 1);
    color: #fafafa;
  }

  :global(.dark) h1 {
    color: #fff8e6;
    text-shadow:
      0.05em 0.05em 0 rgb(248 200 71 / 0.75),
      0.1em 0.1em 0 rgb(216 58 47 / 0.7);
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
    border-color: #fff8e6;
    background:
      linear-gradient(135deg, rgb(24 24 27 / 0.94), rgb(9 9 11 / 0.85)),
      linear-gradient(135deg, rgb(225 29 72 / 0.26), rgb(250 204 21 / 0.14) 45%, rgb(16 185 129 / 0.18));
    box-shadow:
      0.5rem 0.5rem 0 rgb(255 248 230 / 0.55),
      0 18px 48px rgb(0 0 0 / 0.24);
  }

  :global(.dark) .panel-grid div {
    border-color: #fff8e6;
    background: rgb(24 24 27);
    box-shadow: 0.25rem 0.25rem 0 rgb(255 248 230 / 0.4);
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
    background:
      linear-gradient(102deg, rgb(225 29 72 / 0.1) 0 8rem, transparent 8rem 100%),
      linear-gradient(258deg, rgb(16 185 129 / 0.08) 0 10rem, transparent 10rem 100%),
      linear-gradient(90deg, transparent 0 calc(100% - 1px), rgb(255 255 255 / 0.035) calc(100% - 1px)) 0 0 / 3.5rem 100%,
      rgb(9 9 11);
    color: #fafafa;
    border-top-color: rgb(39 39 42);
  }

  :global(.dark) .step {
    border-color: #fff8e6;
    background: linear-gradient(160deg, rgb(39 39 42), rgb(24 24 27));
    box-shadow: 0.34rem 0.34rem 0 rgb(255 248 230 / 0.34);
  }

  :global(.dark) .step h3 {
    color: #fff8e6;
  }

  :global(.dark) .step-icon {
    background: rgb(9 9 11);
  }

  :global(.dark) .rules {
    border-color: #fff8e6;
    background: linear-gradient(135deg, rgb(20 83 45 / 0.24), rgb(30 64 175 / 0.18));
    box-shadow: 0.34rem 0.34rem 0 rgb(255 248 230 / 0.34);
  }

  :global(.dark) .faq details {
    border-color: #fff8e6;
    background: rgb(24 24 27);
    box-shadow: 0.28rem 0.28rem 0 rgb(255 248 230 / 0.3);
  }

  :global(.dark) .faq details[open] {
    border-color: rgb(147 197 253 / 0.34);
    background: rgb(9 9 11);
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
      padding: 1.35rem 1rem 1.5rem;
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

    .how-heading {
      padding-left: 0.8rem;
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
