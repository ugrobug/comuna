<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import SectionTitle from '$lib/components/ui/SectionTitle.svelte'
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Реклама</h1>
  </Header>

  <div class="flex flex-col gap-3 text-base leading-relaxed">
    <p>
      Мы открыты к рекламным интеграциям и партнерствам. Реклама показывается на
      страницах сайта и помогает авторам получать больше внимания к контенту.
    </p>
  </div>

  <SectionTitle class="text-lg font-semibold">Форматы</SectionTitle>
  <ul class="list-disc pl-6 space-y-2 text-base leading-relaxed">
    <li>Спонсорские блоки на страницах статей.</li>
    <li>Интеграции в подборках и разделах сайта.</li>
    <li>Спецпроекты под вашу задачу.</li>
  </ul>

  <SectionTitle class="text-lg font-semibold">Как связаться</SectionTitle>
  <p class="text-base leading-relaxed">
    Напишите нам, и мы подберем оптимальный формат под ваши цели.
  </p>
</div>
