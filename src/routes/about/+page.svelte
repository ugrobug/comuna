<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import SectionTitle from '$lib/components/ui/SectionTitle.svelte'
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
