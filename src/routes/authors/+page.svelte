<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import SectionTitle from '$lib/components/ui/SectionTitle.svelte'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'

  const title = `Авторам — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  const description =
    'Публикуйте посты Telegram-канала на сайте, чтобы их находили в Google и Яндексе и подписывались на ваш канал.'
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Авторам</h1>
  </Header>

  <div class="flex flex-col gap-3 text-base leading-relaxed">
    <p>
      Telegram‑каналы почти не попадают в поисковую выдачу. Люди ищут темы в
      Google и Яндексе, но ваши посты там не видят.
    </p>
    <p>
      Мы решаем это через сайт: публикуем ваши материалы здесь, поисковые системы
      их индексируют, и новые читатели находят ваш контент. Дальше они переходят
      по ссылке на канал и подписываются. Это бесплатные подписчики и
      дополнительный трафик.
    </p>
    <p>
      Важно: мы не принимаем публикации напрямую через сайт — все посты приходят
      только из вашего Telegram-канала через нашего бота.
    </p>
  </div>

  <SectionTitle class="text-lg font-semibold">Как подключиться</SectionTitle>
  <ol class="list-decimal pl-6 space-y-2 text-base leading-relaxed">
    <li>Убедитесь, что канал публичный и у него есть @username.</li>
    <li>Добавьте нашего бота <a href="https://t.me/comuna_tg_bot" target="_blank" rel="noreferrer">@comuna_tg_bot</a> в администраторы канала и дайте права читать/публиковать сообщения.</li>
    <li>В боте выберите тематику канала и режим публикации.</li>
    <li>При желании добавьте ссылку приглашения на канал — она будет использоваться в кнопках подписки, и вы сможете отслеживать конверсию.</li>
    <li>Публикуйте посты как обычно — они появятся на сайте.</li>
    <li>Ваша страница будет доступна по адресу: <code>comuna.ru/ник_канала</code>.</li>
  </ol>
</div>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
