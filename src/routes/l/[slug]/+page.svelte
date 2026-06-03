<script lang="ts">
  import { buildLandingPageLeadsUrl } from '$lib/api/backend'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'
  import { Button, toast } from 'mono-svelte'
  import {
    ArrowRight,
    BookOpen,
    ChatBubbleLeftRight,
    CheckCircle,
    ClipboardDocumentList,
    Cog6Tooth,
    DocumentText,
    Flag,
    Icon,
    LightBulb,
    MagnifyingGlass,
    MapPin,
    ShieldCheck,
    ViewColumns,
    UserGroup,
  } from 'svelte-hero-icons'
  import type { IconSource } from 'svelte-hero-icons'
  import type { LandingPage, LandingPageImage } from './+page'

  export let data: { landingPage: LandingPage }

  type Feature = {
    icon: IconSource
    title: string
    text: string
  }

  type Scenario = {
    id: string
    title: string
    rubrics: string[]
    value: string
  }

  const pageData = data.landingPage
  const siteName = env.PUBLIC_SITE_TITLE || 'Тамбур'
  const title = `${siteName} - платформа для создания сообществ, базы знаний и живых обсуждений`
  const description =
    pageData.description ||
    'Создайте самостоятельное сообщество с рубриками, правилами, базой знаний, дорожной картой, ролями и публикациями.'

  const pains: Feature[] = [
    {
      icon: ChatBubbleLeftRight,
      title: 'Полезное теряется',
      text: 'Хорошие ответы, идеи, инструкции и обсуждения уходят в историю сообщений.',
    },
    {
      icon: MagnifyingGlass,
      title: 'Новичкам сложно войти',
      text: 'Чтобы понять сообщество, нужно читать сотни сообщений или спрашивать старожилов.',
    },
    {
      icon: Cog6Tooth,
      title: 'Все держится на администраторе',
      text: 'Админ вручную объясняет правила, направляет людей и повторяет одно и то же.',
    },
    {
      icon: ViewColumns,
      title: 'Нет структуры',
      text: 'Новости, вопросы, идеи, отзывы, баги и обсуждения живут в одном потоке.',
    },
    {
      icon: DocumentText,
      title: 'Контент не работает вдолгую',
      text: 'Посты не становятся базой знаний и не помогают новым участникам через месяц.',
    },
    {
      icon: UserGroup,
      title: 'Аудитория не становится авторами',
      text: 'Люди читают и иногда комментируют, но не видят понятного сценария вклада.',
    },
  ]

  const features: Feature[] = [
    {
      icon: Flag,
      title: 'Обособленное пространство',
      text: 'У сообщества есть собственная страница, правила, рубрики и инструменты, а не просто тег в общей ленте.',
    },
    {
      icon: ShieldCheck,
      title: 'Рубрики и права доступа',
      text: 'Новости могут писать админы, отзывы - участники, внутренние обсуждения - проверенные пользователи.',
    },
    {
      icon: ClipboardDocumentList,
      title: 'Шаблоны публикаций',
      text: 'Вопросы, идеи, баг-репорты, обзоры, инструкции и подборки получают понятную форму.',
    },
    {
      icon: BookOpen,
      title: 'База знаний и глоссарий',
      text: 'Термины, инструкции, правила и важные материалы можно собрать отдельно от потока.',
    },
    {
      icon: MapPin,
      title: 'Дорожная карта',
      text: 'Идеи участников попадают в обсуждение, получают голоса и становятся частью roadmap.',
    },
    {
      icon: CheckCircle,
      title: 'Рейтинг, роли и модерация',
      text: 'Система доверия помогает отличать полезный вклад от случайного шума.',
    },
  ]

  const comparisons = [
    ['Telegram', 'Быстрый контакт, привычный формат', 'Нет структуры, знания теряются', 'Рубрики, база знаний, посты, SEO'],
    ['VK', 'Есть аудитория и группы', 'Мало гибкости и настройки сообщества', 'Обособленное пространство и правила'],
    ['Discord', 'Удобен для живого общения', 'Это чат, а не публичная база знаний', 'Посты, глоссарий, roadmap'],
    ['Форум', 'Темы и история', 'Устаревший UX, слабая лента', 'Современная лента, редактор, роли'],
    ['Notion', 'Можно хранить материалы', 'Нет живого сообщества и авторов', 'Контент, обсуждения, роли и знания вместе'],
  ]

  const scenarios: Scenario[] = [
    {
      id: 'game',
      title: 'Сообщество вокруг игры',
      rubrics: ['Новости разработки', 'Devlog', 'Баг-репорты', 'Идеи игроков', 'Гайды', 'Фан-арт', 'Roadmap'],
      value: 'Игроки не просто пишут в чат, а помогают развивать проект.',
    },
    {
      id: 'professional',
      title: 'Профессиональное сообщество',
      rubrics: ['Кейсы', 'Вопросы', 'Инструменты', 'Разборы', 'База знаний', 'Мероприятия', 'Вакансии'],
      value: 'Сообщество становится отраслевой площадкой, а не бесконечной перепиской.',
    },
    {
      id: 'product',
      title: 'Продуктовое сообщество',
      rubrics: ['Обратная связь', 'Идеи', 'Вопросы', 'Баги', 'Инструкции', 'Roadmap', 'Обновления'],
      value: 'Пользователи видят, что их вклад не исчезает, а влияет на развитие продукта.',
    },
    {
      id: 'media',
      title: 'Авторское медиа',
      rubrics: ['Статьи автора', 'Обсуждения', 'Вопросы подписчиков', 'Подборки', 'Глоссарий', 'Предложения тем'],
      value: 'Аудитория превращается из пассивных читателей в участников.',
    },
    {
      id: 'club',
      title: 'Офлайн-клуб',
      rubrics: ['Анонсы встреч', 'Отчеты', 'Участники', 'Правила', 'Материалы', 'Обсуждения', 'Предложения'],
      value: 'Офлайн-жизнь получает цифровую память.',
    },
  ]

  const beforeAfter = [
    ['Все обсуждения в одном потоке', 'У каждой темы своя рубрика'],
    ['Новички задают одни и те же вопросы', 'Есть база знаний и глоссарий'],
    ['Идеи теряются в переписке', 'Идеи попадают в обсуждение и roadmap'],
    ['Полезные посты быстро исчезают', 'Материалы живут, ищутся и индексируются'],
    ['Админ все держит вручную', 'Есть роли, правила и модерация'],
    ['Участники только читают', 'Участники становятся авторами'],
  ]

  const faq = [
    [
      'Зачем мне уходить из Telegram?',
      'Не обязательно уходить. Telegram можно оставить для быстрых сообщений, а Тамбур использовать для знаний, постов, правил, идей и обсуждений, которые не должны потеряться.',
    ],
    [
      'Люди не захотят переходить на новую площадку.',
      'Не нужно переносить всех сразу. Начните с материалов долгой ценности: инструкций, гайдов, правил, частых вопросов и обсуждений.',
    ],
    [
      'У меня уже есть Discord.',
      'Discord хорош для живого общения, но плохо работает как публичная база знаний и структурированная контентная площадка.',
    ],
    [
      'У меня маленькое сообщество. Есть смысл?',
      'Да. Маленькому сообществу проще сразу задать структуру, чем потом разбирать хаос из тысяч сообщений.',
    ],
  ]

  const quizCopy: Record<string, string> = {
    Telegram: 'Из Telegram удобно вынести правила, FAQ, полезные ответы, гайды и обсуждения, которые не должны пропадать в истории.',
    VK: 'Из VK можно забрать ядро аудитории и дать ему больше структуры: рубрики, роли, шаблоны публикаций и отдельную базу знаний.',
    Discord: 'Из Discord стоит вынести материалы, идеи, roadmap и публичные обсуждения, а быстрые разговоры оставить в каналах.',
    Форум: 'С форума можно перенести сильную базу и дать ей современную ленту, удобный редактор, роли и сценарии участия.',
    Офлайн: 'Офлайн-клуб получает цифровую память: анонсы, отчеты, материалы, правила, предложения и обсуждения между встречами.',
    Другое: 'Если у вас уже есть люди и общая тема, Тамбур поможет отделить важное от потока и собрать структуру вокруг сообщества.',
  }

  let activeScenario = scenarios[0].id
  let quizSource = 'Telegram'
  let lead = {
    source: 'Telegram',
    contact: '',
    community_url: '',
    note: '',
  }
  let leadSaving = false
  let leadSent = false
  let leadError = ''

  const activeImages = (pageData.images || []).filter((image) => image.is_active)
  const imageBySlot = (slot: string): LandingPageImage | undefined =>
    activeImages.find((image) => image.slot === slot)
  $: heroImage = imageBySlot('hero') || activeImages[0]
  $: currentScenario = scenarios.find((scenario) => scenario.id === activeScenario) || scenarios[0]
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

  async function submitLead() {
    leadSaving = true
    leadError = ''
    try {
      const response = await fetch(buildLandingPageLeadsUrl(pageData.slug), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...lead, source: quizSource }),
      })
      const result = await response.json().catch(() => null)
      if (!response.ok || !result?.ok) {
        throw new Error(result?.error || 'Не удалось отправить заявку')
      }
      leadSent = true
      lead = { source: quizSource, contact: '', community_url: '', note: '' }
      toast({ content: 'Заявка отправлена', type: 'success' })
    } catch (err) {
      leadError = err instanceof Error ? err.message : 'Не удалось отправить заявку'
    } finally {
      leadSaving = false
    }
  }
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  {#if heroImage?.image_url}
    <meta property="og:image" content={heroImage.image_url} />
  {/if}
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>

{#if pageData.template_slug !== 'community-platform'}
  <main class="landing-page generic-page">
    <section class="content-band">
      <div class="section-shell">
        <p class="eyebrow">Посадочная страница</p>
        <h1>{pageData.title}</h1>
        <p>{pageData.description}</p>
      </div>
    </section>
  </main>
{:else}
  <main class="landing-page">
    <section class="hero">
      <div class="section-shell hero-grid">
        <div class="hero-copy">
          <p class="eyebrow">Платформа для независимых сообществ</p>
          <h1>Ваше сообщество уже существует. Просто оно живет не там, где ему удобно расти.</h1>
          <p class="lead">
            Telegram, VK, Discord и форумы помогают собрать людей. Но когда появляются темы,
            правила, знания, идеи, обратная связь и новые участники, обычного чата или группы
            становится мало. Тамбур дает сообществу отдельное пространство, структуру и
            инструменты для развития.
          </p>
          <div class="hero-actions">
            <Button href="/comuns?create=1" size="lg">
              Создать сообщество
              <Icon src={ArrowRight} size="18" mini slot="suffix" />
            </Button>
            <a class="secondary-link" href="/comuns/after_the_credits">Посмотреть пример</a>
          </div>
        </div>

        <div class="hero-visual" aria-label="Пример сообщества в Тамбуре">
          {#if heroImage?.image_url}
            <img src={heroImage.image_url} alt={heroImage.alt_text || heroImage.title} />
          {:else}
            <div class="interface-mock">
              <div class="mock-head">
                <span class="logo-mark">T</span>
                <div>
                  <strong>Сообщество инди-игры</strong>
                  <small>правила, рубрики, база знаний, roadmap</small>
                </div>
              </div>
              <div class="mock-tabs">
                <span>Новости</span><span>Баги</span><span>Идеи</span><span>Гайды</span>
              </div>
              <div class="mock-layout">
                <div class="mock-posts">
                  <article><b>Devlog: новая система боя</b><p>Обсуждение, голосование и ссылки на материалы</p></article>
                  <article><b>Идея игрока: режим испытаний</b><p>Принято в дорожную карту</p></article>
                  <article><b>Гайд для новичков</b><p>Закреплено в базе знаний</p></article>
                </div>
                <aside>
                  <strong>Правила</strong>
                  <span>Роли</span>
                  <span>Глоссарий</span>
                  <span>Roadmap</span>
                </aside>
              </div>
            </div>
          {/if}
          <p class="image-note">Замените заглушку на реальный скриншот через /l/admin.</p>
        </div>
      </div>
    </section>

    <section class="content-band">
      <div class="section-shell">
        <div class="section-heading">
          <p class="eyebrow">Проблема текущих инструментов</p>
          <h2>Чат, группа и форум не решают одну задачу: они не превращают людей в сообщество.</h2>
          <p>
            Сначала все выглядит живым: люди приходят, пишут, спорят, задают вопросы.
            Потом вопросы повторяются, важные ответы теряются, правила никто не читает,
            а хорошие публикации исчезают под новыми сообщениями.
          </p>
        </div>
        <div class="cards-grid">
          {#each pains as item}
            <article class="info-card">
              <span class="card-icon"><Icon src={item.icon} size="20" mini /></span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          {/each}
        </div>
      </div>
    </section>

    <section class="statement-band">
      <div class="section-shell statement-grid">
        <div>
          <p class="eyebrow">Что такое Тамбур</p>
          <h2>Тамбур - это дом для самостоятельного сообщества.</h2>
        </div>
        <p>
          Он не заменяет Telegram, VK, Discord или форум одним кликом. Он дает место,
          где можно накапливать знания, задавать правила, разделять темы, публиковать
          материалы, собирать обратную связь и постепенно превращать участников в авторов.
        </p>
      </div>
    </section>

    <section class="content-band">
      <div class="section-shell">
        <div class="section-heading">
          <p class="eyebrow">Возможности</p>
          <h2>Не просто лента постов, а структура для долгой жизни сообщества.</h2>
        </div>
        <div class="feature-grid">
          {#each features as item}
            <article class="feature-card">
              <span><Icon src={item.icon} size="22" mini /></span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </article>
          {/each}
        </div>
      </div>
    </section>

    <section class="content-band muted">
      <div class="section-shell">
        <div class="section-heading">
          <p class="eyebrow">Сравнение</p>
          <h2>Почему не Telegram, VK, Discord или форум.</h2>
        </div>
        <div class="comparison-table" role="table" aria-label="Сравнение Тамбура с другими инструментами">
          <div class="table-row table-head" role="row">
            <span>Инструмент</span><span>Что хорошо</span><span>Где ломается</span><span>Что дает Тамбур</span>
          </div>
          {#each comparisons as row}
            <div class="table-row" role="row">
              {#each row as cell}
                <span>{cell}</span>
              {/each}
            </div>
          {/each}
        </div>
        <p class="table-summary">
          Тамбур не спорит с чатами. Он закрывает то, что чаты, группы и форумы обычно
          не умеют: превращает поток общения в управляемое сообщество.
        </p>
      </div>
    </section>

    <section class="content-band">
      <div class="section-shell scenarios">
        <div class="section-heading">
          <p class="eyebrow">Готовые структуры рубрик</p>
          <h2>Начать можно с понятного сценария.</h2>
        </div>
        <div class="tabs" role="tablist" aria-label="Сценарии использования">
          {#each scenarios as scenario}
            <button
              class:active={activeScenario === scenario.id}
              type="button"
              on:click={() => (activeScenario = scenario.id)}
            >
              {scenario.title}
            </button>
          {/each}
        </div>
        <div class="scenario-panel">
          <div>
            <h3>{currentScenario.title}</h3>
            <p>{currentScenario.value}</p>
          </div>
          <div class="rubrics">
            {#each currentScenario.rubrics as rubric}
              <span>{rubric}</span>
            {/each}
          </div>
        </div>
      </div>
    </section>

    <section class="content-band muted">
      <div class="section-shell split-section">
        <div>
          <p class="eyebrow">Переход</p>
          <h2>Переход не обязан быть резким.</h2>
          <p>
            Оставьте текущий канал для быстрых объявлений и привычного общения, а Тамбур
            используйте как основное пространство для материалов, правил, базы знаний и
            обратной связи.
          </p>
        </div>
        <ol class="steps">
          <li>Создайте сообщество.</li>
          <li>Опишите тему и правила.</li>
          <li>Настройте рубрики.</li>
          <li>Перенесите ключевые материалы.</li>
          <li>Пригласите первых участников.</li>
          <li>Закрепите ссылку в текущем канале.</li>
        </ol>
      </div>
    </section>

    <section class="content-band">
      <div class="section-shell">
        <div class="section-heading">
          <p class="eyebrow">До и после</p>
          <h2>Проблема не в людях, а в инструменте.</h2>
        </div>
        <div class="before-after">
          {#each beforeAfter as row}
            <div>
              <span>{row[0]}</span>
              <strong>{row[1]}</strong>
            </div>
          {/each}
        </div>
      </div>
    </section>

    <section class="content-band muted">
      <div class="section-shell split-section">
        <div>
          <p class="eyebrow">Мини-квиз</p>
          <h2>Где сейчас живет ваше сообщество?</h2>
          <p>{quizCopy[quizSource]}</p>
          <div class="quiz-options">
            {#each Object.keys(quizCopy) as option}
              <button class:active={quizSource === option} type="button" on:click={() => (quizSource = option)}>
                {option}
              </button>
            {/each}
          </div>
        </div>
        <form id="transfer" class="lead-form" on:submit|preventDefault={submitLead}>
          <h3>Обсудить перенос сообщества</h3>
          <label>
            Контакт
            <input bind:value={lead.contact} required placeholder="Telegram, email или ссылка на профиль" />
          </label>
          <label>
            Ссылка на текущее сообщество
            <input bind:value={lead.community_url} placeholder="https://..." />
          </label>
          <label>
            Что хотите перенести
            <textarea bind:value={lead.note} rows="4" placeholder="Канал, чат, форум, базу материалов, идеи, FAQ..."></textarea>
          </label>
          {#if leadError}<p class="form-error">{leadError}</p>{/if}
          {#if leadSent}<p class="form-success">Заявка отправлена. Мы вернемся с вопросами по переносу.</p>{/if}
          <Button type="submit" disabled={leadSaving}>
            {leadSaving ? 'Отправляем...' : 'Получить консультацию или демо'}
          </Button>
        </form>
      </div>
    </section>

    <section class="content-band">
      <div class="section-shell examples">
        <div class="section-heading">
          <p class="eyebrow">Примеры</p>
          <h2>Посмотрите, как может выглядеть сообщество на Тамбуре.</h2>
        </div>
        <div class="example-grid">
          <a href="/comuns/after_the_credits">Клуб о кино</a>
          <a href="/comuns">Каталог сообществ</a>
          <a href="/lp/communities">Демо страницы сообщества</a>
        </div>
      </div>
    </section>

    <section class="content-band muted">
      <div class="section-shell faq-grid">
        <div>
          <p class="eyebrow">Возражения</p>
          <h2>Частые вопросы перед переносом.</h2>
        </div>
        <div class="faq-list">
          {#each faq as item}
            <details>
              <summary>{item[0]}</summary>
              <p>{item[1]}</p>
            </details>
          {/each}
        </div>
      </div>
    </section>

    <section class="final-cta">
      <div class="section-shell">
        <h2>Дайте своему сообществу место, где оно сможет расти.</h2>
        <p>
          Если у вас уже есть чат, канал, группа, форум или офлайн-клуб, вы можете
          превратить его в структурированное сообщество на Тамбуре.
        </p>
        <div class="hero-actions">
          <Button href="/comuns?create=1" size="lg">Создать сообщество</Button>
          <a class="secondary-link light" href="#transfer">Обсудить перенос</a>
        </div>
      </div>
    </section>
  </main>
{/if}

<style>
  .landing-page {
    --ink: #111827;
    --muted: #4b5563;
    --line: #d8dee8;
    --soft: #f6f8fb;
    --brand: #2563eb;
    --green: #047857;
    --amber: #b45309;
    width: 100%;
    background: #ffffff;
    color: var(--ink);
  }

  .section-shell {
    width: min(1160px, calc(100% - 32px));
    margin: 0 auto;
  }

  .hero {
    padding: clamp(52px, 6vw, 88px) 0 44px;
    background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  }

  .hero-grid,
  .statement-grid,
  .split-section,
  .faq-grid {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(360px, 0.85fr);
    gap: 40px;
    align-items: center;
  }

  .eyebrow {
    margin: 0 0 12px;
    color: var(--green);
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0;
    text-transform: uppercase;
  }

  h1,
  h2,
  h3,
  p {
    letter-spacing: 0;
  }

  h1 {
    max-width: 760px;
    margin: 0;
    font-size: clamp(32px, 3.9vw, 50px);
    line-height: 1.05;
    font-weight: 900;
  }

  h2 {
    margin: 0;
    font-size: clamp(30px, 4vw, 48px);
    line-height: 1.05;
    font-weight: 900;
  }

  h3 {
    margin: 0;
    font-size: 20px;
    line-height: 1.2;
    font-weight: 850;
  }

  p {
    color: var(--muted);
    line-height: 1.7;
  }

  .lead {
    max-width: 720px;
    margin: 18px 0 0;
    font-size: 18px;
  }

  .hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    align-items: center;
    margin-top: 18px;
  }

  .secondary-link {
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--ink);
    font-weight: 800;
    padding: 0 18px;
    text-decoration: none;
  }

  .secondary-link.light {
    border-color: rgba(255, 255, 255, 0.34);
    color: #ffffff;
  }

  .hero-visual {
    min-width: 0;
  }

  .hero-visual img {
    display: block;
    width: 100%;
    aspect-ratio: 4 / 3;
    border: 1px solid var(--line);
    border-radius: 8px;
    object-fit: cover;
    box-shadow: 0 22px 60px rgba(15, 23, 42, 0.14);
  }

  .interface-mock {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
    box-shadow: 0 22px 60px rgba(15, 23, 42, 0.14);
    overflow: hidden;
  }

  .mock-head {
    display: flex;
    gap: 12px;
    align-items: center;
    border-bottom: 1px solid var(--line);
    padding: 18px;
  }

  .logo-mark {
    display: inline-flex;
    width: 42px;
    height: 42px;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: #1d4ed8;
    color: #ffffff;
    font-weight: 900;
  }

  .mock-head small,
  .mock-posts p,
  .image-note {
    color: #64748b;
  }

  .mock-tabs,
  .rubrics,
  .quiz-options {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .mock-tabs {
    padding: 14px 18px;
    border-bottom: 1px solid var(--line);
  }

  .mock-tabs span,
  .rubrics span {
    border-radius: 8px;
    background: #eef2ff;
    color: #3730a3;
    font-size: 14px;
    font-weight: 800;
    padding: 8px 10px;
  }

  .mock-layout {
    display: grid;
    grid-template-columns: 1fr 150px;
    gap: 16px;
    padding: 18px;
  }

  .mock-posts {
    display: grid;
    gap: 10px;
  }

  .mock-posts article {
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    padding: 14px;
  }

  .mock-posts p {
    margin: 6px 0 0;
    font-size: 14px;
    line-height: 1.5;
  }

  .mock-layout aside {
    display: grid;
    align-content: start;
    gap: 10px;
    border-left: 1px solid var(--line);
    color: #475569;
    padding-left: 16px;
  }

  .image-note {
    margin: 12px 0 0;
    font-size: 13px;
  }

  .content-band,
  .statement-band,
  .final-cta {
    padding: 76px 0;
  }

  .muted {
    background: var(--soft);
  }

  .statement-band {
    background: #0f172a;
    color: #ffffff;
  }

  .statement-band p {
    color: #dbeafe;
    font-size: 19px;
  }

  .section-heading {
    max-width: 840px;
    margin-bottom: 28px;
  }

  .section-heading p {
    max-width: 760px;
    font-size: 18px;
  }

  .cards-grid,
  .feature-grid,
  .example-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }

  .info-card,
  .feature-card,
  .lead-form,
  .scenario-panel,
  .example-grid a {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
  }

  .info-card,
  .feature-card {
    padding: 20px;
  }

  .card-icon,
  .feature-card span {
    display: inline-flex;
    width: 38px;
    height: 38px;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    background: #ecfdf5;
    color: var(--green);
    margin-bottom: 16px;
  }

  .info-card p,
  .feature-card p {
    margin: 10px 0 0;
  }

  .comparison-table {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
    overflow: hidden;
  }

  .table-row {
    display: grid;
    grid-template-columns: 0.7fr 1fr 1.1fr 1.15fr;
    border-top: 1px solid var(--line);
  }

  .table-row:first-child {
    border-top: 0;
  }

  .table-row span {
    min-width: 0;
    border-left: 1px solid var(--line);
    padding: 14px;
    line-height: 1.45;
  }

  .table-row span:first-child {
    border-left: 0;
    font-weight: 850;
  }

  .table-head {
    background: #111827;
    color: #ffffff;
    font-weight: 850;
  }

  .table-summary {
    max-width: 880px;
    margin: 18px 0 0;
    font-weight: 700;
  }

  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-bottom: 16px;
  }

  .tabs button,
  .quiz-options button {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
    color: var(--ink);
    cursor: pointer;
    font-weight: 800;
    min-height: 38px;
    padding: 0 12px;
  }

  .tabs button.active,
  .quiz-options button.active {
    border-color: #2563eb;
    background: #dbeafe;
    color: #1d4ed8;
  }

  .scenario-panel {
    display: grid;
    grid-template-columns: 0.65fr 1fr;
    gap: 24px;
    padding: 24px;
  }

  .steps {
    display: grid;
    gap: 12px;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .steps li {
    border-left: 4px solid var(--amber);
    background: #ffffff;
    border-radius: 8px;
    padding: 14px 16px;
    font-weight: 800;
  }

  .before-after {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 12px;
  }

  .before-after div {
    display: grid;
    gap: 8px;
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 18px;
  }

  .before-after span {
    color: #9f1239;
  }

  .before-after strong {
    color: #047857;
  }

  .lead-form {
    display: grid;
    gap: 14px;
    padding: 22px;
  }

  .lead-form label {
    display: grid;
    gap: 7px;
    color: #374151;
    font-weight: 800;
  }

  .lead-form input,
  .lead-form textarea {
    width: 100%;
    border: 1px solid var(--line);
    border-radius: 8px;
    color: var(--ink);
    font: inherit;
    padding: 11px 12px;
  }

  .form-error {
    margin: 0;
    color: #b91c1c;
  }

  .form-success {
    margin: 0;
    color: #047857;
  }

  .example-grid a {
    min-height: 92px;
    color: var(--ink);
    display: flex;
    align-items: center;
    font-size: 20px;
    font-weight: 900;
    padding: 18px;
    text-decoration: none;
  }

  .faq-list {
    display: grid;
    gap: 10px;
  }

  details {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: #ffffff;
    padding: 16px 18px;
  }

  summary {
    cursor: pointer;
    font-weight: 900;
  }

  details p {
    margin: 12px 0 0;
  }

  .final-cta {
    background: #111827;
    color: #ffffff;
  }

  .final-cta p {
    max-width: 780px;
    color: #d1d5db;
    font-size: 19px;
  }

  .generic-page {
    min-height: 70vh;
  }

  @media (max-width: 900px) {
    .hero-grid,
    .statement-grid,
    .split-section,
    .faq-grid,
    .scenario-panel {
      grid-template-columns: 1fr;
    }

    .cards-grid,
    .feature-grid,
    .example-grid,
    .before-after {
      grid-template-columns: 1fr;
    }

    .table-row {
      grid-template-columns: 1fr;
    }

    .table-head {
      display: none;
    }

    .table-row span {
      border-left: 0;
      border-top: 1px solid var(--line);
    }

    .mock-layout {
      grid-template-columns: 1fr;
    }

    .mock-layout aside {
      border-left: 0;
      border-top: 1px solid var(--line);
      padding: 16px 0 0;
    }
  }
</style>
