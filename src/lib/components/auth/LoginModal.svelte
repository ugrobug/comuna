<script lang="ts">
  import { toast } from 'mono-svelte'
  import { t } from '$lib/translations'
  import { Button, TextInput, Modal } from 'mono-svelte'
  import ErrorContainer, { clearErrorScope, pushError } from '$lib/components/error/ErrorContainer.svelte'
  import { page } from '$app/stores'
  import TelegramLoginButton from './TelegramLoginButton.svelte'
  import VkLoginButton from './VkLoginButton.svelte'
  import { login } from '$lib/siteAuth'

  export let open = false

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
    loginData = {
      username: '',
      password: '',
      loading: false,
    }
  }
</script>

<Modal bind:open dismissable on:close={handleModalClose}>
  <h2 class="text-xl font-roboto font-medium text-center">
    {$t('auth.login')}
  </h2>

  <div class="flex flex-col gap-3">
    <TelegramLoginButton onSuccess={handleSuccessfulAuth} />
    <VkLoginButton onSuccess={handleSuccessfulAuth} />
  </div>

  <div class="flex items-center gap-3 text-xs text-slate-400 dark:text-zinc-500 mt-3">
    <span class="h-px flex-1 bg-slate-200 dark:bg-zinc-800" />
    или
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
</Modal>
