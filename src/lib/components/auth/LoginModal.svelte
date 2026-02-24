<script lang="ts">
  import { toast } from 'mono-svelte'
  import { Button, TextInput, Modal } from 'mono-svelte'
  import ErrorContainer, { clearErrorScope, pushError } from '$lib/components/error/ErrorContainer.svelte'
  import { page } from '$app/stores'
  import TelegramLoginButton from './TelegramLoginButton.svelte'
  import VkLoginButton from './VkLoginButton.svelte'
  import { login } from '$lib/siteAuth'

  export let open = false
  let authMode: 'login' | 'signup' = 'login'

  let loginData = {
    username: '',
    password: '',
    loading: false,
  }

  function handleSuccessfulAuth() {
    open = false
    loginData = {
      username: '',
      password: '',
      loading: false,
    }
  }

  async function handleLogin() {
    loginData.loading = true
    clearErrorScope($page.route.id)

    try {
      await login(loginData.username.trim(), loginData.password)
      toast({ content: 'Вы успешно вошли', type: 'success' })
      handleSuccessfulAuth()
    } catch (error) {
      pushError({
        message: (error as Error)?.message ?? 'Не удалось войти',
        scope: $page.route.id!,
      })
    }

    loginData.loading = false
  }

  function handleModalClose() {
    open = false
    authMode = 'login'
    loginData = {
      username: '',
      password: '',
      loading: false,
    }
  }
</script>

<Modal bind:open dismissable on:close={handleModalClose}>
  <div class="w-full max-w-[30rem]">
    <h2 class="text-xl font-roboto font-medium text-center text-slate-900 dark:text-zinc-100">
      Вход и регистрация
    </h2>
    <p class="mt-1 text-center text-sm text-slate-500 dark:text-zinc-400">
      Войдите в существующий аккаунт или зарегистрируйтесь через Telegram / VK
    </p>

    <div class="mt-4 grid grid-cols-2 rounded-xl bg-slate-100 p-1 dark:bg-zinc-900">
      <button
        type="button"
        class={`rounded-lg px-3 py-2 text-sm font-medium transition ${
          authMode === 'login'
            ? 'bg-white text-slate-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100'
            : 'text-slate-500 dark:text-zinc-400'
        }`}
        on:click={() => (authMode = 'login')}
      >
        Авторизация
      </button>
      <button
        type="button"
        class={`rounded-lg px-3 py-2 text-sm font-medium transition ${
          authMode === 'signup'
            ? 'bg-white text-slate-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100'
            : 'text-slate-500 dark:text-zinc-400'
        }`}
        on:click={() => (authMode = 'signup')}
      >
        Регистрация
      </button>
    </div>

    <div class="mt-4 flex flex-col gap-3">
      <TelegramLoginButton
        onSuccess={handleSuccessfulAuth}
        active={open}
        label={authMode === 'signup' ? 'Зарегистрироваться через Telegram' : 'Войти через Telegram'}
      />
      <VkLoginButton
        onSuccess={handleSuccessfulAuth}
        label={authMode === 'signup' ? 'Зарегистрироваться через VK' : 'Войти через VK'}
      />
    </div>

    {#if authMode === 'login'}
      <div class="flex items-center gap-3 text-xs text-slate-400 dark:text-zinc-500 mt-4">
        <span class="h-px flex-1 bg-slate-200 dark:bg-zinc-800" />
        или по почте
        <span class="h-px flex-1 bg-slate-200 dark:bg-zinc-800" />
      </div>

      <form on:submit|preventDefault={handleLogin} class="flex flex-col gap-5 mt-3">
        <ErrorContainer class="pt-2" scope={$page.route.id} />

        <TextInput
          id="username"
          bind:value={loginData.username}
          label="Email или имя пользователя"
          class="flex-1"
          required
        />

        <TextInput
          id="password"
          bind:value={loginData.password}
          label="Пароль"
          type="password"
          minlength={8}
          maxlength={60}
          required
          class="w-full"
        />

        <Button
          loading={loginData.loading}
          disabled={loginData.loading}
          color="primary"
          size="lg"
          submit
        >
          Войти
        </Button>
      </form>
    {:else}
      <div class="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
        Регистрация по email отключена. Используйте Telegram или VK.
      </div>
    {/if}
  </div>
</Modal>
