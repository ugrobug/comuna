<script lang="ts">
  import { toast } from 'mono-svelte'
  import { t } from '$lib/translations'
  import { Button, TextInput, Modal } from 'mono-svelte'
  import { Icon, Identification } from 'svelte-hero-icons'
  import ErrorContainer, { clearErrorScope, pushError } from '$lib/components/error/ErrorContainer.svelte'
  import { page } from '$app/stores'
  import SignupForm from './SignupForm.svelte'
  import { login } from '$lib/siteAuth'

  export let open = false

  let isSignupMode = false

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

  function handleSignupClick(e: Event) {
    e.stopPropagation()
    isSignupMode = true
  }

  function handleLoginClick(e: Event) {
    e.stopPropagation()
    isSignupMode = false
  }

  function handleModalClose() {
    open = false
    isSignupMode = false
    loginData = {
      username: '',
      password: '',
      loading: false,
    }
  }
</script>

<Modal bind:open dismissable on:close={handleModalClose}>
  {#if isSignupMode}
    <SignupForm onSuccess={handleSuccessfulAuth} />
    <hr class="border-slate-200 dark:border-zinc-800 mt-5" />
    <div class="flex flex-row items-center justify-center mt-5">
      <Button
        rounding="pill"
        color="ghost"
        on:click={handleLoginClick}
        type="button"
        element="button"
      >
        У вас уже есть аккаунт?
      </Button>
    </div>
  {:else}
    <h2 class="text-xl font-roboto font-medium text-center">
      {$t('auth.login')}
    </h2>
    <form on:submit|preventDefault={handleLogin} class="flex flex-col gap-5">
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
    <hr class="border-slate-200 dark:border-zinc-800" />
    <div class="flex flex-row items-center justify-center gap-4 mt-5">
      <Button
        rounding="pill"
        color="ghost"
        on:click={handleSignupClick}
        type="button"
        element="button"
      >
        <Icon src={Identification} mini size="16" />
        Регистрация
      </Button>
    </div>
  {/if}
</Modal>
