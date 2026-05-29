<script lang="ts">
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import type { TemplateEditorBlockType } from '$lib/postTemplates'
  import type { IconSource } from 'svelte-hero-icons'
  import {
    ArrowTrendingUp,
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

  type ComparisonPoint = {
    number: string
    title: string
    text: string
  }

  type VisualCommunity = {
    tone: string
    title: string
    text: string
  }

  const siteName = env.PUBLIC_SITE_TITLE || 'Тамбур'
  const title = `Платформа для онлайн-сообществ — ${siteName}`
  const description =
    'Создайте сообщество на Тамбур и управляйте не только обсуждением, но и правилами участия: кто пишет, кто комментирует, какие типы постов доступны, по каким шаблонам публикуются материалы и как выглядит сама страница.'

  const authorControls: LandingCard[] = [
    {
      icon: UserGroup,
      eyebrow: 'Роли и доступ',
      title: 'Вы решаете, кто пишет, а кто только читает и комментирует',
      text: 'Не все участники должны иметь одинаковые права. Настройте роли так, чтобы контент выпускали нужные люди, а обсуждение оставалось живым и управляемым.',
    },
    {
      icon: ClipboardDocumentList,
      eyebrow: 'Типы постов',
      title: 'Каждый формат публикации можно оформить как отдельный сценарий',
      text: 'Новости, подборки, обзоры, разборы и AMA не обязаны жить в одном хаосе. Для каждого типа поста задаются свои ожидания и структура.',
    },
    {
      icon: Sparkles,
      eyebrow: 'Шаблоны',
      title: 'Пользователь публикует не из пустоты, а по понятному шаблону',
      text: 'Шаблоны помогают включать людей в создание контента и при этом не жертвовать качеством, стилем и логикой материалов.',
    },
    {
      icon: ShieldCheck,
      eyebrow: 'Своя среда',
      title: 'Правила, модерация и оформление становятся частью платформы',
      text: 'Сообщество получает не просто канал с сообщениями, а собственную страницу с правилами, подачей и узнаваемой логикой участия.',
    },
  ]

  const messengerGaps: ComparisonPoint[] = [
    {
      number: '01',
      title: 'В одном потоке смешиваются объявления, обсуждения и важные материалы',
      text: 'В мессенджере все быстро уходит вниз. Людям трудно возвращаться к полезному контенту и невозможно воспринимать его как растущую базу знаний.',
    },
    {
      number: '02',
      title: 'Участие в сообществе сводится к чтению и случайным репликам',
      text: 'Если вы хотите, чтобы люди писали по теме, соблюдали формат и развивали направление вместе с вами, чат почти не дает для этого инструментов.',
    },
    {
      number: '03',
      title: 'Автор не управляет архитектурой комьюнити',
      text: 'Нельзя удобно задать типы постов, сценарии публикации, роли и логику участия. В итоге комьюнити держится на ручных объяснениях и энтузиазме.',
    },
  ]

  const migrationWins: LandingCard[] = [
    {
      icon: Megaphone,
      eyebrow: 'Контакт с аудиторией',
      title: 'Вы не теряете близость с подписчиками',
      text: 'Люди по-прежнему приходят к вам за темой, голосом автора и ощущением прямого общения. Просто теперь это общение живет в более сильной среде.',
    },
    {
      icon: DocumentText,
      eyebrow: 'Структура',
      title: 'Контент перестает исчезать и начинает работать на вас месяцами',
      text: 'Каждая публикация получает свою страницу, обсуждение и место в архиве. Со временем это превращается в актив сообщества, а не в пропавший поток.',
    },
    {
      icon: ArrowTrendingUp,
      eyebrow: 'Рост участия',
      title: 'Подписчики могут не только читать, но и включаться глубже',
      text: 'Когда у сообщества есть роли, типы постов и шаблоны, аудитория получает больше способов быть полезной: публиковать, обсуждать, дополнять и возвращаться.',
    },
  ]

  const growthBenefits: LandingCard[] = [
    {
      icon: UserGroup,
      eyebrow: 'Трафик внутри платформы',
      title: 'Сообщество автора встраивается в экосистему сайта',
      text: 'Ваш контент видят не только текущие подписчики. Другие пользователи платформы могут находить публикации, переходить в сообщество, читать материалы и подписываться на него.',
    },
    {
      icon: DocumentText,
      eyebrow: 'Трафик из поиска',
      title: 'Страницы сообщества и публикации индексируются поисковыми системами',
      text: 'Материалы сообщества могут получать органический трафик из поиска. Это значит, что хорошие тексты работают не один день, а продолжают приводить новых читателей и участников.',
    },
    {
      icon: ArrowTrendingUp,
      eyebrow: 'Эффект роста',
      title: 'Каждая сильная публикация начинает работать на рост самого сообщества',
      text: 'Контент приводит новых людей, новые люди подписываются, а сообщество постепенно превращается в самостоятельную точку входа для вашей темы и вашего имени.',
    },
  ]

  const showcaseCommunities: VisualCommunity[] = [
    {
      tone: 'technology',
      title: 'Технологическое сообщество',
      text: 'Подходит для новостей, разборов продуктов, инженерных колонок и экспертных обсуждений.',
    },
    {
      tone: 'science',
      title: 'Научная вертикаль',
      text: 'Можно оформить правила для рецензий, заметок, дискуссий и популяризаторских публикаций.',
    },
    {
      tone: 'music',
      title: 'Культурное комьюнити',
      text: 'Редакционные подборки, рецензии, анонсы и пользовательские посты живут в одном узнаваемом пространстве.',
    },
  ]

  const checklist = [
    'Настройте, кто может писать в сообществе, а кто может комментировать.',
    'Определите типы постов и правила публикации для разных тематик.',
    'Соберите шаблоны, чтобы пользователи публиковали качественно и предсказуемо.',
    'Оформите страницу сообщества так, чтобы у него было собственное лицо.',
    'Получайте новых читателей из экосистемы сайта и из поисковых систем.',
  ]

  const templateExamples = [
    'Обзор: тезис, аргументы, примеры, вывод, рейтинг.',
    'Подборка: критерии отбора, карточки объектов, рекомендации редакции.',
    'Кейс: контекст, решение, результат, что можно повторить у себя.',
  ]

  const editorDemoBlockTypes: TemplateEditorBlockType[] = [
    'header',
    'list',
    'image',
    'quote',
    'code',
    'divider',
    'spoiler',
    'gallery',
    'compare',
    'embed',
    'link',
    'poll',
  ]

  let editorDemoValue = JSON.stringify({
    blocks: [
      {
        type: 'header',
        data: {
          text: 'Шаблон поста для сообщества',
          level: 2,
        },
      },
      {
        type: 'paragraph',
        data: {
          text: 'Этот шаблон можно заранее собрать для авторов сообщества: структура уже задана, участнику остается только заполнить блоки по смыслу.',
        },
      },
      {
        type: 'header',
        data: {
          text: 'Что должно быть в материале',
          level: 3,
        },
      },
      {
        type: 'list',
        data: {
          style: 'unordered',
          items: [
            'Лид с основной мыслью публикации',
            'Ключевые тезисы или критерии оценки',
            'Факты, примеры, иллюстрации или цитаты',
            'Вывод и приглашение к обсуждению',
          ],
        },
      },
      {
        type: 'quote',
        data: {
          text: 'Автор сообщества заранее продумывает структуру. Пользователь приходит уже в понятную форму публикации.',
          caption: 'Смысл шаблонного редактора',
          alignment: 'left',
        },
      },
      {
        type: 'divider',
        data: {},
      },
      {
        type: 'paragraph',
        data: {
          text: 'Попробуйте добавить свои блоки через плюс слева: список, галерею, цитату, код, опрос, сравнение изображений или embed.',
        },
      },
    ],
  })

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
    <div class="hero-shell hero-shell--split">
      <div class="hero-copy">
        <div class="eyebrow">Платформа для онлайн-сообществ</div>
        <h1>Сообщество, которое работает</h1>
        <p class="hero-lead">
          Тамбур помогает автору создать не просто канал, а полноценное
          пространство для сообщества. Здесь вы управляете не только вниманием
          аудитории, но и тем, как люди участвуют, публикуют и взаимодействуют
          друг с другом.
        </p>
        <p class="hero-sublead">
          Вы решаете, кто пишет в сообществе, кто комментирует, какие типы
          постов доступны, по каким шаблонам создаются публикации и как выглядит
          сама страница. Людям нужно больше, чем поток сообщений. Им нужно место
          для нормального участия.
        </p>

        <div class="hero-actions">
          <a class="cta-primary" href="/comuns?create=1">Создать сообщество</a>
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

      <div class="hero-visual">
        <article class="hero-visual__card hero-visual__card--large">
          <div class="gradient-media gradient-media--technology" aria-hidden="true"></div>
          <div class="hero-visual__caption">
            <span>Управляемая среда</span>
            <strong>Роли, типы постов, шаблоны и собственный стиль страницы</strong>
          </div>
        </article>

        <div class="hero-visual__grid">
          <article class="hero-visual__card">
            <div class="gradient-media gradient-media--science" aria-hidden="true"></div>
            <div class="hero-visual__caption hero-visual__caption--compact">
              <span>Для тематики</span>
              <strong>с отдельными правилами публикации</strong>
            </div>
          </article>

          <div class="hero-visual__note">
            <div class="hero-visual__note-label">Что получает автор</div>
            <strong>Контроль над логикой комьюнити</strong>
            <p>
              Не нужно объяснять каждому участнику вручную, как правильно
              публиковать и где искать важное.
            </p>
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="content-section">
    <div class="section-shell">
      <div class="section-heading">
        <div class="eyebrow">Главная ошибка</div>
        <h2>Мессенджер создает иллюзию комьюнити, но не дает среду для его роста</h2>
        <p>
          Каналы и чаты удобны для сигнала, но слабы для построения сообщества.
          Как только вы хотите выстроить правила, вернуть людей к старым
          материалам и дать аудитории больше форм участия, поток начинает
          работать против вас.
        </p>
      </div>

      <div class="message-grid">
        {#each messengerGaps as gap}
          <article class="message-card">
            <div class="message-card__number">{gap.number}</div>
            <h3>{gap.title}</h3>
            <p>{gap.text}</p>
          </article>
        {/each}
      </div>

      <div class="comparison-band">
        <div>
          <span>В мессенджере</span>
          <strong>люди читают, пишут в поток и быстро теряют контекст</strong>
        </div>
        <div>
          <span>В Тамбур</span>
          <strong>люди читают, комментируют, публикуют и возвращаются к материалам</strong>
        </div>
      </div>
    </div>
  </section>

  <section class="content-section content-section--contrast">
    <div class="section-shell">
      <div class="section-heading">
        <div class="eyebrow">Что получает автор</div>
        <h2>Вы задаете архитектуру сообщества, а не надеетесь на хаотичную активность</h2>
        <p>
          Хорошее комьюнити растет не само по себе. Ему нужна среда, где роли,
          формат участия и качество контента заложены в саму платформу.
        </p>
      </div>

      <div class="card-grid">
        {#each authorControls as item}
          <article class="feature-card">
            <div class="feature-card__icon">
              <Icon src={item.icon} size="20" />
            </div>
            <div class="feature-card__eyebrow">{item.eyebrow}</div>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </article>
        {/each}
      </div>
    </div>
  </section>

  <section class="content-section">
    <div class="section-shell split-layout">
      <div class="section-heading section-heading--compact">
        <div class="eyebrow">Шаблоны и публикации</div>
        <h2>Людям проще включаться, когда формат участия уже продуман</h2>
        <p>
          Задайте типы постов и шаблоны публикации, чтобы пользователь не
          начинал с пустого листа. Тогда автор пишет по сценарию, а сообщество
          получает предсказуемо качественный контент.
        </p>

        <div class="template-box">
          <div class="template-box__title">Примеры шаблонов внутри сообщества</div>
          <ul>
            {#each templateExamples as example}
              <li>{example}</li>
            {/each}
          </ul>
        </div>
      </div>

      <div class="template-visual">
        <div class="gradient-media gradient-media--template" aria-hidden="true"></div>
        <div class="template-visual__note">
          <span>Шаблон публикации</span>
          <strong>Материал выходит по понятной структуре</strong>
          <p>
            Автору легче начать, редактору легче проверять, читателю легче
            воспринимать.
          </p>
        </div>
      </div>
    </div>
  </section>

  <section class="content-section content-section--editor">
    <div class="section-shell editor-showcase">
      <div class="section-heading">
        <div class="eyebrow">Редактор сообщества</div>
        <h2>Наш редактор помогает собирать шаблоны из блоков и отдавать их авторам как готовую структуру</h2>
        <p>
          Это не просто поле для текста. Внутри сообщества вы можете заранее
          собрать структуру публикации из блоков: заголовков, списков, цитат,
          галерей, embed-блоков, сравнений изображений и других элементов.
          После этого пользователи пишут не с нуля, а внутри уже подготовленного
          сценария.
        </p>
      </div>

      <div class="editor-promo-grid">
        <article class="message-card">
          <div class="message-card__number">Шаблон</div>
          <h3>Структура поста задается заранее</h3>
          <p>
            Вы можете продумать композицию материала до публикации: где нужен
            лид, где список критериев, где цитата, где иллюстрации и где финальный
            блок для обсуждения.
          </p>
        </article>

        <article class="message-card">
          <div class="message-card__number">Блоки</div>
          <h3>Из множества блоков собирается свой формат сообщества</h3>
          <p>
            Для одних сообществ важны обзоры и рейтинги, для других подборки,
            галереи и embed-контент. Редактор не ограничивает вас одной формой
            публикации.
          </p>
        </article>

        <article class="message-card">
          <div class="message-card__number">Практика</div>
          <h3>Ниже встроен реальный редактор, которым можно пользоваться</h3>
          <p>
            Это не скриншот. Попробуйте нажать на плюс слева, добавить блоки и
            посмотреть, как может выглядеть шаблон поста для вашего сообщества.
          </p>
        </article>
      </div>

      <div class="editor-demo-shell">
        <div class="editor-demo-head">
          <div>
            <div class="editor-demo-label">Живой демо-режим</div>
            <strong>Реальный редактор без сохранения</strong>
          </div>
          <p>
            Здесь можно поиграться с блоками и представить, как будет выглядеть
            шаблон публикации внутри вашего сообщества.
          </p>
        </div>

        <div class="editor-demo">
          <EditorJS
            bind:value={editorDemoValue}
            placeholder="Добавьте новый блок через плюс слева"
            label=""
            enableAutosave={false}
            showPostSettings={false}
            enabledTemplateEditorBlockTypes={editorDemoBlockTypes}
          />
        </div>
      </div>
    </div>
  </section>

  <section class="content-section content-section--gallery">
    <div class="section-shell">
      <div class="section-heading">
        <div class="eyebrow">Своя витрина</div>
        <h2>Страница сообщества должна выглядеть как отдельное место, а не как еще один чат</h2>
        <p>
          У сообщества должно быть собственное лицо. Оформление, тематика,
          публикации и правила создают ощущение пространства, в которое хочется
          возвращаться и которое хочется развивать.
        </p>
      </div>

      <div class="showcase-grid">
        {#each showcaseCommunities as community}
          <article class="showcase-card">
            <div class={`gradient-media gradient-media--${community.tone}`} aria-hidden="true"></div>
            <div class="showcase-card__body">
              <h3>{community.title}</h3>
              <p>{community.text}</p>
            </div>
          </article>
        {/each}
      </div>
    </div>
  </section>

  <section class="content-section" id="telegram-migration">
    <div class="section-shell">
      <div class="section-heading">
        <div class="eyebrow">Переход из Telegram и чатов</div>
        <h2>Можно перевести аудиторию на платформу и не потерять ощущение близости</h2>
        <p>
          Вам не нужно отказываться от своей аудитории или ломать ее привычки.
          Вы просто переносите взаимодействие в место, где подписчики получают
          больше возможностей: читать, обсуждать, публиковать и возвращаться к
          лучшим материалам.
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
    </div>
  </section>

  <section class="content-section content-section--contrast">
    <div class="section-shell">
      <div class="section-heading">
        <div class="eyebrow">Рост аудитории</div>
        <h2>Сообщество на платформе помогает не только удерживать, но и привлекать новых людей</h2>
        <p>
          Когда сообщество живет внутри сайта, оно получает дополнительный канал
          роста. Публикации работают не только на ваших текущих подписчиков, но и
          на новых пользователей, которые находят контент внутри платформы и через
          поисковые системы.
        </p>
      </div>

      <div class="card-grid">
        {#each growthBenefits as item}
          <article class="feature-card">
            <div class="feature-card__icon">
              <Icon src={item.icon} size="20" />
            </div>
            <div class="feature-card__eyebrow">{item.eyebrow}</div>
            <h3>{item.title}</h3>
            <p>{item.text}</p>
          </article>
        {/each}
      </div>
    </div>
  </section>

  <section class="cta-section">
    <div class="cta-shell">
      <div>
        <h2>Если у вас уже есть канал, редакция или клуб по интересам, пора дать ему настоящую платформу</h2>
        <p>
          Создайте сообщество, настройте роли, шаблоны и правила, оформите свою
          страницу и переведите аудиторию туда, где комьюнити действительно
          может расти.
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

  .hero-shell,
  .section-shell,
  .cta-shell {
    display: grid;
    gap: 1.5rem;
  }

  .hero-copy,
  .hero-visual__note,
  .message-card,
  .feature-card,
  .template-box,
  .template-visual__note,
  .migration-card,
  .showcase-card,
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

  .hero-sublead {
    margin: 1rem 0 0;
    color: var(--landing-muted);
    font-size: 1.05rem;
    line-height: 1.65;
  }

  .hero-lead,
  .section-heading p,
  .message-card p,
  .feature-card p,
  .template-visual__note p,
  .showcase-card p,
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

  .hero-visual {
    display: grid;
    gap: 1rem;
  }

  .hero-visual__grid {
    display: grid;
    gap: 1rem;
  }

  .hero-visual__card,
  .template-visual,
  .showcase-card {
    position: relative;
    overflow: hidden;
    border-radius: 1.8rem;
    border: 1px solid var(--landing-line);
    background: rgba(255, 255, 255, 0.6);
    box-shadow: 0 18px 60px rgba(35, 44, 79, 0.08);
  }

  .gradient-media {
    display: block;
    width: 100%;
    height: 100%;
    background-size: cover;
    background-position: center;
  }

  .gradient-media--technology {
    background:
      radial-gradient(circle at 22% 24%, rgba(110, 231, 255, 0.55), transparent 24%),
      radial-gradient(circle at 80% 18%, rgba(59, 130, 246, 0.42), transparent 28%),
      linear-gradient(135deg, #133b67 0%, #1d5f89 42%, #3aa4b0 100%);
  }

  .gradient-media--science {
    background:
      radial-gradient(circle at 28% 22%, rgba(167, 243, 208, 0.36), transparent 24%),
      radial-gradient(circle at 78% 70%, rgba(96, 165, 250, 0.4), transparent 28%),
      linear-gradient(145deg, #142549 0%, #1f4d78 48%, #2f7c7a 100%);
  }

  .gradient-media--template {
    background:
      radial-gradient(circle at 18% 22%, rgba(255, 214, 170, 0.42), transparent 24%),
      radial-gradient(circle at 74% 18%, rgba(251, 146, 60, 0.24), transparent 26%),
      linear-gradient(135deg, #7b402d 0%, #b7643d 45%, #df9a52 100%);
  }

  .gradient-media--music {
    background:
      radial-gradient(circle at 24% 24%, rgba(254, 205, 211, 0.38), transparent 24%),
      radial-gradient(circle at 78% 20%, rgba(253, 186, 116, 0.28), transparent 26%),
      linear-gradient(140deg, #5a1f35 0%, #9b3653 42%, #e28a47 100%);
  }

  .hero-visual__card--large {
    min-height: 26rem;
  }

  .hero-visual__card:not(.hero-visual__card--large) {
    min-height: 14rem;
  }

  .hero-visual__caption {
    position: absolute;
    left: 1rem;
    right: 1rem;
    bottom: 1rem;
    display: grid;
    gap: 0.35rem;
    padding: 1rem 1.1rem;
    border-radius: 1.3rem;
    background: rgba(14, 24, 46, 0.78);
    color: #fff;
  }

  .hero-visual__caption span,
  .hero-visual__note-label {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.72);
  }

  .hero-visual__caption strong,
  .hero-visual__note strong,
  .message-card h3,
  .migration-card h3,
  .feature-card h3,
  .showcase-card h3,
  .cta-shell h2,
  .section-heading h2,
  .template-box__title,
  .template-visual__note strong {
    display: block;
    margin: 0;
    font-weight: 500;
    letter-spacing: -0.03em;
  }

  .hero-visual__caption--compact strong {
    font-size: 1.05rem;
    line-height: 1.25;
  }

  .hero-visual__note {
    padding: 1.4rem;
    border-radius: 1.8rem;
    border: 1px solid var(--landing-line);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.78)),
      linear-gradient(135deg, rgba(209, 96, 50, 0.12), transparent);
    box-shadow: 0 18px 60px rgba(35, 44, 79, 0.08);
  }

  .hero-visual__note p {
    margin: 0.65rem 0 0;
    color: var(--landing-muted);
    line-height: 1.6;
  }

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

  .feature-card__icon,
  .migration-card__icon {
    background: var(--landing-accent-soft);
    color: var(--landing-accent);
  }

  .message-grid,
  .card-grid,
  .migration-grid,
  .showcase-grid {
    display: grid;
    gap: 1rem;
  }

  .message-card,
  .feature-card,
  .template-box,
  .migration-card {
    padding: 1.5rem;
    border-radius: 1.6rem;
    border: 1px solid var(--landing-line);
    background: var(--landing-paper);
    box-shadow: 0 18px 60px rgba(35, 44, 79, 0.06);
  }

  .message-card {
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.8)),
      linear-gradient(135deg, rgba(23, 61, 138, 0.08), transparent);
  }

  .message-card__number {
    color: var(--landing-accent-dark);
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  .message-card h3,
  .feature-card h3,
  .migration-card h3,
  .showcase-card h3 {
    margin-top: 0.8rem;
    font-size: 1.45rem;
    line-height: 1.1 !important;
  }

  .editor-showcase {
    gap: 1.5rem;
  }

  .editor-promo-grid {
    display: grid;
    gap: 1rem;
  }

  .editor-demo-shell {
    display: grid;
    gap: 1rem;
    padding: 1.4rem;
    border-radius: 1.8rem;
    border: 1px solid var(--landing-line);
    background:
      linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.82)),
      linear-gradient(135deg, rgba(23, 61, 138, 0.08), transparent);
    box-shadow: 0 20px 70px rgba(35, 44, 79, 0.08);
  }

  .editor-demo-head {
    display: grid;
    gap: 0.65rem;
  }

  .editor-demo-label {
    color: var(--landing-accent-dark);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .editor-demo-head strong {
    display: block;
    font-size: clamp(1.4rem, 3vw, 2rem);
    font-weight: 500;
    letter-spacing: -0.03em;
  }

  .editor-demo-head p {
    margin: 0;
    max-width: 42rem;
    color: var(--landing-muted);
    line-height: 1.65;
  }

  .editor-demo {
    overflow: hidden;
    border-radius: 1.4rem;
    border: 1px solid rgba(57, 76, 116, 0.12);
    background: rgba(255, 255, 255, 0.72);
  }

  .editor-demo :global(.editor-container) {
    padding: 1rem;
  }

  .editor-demo :global(.editor-content) {
    min-height: 30rem;
    background: rgba(255, 255, 255, 0.95);
  }

  .content-section {
    padding: 1rem 0 3.5rem;
  }

  .content-section--contrast {
    padding-top: 0.25rem;
  }

  .content-section--editor {
    padding-top: 0;
  }

  .content-section--gallery {
    padding-top: 0;
  }

  .section-shell {
    align-items: start;
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

  .feature-card__eyebrow,
  .migration-card__eyebrow {
    margin-top: 1rem;
    color: var(--landing-accent-dark);
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .split-layout {
    align-items: start;
  }

  .template-box {
    margin-top: 1.5rem;
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

  .template-visual {
    min-height: 24rem;
  }

  .template-visual__note {
    position: absolute;
    left: 1rem;
    right: 1rem;
    bottom: 1rem;
    padding: 1rem 1.1rem;
    border-radius: 1.35rem;
    border: 1px solid rgba(255, 255, 255, 0.16);
    background: rgba(14, 24, 46, 0.82);
    color: #fff;
  }

  .template-visual__note span {
    display: block;
    margin-bottom: 0.35rem;
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: rgba(255, 255, 255, 0.72);
  }

  .template-visual__note p {
    margin: 0.5rem 0 0;
    color: rgba(255, 255, 255, 0.78);
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

  .showcase-card .gradient-media {
    aspect-ratio: 1.2 / 1;
  }

  .showcase-card__body {
    display: grid;
    gap: 0.5rem;
    padding: 1.3rem;
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.8));
  }

  .showcase-card__body h3 {
    margin: 0;
  }

  .showcase-card__body p {
    margin: 0;
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

  @media (min-width: 960px) {
    .hero-shell--split,
    .split-layout,
    .cta-shell {
      grid-template-columns: minmax(0, 1.05fr) minmax(22rem, 0.95fr);
    }

    .hero-visual__grid {
      grid-template-columns: minmax(0, 1.05fr) minmax(16rem, 0.95fr);
    }

    .message-grid,
    .card-grid {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .editor-promo-grid,
    .showcase-grid,
    .migration-grid {
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }

    .comparison-band {
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }

    .cta-buttons {
      justify-content: flex-end;
      align-content: start;
    }
  }

  @media (max-width: 959px) {
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
    .hero-visual__note,
    .message-card,
    .feature-card,
    .template-box,
    .template-visual__note,
    .migration-card,
    .showcase-card__body,
    .cta-shell {
      padding: 1.25rem;
    }

    .hero-visual__card--large {
      min-height: 18rem;
    }

    .hero-visual__card:not(.hero-visual__card--large),
    .template-visual {
      min-height: 14rem;
    }

    .editor-demo-shell {
      padding: 1rem;
    }

    .editor-demo :global(.editor-container) {
      padding: 0.65rem;
    }

    .editor-demo :global(.editor-content) {
      min-height: 24rem;
    }

    .hero-visual__caption,
    .template-visual__note {
      left: 0.75rem;
      right: 0.75rem;
      bottom: 0.75rem;
    }
  }
</style>
