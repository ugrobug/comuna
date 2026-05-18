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
  $: heroImage = landingImages.find((image) => image.image_url) ?? landingImages[0]

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

  <div class="landing-shell">
    <div class="screen-card">
      <div class="screen-glass">
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
          <div class="editorial-visual" class:has-image={Boolean(heroImage?.image_url)}>
            {#if heroImage?.image_url}
              <img src={heroImage.image_url} alt={heroImage.title || 'Кадр из фильма'} loading="lazy" />
            {:else}
              <div class="visual-placeholder" aria-hidden="true"></div>
            {/if}
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
    </div>

    <div class="program-grid">
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
  </div>
</section>

<style>
  .films-page {
    --retro-ink: #2b1830;
    --retro-wine: #6f1e32;
    --retro-red: #d73b2f;
    --retro-orange: #f4a91f;
    --retro-gold: #e9c767;
    --retro-paper: #efe2b8;
    --retro-paper-dark: #d5bd79;
    --retro-cream: #fff5cf;
    --retro-night: #090b25;
    --retro-blue: #2f46c8;
    --retro-cyan: #35d4df;
    --retro-line: rgb(43 24 48 / 0.16);
    --btn-primary-background: #f4a91f;
    --btn-primary-background-hover: #ffc13d;
    --btn-primary-color: #27132b;
    --btn-primary-shadow: 0 0.4rem 0 #8c3b19;
    --btn-primary-shadow-hover: 0 0.5rem 0 #8c3b19;

    position: relative;
    overflow: hidden;
    margin-top: -1rem;
    background:
      radial-gradient(circle at 12% 8%, rgb(215 59 47 / 0.2), transparent 16rem),
      radial-gradient(circle at 90% 10%, rgb(47 70 200 / 0.18), transparent 18rem),
      linear-gradient(90deg, rgb(43 24 48 / 0.055) 1px, transparent 1px) 0 0 / 2rem 2rem,
      linear-gradient(0deg, rgb(43 24 48 / 0.04) 1px, transparent 1px) 0 0 / 2rem 2rem,
      linear-gradient(180deg, #efd17b 0, #f4e4b5 32%, #e6c66a 100%);
    color: var(--retro-ink);
    padding: 1.35rem 1rem 3rem;
  }

  .films-page::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    background:
      radial-gradient(circle, rgb(43 24 48 / 0.14) 0 0.04rem, transparent 0.055rem) 0.4rem 0.2rem / 1.1rem 1.1rem,
      linear-gradient(90deg, transparent, rgb(255 255 255 / 0.26), transparent);
    mix-blend-mode: multiply;
    opacity: 0.22;
  }

  .hero-shapes {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .hero-shapes span {
    position: absolute;
    pointer-events: none;
  }

  .hero-shapes span:nth-child(1) {
    width: 31rem;
    height: 31rem;
    right: max(-11rem, calc(50% - 45rem));
    top: -12rem;
    border: 1.2rem solid rgb(111 30 50 / 0.14);
    border-radius: 999px;
    background:
      radial-gradient(circle, transparent 0 62%, rgb(47 70 200 / 0.14) 63% 64%, transparent 65%);
  }

  .hero-shapes span:nth-child(2) {
    width: 14rem;
    height: 1.2rem;
    left: max(1rem, calc(50% - 38rem));
    top: 8rem;
    border-radius: 999px;
    background: var(--retro-red);
    box-shadow:
      2rem 2.1rem 0 -0.25rem var(--retro-orange),
      4.5rem 4.2rem 0 -0.32rem var(--retro-cyan);
    transform: rotate(-9deg);
  }

  .hero-shapes span:nth-child(3) {
    width: 0.85rem;
    height: 0.85rem;
    right: max(3rem, calc(50% - 28rem));
    top: 11rem;
    background: var(--retro-orange);
    box-shadow:
      8rem 7rem 0 -0.12rem var(--retro-cyan),
      -14rem 11rem 0 -0.18rem var(--retro-red),
      20rem 18rem 0 -0.1rem var(--retro-orange);
    transform: rotate(45deg);
  }

  .landing-shell {
    position: relative;
    z-index: 1;
    max-width: 72rem;
    width: 100%;
    margin: 0 auto;
  }

  .screen-card {
    position: relative;
    overflow: hidden;
    border: 0.22rem solid var(--retro-red);
    background:
      linear-gradient(135deg, #202022, #090909 58%, #2d2c2b);
    padding: 1.6rem;
    box-shadow:
      0 1.2rem 2.8rem rgb(43 24 48 / 0.25),
      inset 0 0 0 0.14rem #111;
  }

  .screen-card::before {
    content: "";
    position: absolute;
    inset: 0.65rem;
    border: 0.55rem solid #141414;
    border-radius: 2.4rem;
    pointer-events: none;
    z-index: 3;
    box-shadow:
      inset 0 0 0 0.18rem #303030,
      inset 0 0 2.5rem rgb(0 0 0 / 0.85);
  }

  .screen-glass {
    position: relative;
    overflow: hidden;
    min-height: 30rem;
    display: grid;
    grid-template-columns: minmax(0, 1.18fr) minmax(17rem, 23rem);
    gap: 1.3rem;
    align-items: stretch;
    border-radius: 2rem;
    padding: 2.6rem;
    background:
      radial-gradient(circle at 73% 37%, rgb(53 212 223 / 0.35), transparent 11rem),
      radial-gradient(circle at 48% 65%, rgb(215 59 47 / 0.48), transparent 13rem),
      linear-gradient(135deg, #0d1034 0, #151357 52%, #07081d 100%);
    color: var(--retro-cream);
    box-shadow: inset 0 0 3rem rgb(0 0 0 / 0.74);
  }

  .screen-glass::before,
  .screen-glass::after {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .screen-glass::before {
    background:
      repeating-linear-gradient(0deg, rgb(255 255 255 / 0.08) 0 1px, transparent 1px 4px),
      radial-gradient(ellipse at 50% 40%, transparent 0 44%, rgb(0 0 0 / 0.35) 74%);
    z-index: 2;
  }

  .screen-glass::after {
    background: linear-gradient(110deg, transparent 0 36%, rgb(255 255 255 / 0.14) 43%, transparent 54%);
    opacity: 0.6;
    z-index: 2;
  }

  .hero-copy {
    position: relative;
    z-index: 4;
    display: flex;
    flex-direction: column;
    justify-content: center;
    gap: 1rem;
    min-width: 0;
  }

  h1 {
    max-width: 14ch;
    font-family: Impact, Haettenschweiler, "Arial Narrow Bold", sans-serif;
    font-size: 5rem;
    line-height: 0.88;
    letter-spacing: 0;
    font-weight: 900;
    text-transform: uppercase;
    color: #f0c16b;
    text-shadow:
      0.045em 0.045em 0 rgb(215 59 47 / 0.78),
      0.09em 0.09em 0 rgb(24 140 197 / 0.58),
      0.13em 0.13em 0 rgb(0 0 0 / 0.38);
  }

  .lead {
    max-width: 38rem;
    color: var(--retro-cream);
    font-size: 1.02rem;
    line-height: 1.5;
    text-shadow: 0 0.08rem 0 rgb(0 0 0 / 0.3);
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    margin-top: 0.25rem;
  }

  .error {
    color: #ffd479;
  }

  .notification-note {
    max-width: 35rem;
    color: rgb(255 245 207 / 0.75);
    font-size: 0.92rem;
    line-height: 1.45;
  }

  .telegram-callout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(16rem, 20rem);
    gap: 0.8rem;
    align-items: center;
    max-width: 42rem;
    border: 1px solid rgb(255 245 207 / 0.26);
    border-radius: 0.9rem;
    background: rgb(9 11 37 / 0.76);
    padding: 0.85rem;
    box-shadow: inset 0 0 0 1px rgb(53 212 223 / 0.12);
    backdrop-filter: blur(16px);
  }

  .telegram-callout strong {
    display: block;
    margin-bottom: 0.25rem;
    font-weight: 500;
    color: var(--retro-cream);
  }

  .telegram-callout p {
    color: rgb(255 245 207 / 0.74);
    font-size: 0.9rem;
    line-height: 1.45;
  }

  .project-panel {
    position: relative;
    z-index: 4;
    overflow: hidden;
    align-self: center;
    border: 1px solid rgb(255 245 207 / 0.24);
    border-radius: 1rem;
    background:
      linear-gradient(180deg, rgb(255 245 207 / 0.13), transparent),
      rgb(9 11 37 / 0.72);
    padding: 0.68rem;
    box-shadow:
      0 1rem 2rem rgb(0 0 0 / 0.32),
      inset 0 0 0 1px rgb(255 245 207 / 0.08);
  }

  .project-panel::before {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent 0 49%, rgb(255 245 207 / 0.08) 49% 51%, transparent 51%);
    opacity: 0.35;
    pointer-events: none;
  }

  .editorial-visual {
    position: relative;
    min-height: 19rem;
    margin-bottom: 0.72rem;
    overflow: hidden;
    border-radius: 0.72rem;
    border: 0.18rem solid #0b0b16;
    background:
      radial-gradient(circle at 68% 34%, #f5e09a 0 3.8rem, transparent 3.9rem),
      radial-gradient(circle at 30% 70%, rgb(215 59 47 / 0.72), transparent 8rem),
      linear-gradient(145deg, #101451, #07081d 68%);
    box-shadow: 0 0.7rem 0 rgb(0 0 0 / 0.28);
  }

  .editorial-visual::before,
  .editorial-visual::after {
    content: "";
    position: absolute;
    pointer-events: none;
    z-index: 2;
  }

  .editorial-visual::before {
    inset: 0.8rem;
    border: 1px solid rgb(255 245 207 / 0.26);
    border-radius: 0.5rem;
  }

  .editorial-visual::after {
    inset: 0;
    background:
      repeating-linear-gradient(0deg, rgb(255 255 255 / 0.11) 0 1px, transparent 1px 4px),
      linear-gradient(180deg, transparent 46%, rgb(9 11 37 / 0.52));
  }

  .editorial-visual.has-image {
    background: #07081d;
  }

  .editorial-visual img {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: cover;
    filter: saturate(1.18) contrast(1.08) sepia(0.12);
  }

  .visual-placeholder {
    position: absolute;
    inset: 0;
    background:
      conic-gradient(from 34deg at 48% 105%, rgb(215 59 47 / 0.95), rgb(244 169 31 / 0.9), transparent 24deg 336deg, rgb(215 59 47 / 0.95)),
      radial-gradient(circle at 70% 28%, #f5e09a 0 3.7rem, transparent 3.8rem),
      linear-gradient(145deg, #111657, #07081d 68%);
  }

  .visual-placeholder::before {
    content: "";
    position: absolute;
    left: 18%;
    top: 18%;
    width: 46%;
    aspect-ratio: 0.62;
    border: 0.18rem solid #050617;
    border-radius: 0.45rem;
    transform: rotate(-8deg);
    background:
      linear-gradient(180deg, #d73b2f 0 18%, transparent 18%),
      radial-gradient(circle at 52% 54%, #35d4df 0 2.1rem, transparent 2.2rem),
      linear-gradient(135deg, #f6e1ad, #101451 54%, #07081d);
    box-shadow:
      7rem 1.2rem 0 -0.65rem #f6e1ad,
      7.4rem 1.55rem 0 -0.65rem #050617;
  }

  .visual-placeholder::after {
    content: "";
    position: absolute;
    left: 22%;
    bottom: 15%;
    width: 58%;
    height: 0.62rem;
    border-radius: 999px;
    background: #35d4df;
    box-shadow:
      1.4rem 1rem 0 #d73b2f,
      4.2rem -1.1rem 0 -0.12rem #f4a91f;
    transform: rotate(-5deg);
  }

  .panel-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 0.55rem;
  }

  .panel-grid div {
    border-radius: 0.72rem;
    background: var(--retro-orange);
    border: 1px solid rgb(255 245 207 / 0.28);
    padding: 0.7rem 0.8rem;
    color: #27132b;
  }

  .panel-grid span,
  .status-line {
    color: rgb(255 245 207 / 0.72);
    font-size: 0.9rem;
  }

  .panel-grid span {
    color: rgb(39 19 43 / 0.72);
    text-transform: uppercase;
    font-size: 0.72rem;
    font-weight: 800;
  }

  .panel-grid strong {
    display: block;
    margin-top: 0.18rem;
    font-size: 1.45rem;
    font-family: Impact, Haettenschweiler, "Arial Narrow Bold", sans-serif;
    font-weight: 900;
    color: #27132b;
    letter-spacing: 0;
  }

  .status-line {
    margin-top: 0.75rem;
    line-height: 1.45;
  }

  .program-grid {
    position: relative;
    display: grid;
    grid-template-columns: minmax(16rem, 0.9fr) minmax(0, 1.4fr);
    gap: 1rem;
    padding: 2.2rem 2.4rem 2.6rem;
    border-inline: 0.22rem solid rgb(111 30 50 / 0.18);
    background:
      radial-gradient(circle at 10% 28%, rgb(215 59 47 / 0.1), transparent 13rem),
      linear-gradient(90deg, rgb(43 24 48 / 0.07) 1px, transparent 1px) 0 0 / 1.5rem 1.5rem,
      linear-gradient(0deg, rgb(43 24 48 / 0.055) 1px, transparent 1px) 0 0 / 1.5rem 1.5rem,
      linear-gradient(180deg, #f7edcf, #ebd493);
    box-shadow: 0 1rem 2.5rem rgb(43 24 48 / 0.16);
  }

  .how-heading {
    position: sticky;
    top: 1rem;
    align-self: start;
    border-top: 0.42rem solid var(--retro-red);
    background:
      linear-gradient(180deg, rgb(255 245 207 / 0.78), rgb(255 245 207 / 0.54));
    padding: 1.15rem 1.2rem;
    box-shadow: 0 0.5rem 0 rgb(43 24 48 / 0.08);
  }

  .how-heading p,
  .step p,
  .rules p,
  .faq p {
    color: var(--retro-ink);
    line-height: 1.48;
  }

  .how-heading a {
    color: #0c73a2;
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 0.16em;
    text-decoration-color: rgb(215 59 47 / 0.64);
  }

  .steps {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.9rem;
    grid-column: 2;
  }

  .step {
    position: relative;
    overflow: hidden;
    min-height: 13.8rem;
    border: 0.16rem solid var(--retro-ink);
    border-radius: 0.35rem;
    background: var(--retro-cream);
    padding: 1rem;
    box-shadow: 0.45rem 0.45rem 0 rgb(43 24 48 / 0.13);
  }

  .step::before {
    content: "";
    position: absolute;
    inset: 0 0 auto;
    height: 0.42rem;
    background: var(--retro-red);
  }

  .step:nth-child(1) {
    background:
      radial-gradient(circle at 95% 8%, rgb(215 59 47 / 0.18), transparent 5rem),
      var(--retro-cream);
  }

  .step:nth-child(2) {
    background:
      radial-gradient(circle at 92% 10%, rgb(53 212 223 / 0.2), transparent 5rem),
      var(--retro-cream);
  }

  .step:nth-child(3) {
    background:
      radial-gradient(circle at 92% 10%, rgb(244 169 31 / 0.22), transparent 5rem),
      var(--retro-cream);
  }

  .step:nth-child(1)::before {
    background: linear-gradient(90deg, var(--retro-orange), transparent);
  }

  .step:nth-child(3)::before {
    background: var(--retro-orange);
  }

  .step-icon {
    width: 2rem;
    height: 2rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 999px;
    color: var(--retro-ink);
    background: var(--retro-gold);
    border: 0.14rem solid var(--retro-ink);
    margin-bottom: 0.9rem;
  }

  .step:nth-child(1) .step-icon {
    color: var(--retro-cream);
    background: var(--retro-red);
  }

  .step:nth-child(2) .step-icon {
    color: var(--retro-ink);
    background: #26d7d0;
  }

  .step:nth-child(3) .step-icon {
    color: #101044;
  }

  .step h3 {
    font-size: 1.05rem;
    font-family: Impact, Haettenschweiler, "Arial Narrow Bold", sans-serif;
    font-weight: 900;
    margin-bottom: 0.45rem;
    color: var(--retro-wine);
    letter-spacing: 0;
    text-transform: uppercase;
  }

  .rules {
    grid-column: 2;
    border-radius: 0.35rem;
    border: 0.16rem solid var(--retro-ink);
    padding: 1.05rem 1.2rem;
    background:
      linear-gradient(90deg, rgb(215 59 47 / 0.16), transparent),
      var(--retro-cream);
    box-shadow: 0.45rem 0.45rem 0 rgb(43 24 48 / 0.13);
  }

  .faq {
    grid-column: 1 / -1;
    margin-top: 0.35rem;
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 0.75rem;
    align-items: start;
  }

  .faq details {
    border: 0.14rem solid var(--retro-ink);
    border-radius: 0.35rem;
    background: var(--retro-cream);
    padding: 0.9rem 1rem;
    box-shadow: 0.35rem 0.35rem 0 rgb(43 24 48 / 0.12);
  }

  .faq details:nth-child(3n + 1) {
    background: linear-gradient(180deg, rgb(215 59 47 / 0.16), var(--retro-cream) 34%);
  }

  .faq details:nth-child(3n + 2) {
    background: linear-gradient(180deg, rgb(53 212 223 / 0.16), var(--retro-cream) 34%);
  }

  .faq details:nth-child(3n + 3) {
    background: linear-gradient(180deg, rgb(244 169 31 / 0.18), var(--retro-cream) 34%);
  }

  .faq details[open] {
    border-color: var(--retro-red);
    background: #fff1bd;
  }

  .faq summary {
    cursor: pointer;
    color: var(--retro-wine);
    font-size: 1rem;
    font-family: Impact, Haettenschweiler, "Arial Narrow Bold", sans-serif;
    font-weight: 900;
    line-height: 1.35;
    letter-spacing: 0;
    text-transform: uppercase;
  }

  .faq summary::marker {
    color: var(--retro-red);
  }

  .faq p {
    margin-top: 0.65rem;
  }

  @media (max-width: 820px) {
    .films-page {
      padding: 1rem 0.75rem 2rem;
    }

    .screen-card {
      padding: 0.8rem;
      border-width: 0.16rem;
    }

    .screen-card::before {
      inset: 0.35rem;
      border-width: 0.3rem;
      border-radius: 1.3rem;
    }

    .screen-glass {
      grid-template-columns: 1fr;
      gap: 1rem;
      min-height: auto;
      border-radius: 1.05rem;
      padding: 1.45rem;
    }

    h1 {
      max-width: 16ch;
      font-size: 2.18rem;
      line-height: 0.98;
    }

    .lead {
      font-size: 0.94rem;
      line-height: 1.45;
    }

    .editorial-visual {
      min-height: 15rem;
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

    .program-grid {
      grid-template-columns: 1fr;
      padding: 1.25rem 0.9rem 1.6rem;
    }

    .how-heading {
      position: relative;
      top: auto;
    }

    .steps,
    .rules,
    .faq {
      grid-column: 1;
    }

    .steps,
    .faq {
      grid-template-columns: 1fr;
    }
  }

  @media (min-width: 560px) and (max-width: 820px) {
    .screen-glass {
      grid-template-columns: minmax(0, 1fr) 13.5rem;
      gap: 1rem;
    }

    h1 {
      max-width: 16ch;
      font-size: 1.95rem;
    }

    .lead {
      max-width: 30rem;
      font-size: 0.9rem;
    }

    .editorial-visual {
      min-height: 14rem;
    }

    .program-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
