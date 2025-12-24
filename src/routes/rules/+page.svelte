<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import SectionTitle from '$lib/components/ui/SectionTitle.svelte'
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Правила</h1>
  </Header>

  <div class="flex flex-col gap-3 text-base leading-relaxed">
    <p>
      Мы публикуем материалы из Telegram‑каналов в открытом доступе. Чтобы
      сохранить качество и безопасность, мы просим соблюдать простые правила.
    </p>
  </div>

  <SectionTitle class="text-lg font-semibold">Что нельзя</SectionTitle>
  <ul class="list-disc pl-6 space-y-2 text-base leading-relaxed">
    <li>Нарушать законы РФ и других стран.</li>
    <li>Публиковать экстремизм, угрозы, призывы к насилию.</li>
    <li>Публиковать спам, мошенничество и фишинг.</li>
    <li>Нарушать авторские права.</li>
  </ul>

  <SectionTitle class="text-lg font-semibold">Модерация</SectionTitle>
  <p class="text-base leading-relaxed">
    Мы можем скрывать отдельные публикации или полностью блокировать каналы,
    нарушающие правила. Для вопросов и апелляций — напишите нам.
  </p>
</div>
