<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import SectionTitle from '$lib/components/ui/SectionTitle.svelte'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'

  const title = `О проекте — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  const description =
    'Comuna помогает Telegram-каналам получать органический трафик из поисковых систем за счет публикации контента на сайте.'
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">О проекте</h1>
  </Header>

  <div class="flex flex-col gap-3 text-base leading-relaxed">
    <p>
      Мы помогаем авторам Telegram‑каналов получать органический трафик из
      поисковых систем. Контент каналов почти не индексируется, поэтому новые
      читатели вас не находят.
    </p>
    <p>
      Наш сайт публикует материалы из вашего канала и делает их доступными для
      Google и Яндекса. Люди находят статьи, переходят на канал и подписываются.
    </p>
  </div>

  <SectionTitle class="text-lg font-semibold">Как это работает</SectionTitle>
  <ol class="list-decimal pl-6 space-y-2 text-base leading-relaxed">
    <li>Вы добавляете нашего бота в админы своего канала.</li>
    <li>Мы автоматически создаем страницы с вашими постами.</li>
    <li>Поисковые системы индексируют страницы.</li>
    <li>Читатели приходят на сайт и подписываются на ваш канал.</li>
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
