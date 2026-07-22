import type { PostLanguageCode } from '$lib/postLanguages'

export type EditableStaticPageSlug = 'about' | 'advertisement' | 'apps' | 'authors' | 'rules'

export const EDITABLE_STATIC_PAGE_META: Record<
  EditableStaticPageSlug,
  {
    heading: string
    description: string
  }
> = {
  about: {
    heading: 'О проекте',
    description:
      'Тамбур помогает Telegram-каналам получать органический трафик из поисковых систем за счет публикации контента на сайте.',
  },
  advertisement: {
    heading: 'Реклама',
    description:
      'Рекламные возможности на Тамбур: спонсорские блоки, интеграции и спецпроекты.',
  },
  apps: {
    heading: 'Приложения',
    description:
      'Скачайте мобильное приложение Тамбур в App Store, Google Play или RuStore.',
  },
  authors: {
    heading: 'Авторам',
    description:
      'Публикуйте посты Telegram-канала на сайте, чтобы их находили в Google и Яндексе и подписывались на ваш канал.',
  },
  rules: {
    heading: 'Правила',
    description:
      'Правила публикации и модерации контента на Тамбур для владельцев Telegram-каналов.',
  },
}

export const isEditableStaticPageSlug = (value: string): value is EditableStaticPageSlug =>
  Object.prototype.hasOwnProperty.call(EDITABLE_STATIC_PAGE_META, value)

const encodeEditorPayload = (payload: unknown): string => {
  const json = JSON.stringify(payload)
  const bufferCtor = (globalThis as any)?.Buffer
  if (bufferCtor) {
    return bufferCtor.from(json, 'utf-8').toString('base64')
  }
  if (typeof btoa === 'function') {
    return btoa(unescape(encodeURIComponent(json)))
  }
  return ''
}

const paragraph = (text: string) => ({ type: 'paragraph', data: { text } })
const header = (text: string, level = 2) => ({ type: 'header', data: { text, level } })

const APP_STORE_LINKS =
  '<span style="display:flex; flex-direction:column; gap:12px; align-items:flex-start;"><a href="https://apps.apple.com/ru/app/tambur/id6784176665" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:0 18px; border-radius:8px; background:#111827; color:#ffffff; font-weight:600; text-decoration:none;">App Store</a><a href="https://play.google.com/store/apps/details?id=ru.comuna.mobile" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:0 18px; border-radius:8px; background:#2563eb; color:#ffffff; font-weight:600; text-decoration:none;">Google Play</a><a href="https://www.rustore.ru/catalog/app/ru.comuna.mobile?_rsc=tf3rt" target="_blank" rel="noopener noreferrer" style="display:inline-flex; align-items:center; justify-content:center; min-height:44px; padding:0 18px; border-radius:8px; background:#0f766e; color:#ffffff; font-weight:600; text-decoration:none;">RuStore</a></span>'

export const APPS_PAGE_LOCALIZATION: Record<
  PostLanguageCode,
  { title: string; description: string; intro: string }
> = {
  ru: {
    title: 'Приложения',
    description: 'Скачайте мобильное приложение Тамбур в App Store, Google Play или RuStore.',
    intro: 'Читайте ленту, статьи и сообщества Тамбура в мобильном приложении.',
  },
  en: {
    title: 'Apps',
    description: 'Download the Tambur mobile app from the App Store, Google Play, or RuStore.',
    intro: 'Read your feed, articles, and Tambur communities in the mobile app.',
  },
  es: {
    title: 'Aplicaciones',
    description: 'Descarga la aplicación móvil de Tambur desde App Store, Google Play o RuStore.',
    intro: 'Lee tu feed, artículos y comunidades de Tambur en la aplicación móvil.',
  },
  pt: {
    title: 'Aplicativos',
    description: 'Baixe o aplicativo móvel do Tambur na App Store, no Google Play ou no RuStore.',
    intro: 'Leia seu feed, artigos e comunidades do Tambur no aplicativo móvel.',
  },
  de: {
    title: 'Apps',
    description: 'Lade die Tambur-App im App Store, bei Google Play oder RuStore herunter.',
    intro: 'Lies deinen Feed, Artikel und Tambur-Communitys in der mobilen App.',
  },
  fr: {
    title: 'Applications',
    description: "Téléchargez l'application mobile Tambur sur l'App Store, Google Play ou RuStore.",
    intro: "Consultez votre fil, les articles et les communautés Tambur dans l'application mobile.",
  },
  tr: {
    title: 'Uygulamalar',
    description: "Tambur mobil uygulamasını App Store, Google Play veya RuStore'dan indirin.",
    intro: 'Akışınızı, makaleleri ve Tambur topluluklarını mobil uygulamada okuyun.',
  },
  id: {
    title: 'Aplikasi',
    description: 'Unduh aplikasi seluler Tambur dari App Store, Google Play, atau RuStore.',
    intro: 'Baca feed, artikel, dan komunitas Tambur melalui aplikasi seluler.',
  },
}

const DEFAULT_BLOCKS: Record<EditableStaticPageSlug, Array<Record<string, any>>> = {
  about: [
    paragraph(
      'Мы помогаем авторам Telegram-каналов получать органический трафик из поисковых систем. Контент каналов почти не индексируется, поэтому новые читатели вас не находят.'
    ),
    paragraph(
      'Наш сайт публикует материалы из вашего канала и делает их доступными для Google и Яндекса. Люди находят статьи, переходят на канал и подписываются.'
    ),
    paragraph(
      '<a href="https://productradar.ru/product/comuna?utm_source=badge" target="_blank" rel="noopener noreferrer"><img src="https://productradar.ru/badge?period=week&amp;rank=1&amp;theme=white" alt="Награда Продукт недели #1 | Product Radar" width="252" height="68" style="object-fit: initial; border: none; margin:0; width: 252px; height: 68px; vertical-align: bottom;" /></a>'
    ),
    header('Как это работает'),
    paragraph(
      '1. Вы добавляете нашего бота в админы своего канала.<br>2. Мы автоматически создаем страницы с вашими постами.<br>3. Поисковые системы индексируют страницы.<br>4. Читатели приходят на сайт и подписываются на ваш канал.'
    ),
  ],
  advertisement: [
    paragraph(
      'Мы открыты к рекламным интеграциям и партнерствам. Реклама показывается на страницах сайта и помогает авторам получать больше внимания к контенту.'
    ),
    header('Форматы'),
    paragraph(
      '• Спонсорские блоки на страницах статей.<br>• Интеграции в подборках и разделах сайта.<br>• Спецпроекты под вашу задачу.'
    ),
    header('Как связаться'),
    paragraph('Напишите нам, и мы подберем оптимальный формат под ваши цели.'),
  ],
  apps: [
    paragraph(APPS_PAGE_LOCALIZATION.ru.intro),
    paragraph(APP_STORE_LINKS),
  ],
  authors: [
    paragraph(
      'Telegram-каналы почти не попадают в поисковую выдачу. Люди ищут темы в Google и Яндексе, но ваши посты там не видят.'
    ),
    paragraph(
      'Мы решаем это через сайт: публикуем ваши материалы здесь, поисковые системы их индексируют, и новые читатели находят ваш контент. Дальше они переходят по ссылке на канал и подписываются. Это бесплатные подписчики и дополнительный трафик.'
    ),
    paragraph(
      'Сайт работает как для публикации постов через телеграм, так и через личный кабинет сайта.'
    ),
    header('Как подключиться'),
    paragraph(
      '1. Убедитесь, что канал публичный и у него есть @username.<br>2. Добавьте нашего бота <a href="https://t.me/comuna_tg_bot" target="_blank" rel="nofollow noopener">@comuna_tg_bot</a> в администраторы канала и дайте права читать сообщения, прав на чтение будет достаточно для работы.<br>3. В боте выберите режим публикации.<br>4. Для канала на сайте будет создано одноименное сообщество, управлять им можно после регистрации на сайте.<br>5. Публикуйте посты как обычно — они появятся на сайте.<br>6. Ваша страница будет доступна по адресу: <code>tambur.pub/ник_канала</code>.'
    ),
  ],
  rules: [
    paragraph(
      'Мы публикуем материалы из Telegram-каналов в открытом доступе. Чтобы сохранить качество и безопасность, мы просим соблюдать простые правила.'
    ),
    header('Что нельзя'),
    paragraph(
      '• Нарушать законы РФ и других стран.<br>• Публиковать экстремизм, угрозы, призывы к насилию.<br>• Публиковать спам, мошенничество и фишинг.<br>• Прямая реклама без дополнительной ценности.<br>• Нарушать авторские права.'
    ),
    header('Модерация'),
    paragraph(
      'Мы можем скрывать отдельные публикации или полностью блокировать каналы, нарушающие правила. Администрация не уведомляет о блокировке или удалении контента. Для вопросов и апелляций — напишите нам.'
    ),
  ],
}

export const DEFAULT_STATIC_PAGE_CONTENT: Record<EditableStaticPageSlug, string> = {
  about: encodeEditorPayload({ blocks: DEFAULT_BLOCKS.about }),
  advertisement: encodeEditorPayload({ blocks: DEFAULT_BLOCKS.advertisement }),
  apps: encodeEditorPayload({ blocks: DEFAULT_BLOCKS.apps }),
  authors: encodeEditorPayload({ blocks: DEFAULT_BLOCKS.authors }),
  rules: encodeEditorPayload({ blocks: DEFAULT_BLOCKS.rules }),
}

export const getDefaultStaticPageContent = (slug: EditableStaticPageSlug): string =>
  DEFAULT_STATIC_PAGE_CONTENT[slug]

export const getLocalizedDefaultStaticPage = (
  slug: EditableStaticPageSlug,
  language: PostLanguageCode
): { title: string; content: string } => {
  if (slug !== 'apps' || language === 'ru') {
    return {
      title: EDITABLE_STATIC_PAGE_META[slug].heading,
      content: getDefaultStaticPageContent(slug),
    }
  }

  const localized = APPS_PAGE_LOCALIZATION[language]
  return {
    title: localized.title,
    content: encodeEditorPayload({
      blocks: [paragraph(localized.intro), paragraph(APP_STORE_LINKS)],
    }),
  }
}
