<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { Button } from 'mono-svelte'

  export let ref: string = '/'

  let loginOpen = true

  $: returnTo =
    $page.url.searchParams.get('next') ||
    $page.url.searchParams.get('redirect') ||
    ref ||
    '/'

  function handleSuccess() {
    goto(returnTo)
  }
</script>

<svelte:head>
  <title>Вход</title>
</svelte:head>

<div class="mx-auto my-auto flex w-full max-w-xl flex-col items-center gap-5 px-4 py-10 text-center">
  <slot />
  <div class="flex flex-col gap-2">
    <p class="text-sm font-medium uppercase tracking-wide text-slate-500 dark:text-zinc-400">
      Тамбур
    </p>
    <h1 class="text-3xl font-roboto font-medium text-slate-950 dark:text-zinc-50">
      Вход в аккаунт
    </h1>
    <p class="text-sm text-slate-600 dark:text-zinc-400">
      Войдите через стандартную форму сайта.
    </p>
  </div>
  <Button color="primary" size="lg" on:click={() => (loginOpen = true)}>
    Войти
  </Button>
</div>

<LoginModal bind:open={loginOpen} initialMode="login" on:success={handleSuccess} />
