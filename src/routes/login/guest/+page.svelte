<script lang="ts">
  import { Button } from 'mono-svelte'
</script>

<div class="mx-auto my-auto flex w-full max-w-xl flex-col items-center gap-4 px-4 py-10 text-center">
  <slot />
  <h1 class="text-2xl font-roboto font-medium text-slate-950 dark:text-zinc-50">
    Гостевой вход отключен
  </h1>
  <p class="text-sm text-slate-600 dark:text-zinc-400">
    На Тамбуре можно работать только через авторизованный аккаунт.
  </p>
  <Button href="/login" color="primary" size="lg">Войти</Button>
</div>
