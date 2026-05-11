<script>
  import { Check, Icon } from 'svelte-hero-icons'
</script>

<div class="flex flex-col items-center h-max my-auto gap-2">
  <div
    class="rounded-full bg-green-200 dark:bg-green-700 text-green-600 dark:text-green-200 p-3"
  >
    <Icon src={Check} size="32" mini />
  </div>
  <h1 class="text-green-800 dark:text-green-200 text-2xl font-semibold">
    Почта подтверждена
  </h1>
  <p class="text-green-800 dark:text-green-200">
    Теперь этот email привязан к вашему аккаунту Tambur.
  </p>
</div>
