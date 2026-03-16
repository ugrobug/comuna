<script lang="ts">
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import type { IconSource } from 'svelte-hero-icons'
  import {
    ArrowTrendingUp,
    ChatBubbleLeftRight,
    CheckCircle,
    ClipboardDocumentList,
    DocumentText,
    Icon,
    Megaphone,
    ShieldCheck,
    Sparkles,
    UserGroup,
  } from 'svelte-hero-icons'

  type LandingCard = {
    icon: IconSource
    eyebrow: string
    title: string
    text: string
  }

  const siteName = env.PUBLIC_SITE_TITLE || 'Comuna'
  const title = `Сообщества для авторов и редакций — ${siteName}`
  const description =
    'Запускайте сообщества в Comuna, задавайте правила публикации по тематикам, собирайте шаблоны постов и переводите аудиторию из Telegram в более сильный формат общения.'

  const pillars: LandingCard[] = [
    {
      icon: ClipboardDocumentList,
      eyebrow: 'Правила внутри тематик',
      title: 'У каждой рубрики свой сценарий публикации',
      text: 'Вы определяете, что именно должен заполнить автор: структуру, обязательные поля, формат заголовка, тональность и ограничения.',
    },
    {
      icon: Sparkles,
      eyebrow: 'Шаблоны постов',
      title: 'Повторяемые форматы превращаются в продукт',
      text: 'Подборки, рецензии, анонсы, разборы и AMA можно оформить как шаблоны, чтобы публикации выглядели стабильно и собирались быстрее.',
    },
    {
      icon: ShieldCheck,
      eyebrow: 'Управление качеством',
      title: 'Сообщество не расползается по стилю и теме',
      text: 'Правила и шаблоны снижают шум, уменьшают ручную модерацию и помогают новым авторам публиковаться без постоянных объяснений в личке.',
    },
    {
      icon: UserGroup,
      eyebrow: 'Не просто чат',
      title: 'Контент, обсуждение и подписка живут в одном месте',
      text: 'Люди не теряются в потоке сообщений: у каждой публикации есть собственная ссылка, обсуждение, реакция и место в архиве сообщества.',
    },
  ]

  const migrationWins: LandingCard[] = [
    {
      icon: Megaphone,
      eyebrow: 'Что сохраняется',
      title: 'Ощущение живого канала и прямого контакта',
      text: 'Вы по-прежнему общаетесь с ядром аудитории, запускаете обсуждения, публикуете важные апдейты и собираете обратную связь вокруг своей темы.',
    },
    {
      icon: DocumentText,
      eyebrow: 'Что добавляется',
      title: 'Нормальная структура вместо бесконечной ленты',
      text: 'Посты можно находить, перечитывать, обсуждать отдельно друг от друга и использовать как постоянно растущую базу знаний сообщества.',
    },
    {
      icon: ArrowTrendingUp,
      eyebrow: 'Что растет',
      title: 'Вовлечение без потери контроля',
      text: 'Подписчики начинают не только читать, но и публиковать по вашим правилам, а лучшие материалы усиливают сам бренд сообщества.',
    },
  ]

  const checklist = [
    'Создайте сообщество как самостоятельную площадку вокруг своей темы.',
    'Задайте правила публикации отдельно для разных тематик и форматов.',
    'Соберите библиотеку шаблонов, чтобы пользователи публиковали качественнее.',
    'Перетяните аудиторию из Telegram или чата и дайте ей больше способов участвовать.',
  ]

  const templateExamples = [
    'Рецензия: оценка, тезисы, сильные и слабые стороны, вывод.',
    'Подборка: критерии отбора, карточки объектов, рекомендации редакции.',
    'Разбор кейса: контекст, решение, результат, выводы для сообщества.',
  ]

  let signupModalOpen = false

  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>

<div class="landing-page">
  <section class="hero-section">
    <div class="hero-shell">
      <div class="hero-copy">
        <div class="eyebrow">Landing page / Сообщества</div>
        <h1>Сообщество, которое работает как сабреддит, а не как шумный чат</h1>
        <p class="hero-lead">
          В Comuna авторы создают сообщества, задают правила публикации по
          тематикам и собирают шаблоны постов, внутри которых участники выпускают
          статьи. В итоге вы ведете комьюнити не потоком сообщений, а
          управляемой контентной системой.
        </p>

        <div class="hero-actions">
          <a class="cta-primary" href="/comuns?create=1">Создать сообщество</a>
          <a class="cta-secondary" href="#telegram-migration">Перенести аудиторию из Telegram</a>
        </div>

        <ul class="hero-checklist">
          {#each checklist as item}
            <li>
              <Icon src={CheckCircle} size="18" />
              <span>{item}</span>
            </li>
          {/each}
        </ul>
      </div>

      <div class="hero-panel">
        <div class="panel-window">
          <div class="panel-window__top">
            <span>Комьюнити о кино и медиа</span>
            <span>Редакторский режим</span>
          </div>

          <div class="panel-stack">
            <div class="signal-card signal-card--accent">
              <div class="signal-card__icon">
                <Icon src={ClipboardDocumentList} size="18" />
              </div>
              <div>
                <strong>Тема: «Рецензии»</strong>
                <p>
                  Обязательные поля: оценка, аргументы, вывод, спойлер-метка,
                  рекомендации по заголовку.
                </p>
              </div>
            </div>

            <div class="signal-card">
              <div class="signal-card__icon">
                <Icon src={Sparkles} size="18" />
              </div>
              <div>
                <strong>Шаблон: «Разбор премьеры»</strong>
                <p>
                  Пользователь не начинает с пустого листа, а двигается по
                  понятной структуре публикации.
                </p>
              </div>
            </div>

            <div class="signal-card">
              <div class="signal-card__icon">
                <Icon src={ChatBubbleLeftRight} size="18" />
              </div>
              <div>
                <strong>Обсуждение под постом</strong>
                <p>
                  Комментарии и реакции живут рядом с публикацией, а не тонут в
                  ленте чата через десять минут.
                </p>
              </div>
            </div>
          </div>

          <div class="metric-row">
            <div>
              <span class="metric-label">Роль автора</span>
              <strong>ведет тему</strong>
            </div>
            <div>
              <span class="metric-label">Роль участника</span>
              <strong>публикует по шаблону</strong>
            </div>
            <div>
              <span class="metric-label">Результат</span>
              <strong>контент копится, а не исчезает</strong>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="content-section">
    <div class="section-shell">
      <div class="section-heading">
        <div class="eyebrow">Почему это сильнее обычного канала</div>
        <h2>Вы управляете не только обсуждением, но и качеством публикаций</h2>
        <p>
          Хорошее сообщество растет вокруг понятных правил. В Comuna они
          зашиваются в сам процесс публикации, а не висят отдельным постом,
          который никто не перечитывает.
        </p>
      </div>

      <div class="card-grid">
        {#each pillars as pillar}
          <article class="feature-card">
            <div class="feature-card__icon">
              <Icon src={pillar.icon} size="20" />
            </div>
            <div class="feature-card__eyebrow">{pillar.eyebrow}</div>
            <h3>{pillar.title}</h3>
            <p>{pillar.text}</p>
          </article>
        {/each}
      </div>
    </div>
  </section>

  <section class="content-section content-section--contrast">
    <div class="section-shell split-layout">
      <div class="section-heading section-heading--compact">
        <div class="eyebrow">Шаблоны публикаций</div>
        <h2>Повторяемые форматы перестают быть ручной работой</h2>
        <p>
          Если у вас есть статьи, которые выходят снова и снова, оформите их как
          шаблоны. Тогда пользователи будут делать меньше случайных ошибок, а
          редактура станет заметно легче.
        </p>
      </div>

      <div class="template-box">
        <div class="template-box__title">Примеры форматов внутри сообщества</div>
        <ul>
          {#each templateExamples as example}
            <li>{example}</li>
          {/each}
        </ul>
      </div>
    </div>
  </section>

  <section class="content-section" id="telegram-migration">
    <div class="section-shell">
      <div class="section-heading">
        <div class="eyebrow">Миграция из Telegram и чатов</div>
        <h2>Не теряйте аудиторию. Переведите ее в более сильный формат общения.</h2>
        <p>
          Можно не ломать привычку подписчиков читать вас регулярно. Вместо этого
          вы даете им пространство, где знакомая коммуникация сохраняется, но к
          ней добавляются нормальные публикации, комментарии, роли и архив.
        </p>
      </div>

      <div class="migration-grid">
        {#each migrationWins as item}
          <article class="migration-card">
            <div class="migration-card__head">
              <div class="migration-card__icon">
                <Icon src={item.icon} size="20" />
              </div>
              <div class="migration-card__eyebrow">{item.eyebrow}</div>
            </div>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </article>
        {/each}
      </div>

      <div class="comparison-band">
        <div>
          <span>В Telegram</span>
          <strong>контент быстро уходит вниз, а обсуждение смешивается с потоком</strong>
        </div>
        <div>
          <span>В Comuna</span>
          <strong>каждый материал получает свой дом, а комьюнити растет вокруг него</strong>
        </div>
      </div>
    </div>
  </section>

  <section class="cta-section">
    <div class="cta-shell">
      <div>
        <div class="eyebrow eyebrow--light">Для авторов, редакций и тематических лидеров</div>
        <h2>Если вы уже собрали ядро аудитории, пора дать ему нормальную платформу</h2>
        <p>
          Запускайте сообщество, задавайте правила по тематикам, собирайте
          шаблоны и переносите подписчиков в пространство, где контент можно не
          только читать, но и развивать вместе.
        </p>
      </div>

      <div class="cta-buttons">
        <a class="cta-primary cta-primary--light" href="/comuns?create=1">Запустить сообщество</a>
        <button
          type="button"
          class="cta-secondary cta-secondary--light"
          on:click={() => (signupModalOpen = true)}
        >
          Создать аккаунт
        </button>
      </div>
    </div>
  </section>

  <LoginModal bind:open={signupModalOpen} initialMode="signup" />
</div>

<style>
  .landing-page {
    --landing-bg: #f4efe4;
    --landing-paper: rgba(255, 255, 255, 0.84);
    --landing-ink: #172033;
    --landing-muted: rgba(23, 32, 51, 0.72);
    --landing-line: rgba(57, 76, 116, 0.14);
    --landing-accent: #d16032;
    --landing-accent-soft: rgba(209, 96, 50, 0.12);
    --landing-accent-dark: #173d8a;
    background:
      radial-gradient(circle at top left, rgba(209, 96, 50, 0.16), transparent 28%),
      radial-gradient(circle at 85% 12%, rgba(23, 61, 138, 0.16), transparent 24%),
      linear-gradient(180deg, #f8f3e9 0%, var(--landing-bg) 44%, #fbfaf7 100%);
    color: var(--landing-ink);
  }

  .hero-section,
  .content-section,
  .cta-section {
    position: relative;
    width: 100%;
  }

  .hero-shell,
  .section-shell,
  .cta-shell {
    width: min(1280px, calc(100% - 2rem));
    margin: 0 auto;
  }

  .hero-section {
    padding: 2rem 0 3rem;
  }

  .hero-shell {
    display: grid;
    gap: 1.5rem;
    align-items: stretch;
  }

  .hero-copy,
  .hero-panel,
  .feature-card,
  .template-box,
  .migration-card,
  .cta-shell {
    backdrop-filter: blur(16px);
  }

  .hero-copy {
    padding: 2rem;
    border: 1px solid var(--landing-line);
    border-radius: 2rem;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(255, 255, 255, 0.72));
    box-shadow: 0 20px 80px rgba(35, 44, 79, 0.08);
  }

  .hero-copy h1 {
    margin: 0.5rem 0 0;
    max-width: 12ch;
    font-size: clamp(2.5rem, 6vw, 5.4rem);
    line-height: 0.95 !important;
    font-weight: 500 !important;
    letter-spacing: -0.06em;
  }

  .hero-lead,
  .section-heading p,
  .feature-card p,
  .migration-card p,
  .cta-shell p {
    color: var(--landing-muted);
    font-size: 1.05rem;
    line-height: 1.65;
  }

  .eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.85rem;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.72);
    border: 1px solid var(--landing-line);
    color: var(--landing-accent-dark);
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .eyebrow--light {
    background: rgba(255, 255, 255, 0.12);
    border-color: rgba(255, 255, 255, 0.22);
    color: rgba(255, 255, 255, 0.86);
  }

  .hero-actions,
  .cta-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 0.875rem;
    margin-top: 1.75rem;
  }

  .cta-primary,
  .cta-secondary {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 3.25rem;
    padding: 0.85rem 1.35rem;
    border-radius: 999px;
    border: 1px solid transparent;
    font-weight: 500;
    text-decoration: none;
    transition:
      transform 0.2s ease,
      background-color 0.2s ease,
      border-color 0.2s ease,
      color 0.2s ease,
      box-shadow 0.2s ease;
  }

  .cta-primary {
    background: var(--landing-accent);
    color: #fff;
    box-shadow: 0 16px 40px rgba(209, 96, 50, 0.24);
  }

  .cta-primary:hover {
    transform: translateY(-1px);
    color: #fff;
    box-shadow: 0 22px 50px rgba(209, 96, 50, 0.32);
  }

  .cta-secondary {
    border-color: var(--landing-line);
    background: rgba(255, 255, 255, 0.56);
    color: var(--landing-ink);
  }

  .cta-secondary:hover {
    transform: translateY(-1px);
    color: var(--landing-ink);
    background: rgba(255, 255, 255, 0.78);
  }

  .cta-primary--light {
    background: #fff;
    color: var(--landing-accent-dark);
    box-shadow: none;
  }

  .cta-primary--light:hover {
    color: var(--landing-accent-dark);
    box-shadow: 0 16px 40px rgba(9, 18, 40, 0.22);
  }

  .cta-secondary--light {
    border-color: rgba(255, 255, 255, 0.22);
    background: rgba(255, 255, 255, 0.08);
    color: #fff;
  }

  .cta-secondary--light:hover {
    color: #fff;
    background: rgba(255, 255, 255, 0.14);
  }

  .hero-checklist {
    display: grid;
    gap: 0.85rem;
    margin: 1.75rem 0 0;
    padding: 0;
    list-style: none;
  }

  .hero-checklist li {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
    color: var(--landing-ink);
  }

  .hero-checklist :global(svg) {
    flex: none;
    color: var(--landing-accent);
    margin-top: 0.15rem;
  }

  .hero-panel {
    padding: 0.75rem;
    border-radius: 2rem;
    border: 1px solid rgba(22, 37, 70, 0.08);
    background:
      linear-gradient(180deg, rgba(17, 38, 80, 0.96), rgba(11, 20, 46, 0.96)),
      linear-gradient(135deg, rgba(255, 255, 255, 0.04), transparent);
    color: #f8fafc;
    box-shadow: 0 30px 80px rgba(11, 20, 46, 0.28);
  }

  .panel-window {
    height: 100%;
    padding: 1.5rem;
    border-radius: 1.5rem;
    border: 1px solid rgba(255, 255, 255, 0.08);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03));
  }

  .panel-window__top {
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    margin-bottom: 1.25rem;
    color: rgba(226, 232, 240, 0.72);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .panel-stack {
    display: grid;
    gap: 0.9rem;
  }

  .signal-card {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.85rem;
    padding: 1rem;
    border-radius: 1.25rem;
    border: 1px solid rgba(255, 255, 255, 0.09);
    background: rgba(255, 255, 255, 0.05);
  }

  .signal-card--accent {
    background: linear-gradient(135deg, rgba(209, 96, 50, 0.16), rgba(255, 255, 255, 0.05));
    border-color: rgba(255, 211, 194, 0.22);
  }

  .signal-card strong,
  .migration-card h3,
  .feature-card h3,
  .cta-shell h2,
  .section-heading h2,
  .template-box__title {
    display: block;
    margin: 0;
    font-weight: 500;
    letter-spacing: -0.03em;
  }

  .signal-card p {
    margin: 0.35rem 0 0;
    color: rgba(226, 232, 240, 0.76);
    line-height: 1.6;
  }

  .signal-card__icon,
  .feature-card__icon,
  .migration-card__icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 999px;
    flex: none;
  }

  .signal-card__icon {
    background: rgba(255, 255, 255, 0.08);
    color: #fff;
  }

  .feature-card__icon,
  .migration-card__icon {
    background: var(--landing-accent-soft);
    color: var(--landing-accent);
  }

  .metric-row {
    display: grid;
    gap: 0.9rem;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
  }

  .metric-row span {
    display: block;
    color: rgba(226, 232, 240, 0.62);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .metric-row strong {
    display: block;
    margin-top: 0.25rem;
    font-size: 1rem;
    font-weight: 500;
  }

  .content-section {
    padding: 1rem 0 3.5rem;
  }

  .content-section--contrast {
    padding-top: 0;
  }

  .section-shell {
    display: grid;
    gap: 1.5rem;
  }

  .section-heading {
    max-width: 52rem;
  }

  .section-heading h2,
  .cta-shell h2 {
    margin: 0.9rem 0 0;
    font-size: clamp(2rem, 4.5vw, 3.5rem);
    line-height: 1.02 !important;
  }

  .section-heading--compact h2 {
    max-width: 16ch;
  }

  .card-grid,
  .migration-grid {
    display: grid;
    gap: 1rem;
  }

  .feature-card,
  .template-box,
  .migration-card {
    padding: 1.5rem;
    border-radius: 1.6rem;
    border: 1px solid var(--landing-line);
    background: var(--landing-paper);
    box-shadow: 0 18px 60px rgba(35, 44, 79, 0.06);
  }

  .feature-card__eyebrow,
  .migration-card__eyebrow {
    margin-top: 1rem;
    color: var(--landing-accent-dark);
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .feature-card h3,
  .migration-card h3 {
    margin-top: 0.65rem;
    font-size: 1.45rem;
    line-height: 1.1 !important;
  }

  .split-layout {
    align-items: start;
  }

  .template-box {
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(255, 255, 255, 0.76)),
      linear-gradient(135deg, rgba(209, 96, 50, 0.08), transparent);
  }

  .template-box__title {
    font-size: 1.35rem;
    color: var(--landing-ink);
  }

  .template-box ul {
    display: grid;
    gap: 0.8rem;
    margin: 1rem 0 0;
    padding-left: 1.1rem;
    color: var(--landing-muted);
  }

  .migration-card__head {
    display: flex;
    align-items: center;
    gap: 0.85rem;
  }

  .comparison-band {
    display: grid;
    gap: 1rem;
    padding: 1.25rem;
    border-radius: 1.75rem;
    background: linear-gradient(135deg, rgba(23, 61, 138, 0.94), rgba(19, 30, 57, 0.94));
    color: #fff;
    box-shadow: 0 22px 60px rgba(20, 33, 67, 0.22);
  }

  .comparison-band span {
    display: block;
    color: rgba(255, 255, 255, 0.64);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .comparison-band strong {
    display: block;
    margin-top: 0.35rem;
    font-size: 1.15rem;
    font-weight: 500;
    line-height: 1.45;
  }

  .cta-section {
    padding: 0 0 4rem;
  }

  .cta-shell {
    display: grid;
    gap: 1.5rem;
    padding: 2rem;
    border-radius: 2rem;
    background:
      radial-gradient(circle at top right, rgba(255, 255, 255, 0.12), transparent 28%),
      linear-gradient(135deg, #142549, #091228);
    color: #fff;
    box-shadow: 0 28px 80px rgba(10, 18, 40, 0.28);
  }

  .cta-shell p {
    color: rgba(255, 255, 255, 0.72);
  }

  @media (min-width: 900px) {
    .hero-shell,
    .split-layout,
    .cta-shell {
      grid-template-columns: minmax(0, 1.05fr) minmax(22rem, 0.95fr);
    }

    .card-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .migration-grid,
    .metric-row,
    .comparison-band {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .cta-buttons {
      justify-content: flex-end;
      align-content: start;
    }
  }

  @media (max-width: 899px) {
    .hero-section {
      padding-top: 1rem;
    }

    .hero-shell,
    .section-shell,
    .cta-shell,
    .hero-copy {
      width: min(100%, calc(100% - 1rem));
    }

    .hero-shell,
    .section-shell,
    .cta-shell {
      margin: 0 auto;
    }

    .hero-copy,
    .feature-card,
    .template-box,
    .migration-card,
    .cta-shell,
    .panel-window {
      padding: 1.25rem;
    }
  }
</style>
