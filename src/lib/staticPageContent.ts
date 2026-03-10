export type EditableStaticPageSlug = 'about' | 'advertisement' | 'authors' | 'rules'

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
      '1. Убедитесь, что канал публичный и у него есть @username.<br>2. Добавьте нашего бота <a href="https://t.me/comuna_tg_bot" target="_blank" rel="nofollow noopener">@comuna_tg_bot</a> в администраторы канала и дайте права читать сообщения, прав на чтение будет достаточно для работы.<br>3. В боте выберите тематику канала и режим публикации.<br>4. Публикуйте посты как обычно — они появятся на сайте.<br>5. Ваша страница будет доступна по адресу: <code>comuna.ru/ник_канала</code>.'
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
  authors: encodeEditorPayload({ blocks: DEFAULT_BLOCKS.authors }),
  rules: encodeEditorPayload({ blocks: DEFAULT_BLOCKS.rules }),
}

export const getDefaultStaticPageContent = (slug: EditableStaticPageSlug): string =>
  DEFAULT_STATIC_PAGE_CONTENT[slug]
