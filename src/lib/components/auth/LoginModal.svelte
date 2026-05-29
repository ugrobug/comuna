<script lang="ts">
  import { toast } from 'mono-svelte'
  import { Button, TextInput, Modal } from 'mono-svelte'
  import ErrorContainer, { clearErrorScope, pushError } from '$lib/components/error/ErrorContainer.svelte'
  import { page } from '$app/stores'
  import VkLoginButton from './VkLoginButton.svelte'
  import { login } from '$lib/siteAuth'
  import type { ComponentType } from 'svelte'
  import SignupForm from './SignupForm.svelte'
  import ResetPasswordForm from './ResetPasswordForm.svelte'
  import { Envelope, Icon } from 'svelte-hero-icons'
  import { createEventDispatcher } from 'svelte'

  export let open = false
  export let initialMode: 'login' | 'signup' = 'login'
  export let registrationSource = ''
  export let registrationPath = ''
  const dispatch = createEventDispatcher<{ success: void }>()
  let authMode: 'login' | 'signup' | 'reset' = initialMode
  let wasOpen = false
  let telegramButtonModulePromise: Promise<{ default: ComponentType }> | null = null
  let signupPrivacyAccepted = false
  let signupMethod: 'options' | 'email' = 'options'

  let loginData = {
    username: '',
    password: '',
    loading: false,
  }

  function handleSuccessfulAuth() {
    open = false
    dispatch('success')
    loginData = {
      username: '',
      password: '',
      loading: false,
    }
    signupPrivacyAccepted = false
    signupMethod = 'options'
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
    authMode = initialMode
    loginData = {
      username: '',
      password: '',
      loading: false,
    }
    signupPrivacyAccepted = false
    signupMethod = 'options'
  }

  $: if (open && !wasOpen) {
    authMode = initialMode
    signupMethod = 'options'
    wasOpen = true
    telegramButtonModulePromise ??= import('$lib/components/telegram/TelegramLoginButton.svelte')
  }

  $: if (!open && wasOpen) {
    wasOpen = false
  }

  $: if (authMode !== 'signup' && signupMethod !== 'options') {
    signupMethod = 'options'
  }

  const requireSignupPrivacyAcceptance = (onAccepted: () => void) => {
    if (signupPrivacyAccepted) {
      onAccepted()
      return
    }

    toast({
      content: 'Сначала примите политику обработки персональных данных.',
      type: 'info',
    })
  }
</script>

<Modal bind:open dismissable on:close={handleModalClose}>
  <div class="w-full max-w-[30rem]">
    <h2 class="text-xl font-roboto font-medium text-center text-slate-900 dark:text-zinc-100">
      Вход и регистрация
    </h2>
    <p class="mt-1 text-center text-sm text-slate-500 dark:text-zinc-400">
      Войдите в существующий аккаунт или зарегистрируйтесь удобным способом
    </p>

    <div class="mt-4 grid grid-cols-2 rounded-xl bg-slate-100 p-1 dark:bg-zinc-900">
      <button
        type="button"
        class={`rounded-lg px-3 py-2 text-sm font-medium transition ${
          authMode === 'login'
            ? 'bg-white text-slate-900 shadow-sm dark:bg-zinc-800 dark:text-zinc-100'
            : 'text-slate-500 dark:text-zinc-400'
        }`}
        on:click={() => {
          authMode = 'login'
          signupMethod = 'options'
        }}
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
        on:click={() => {
          authMode = 'signup'
          signupMethod = 'options'
        }}
      >
        Регистрация
      </button>
    </div>

    {#if authMode === 'login'}
      <div class="mt-4 flex flex-col gap-3">
        {#if telegramButtonModulePromise}
          {#await telegramButtonModulePromise then module}
            <svelte:component
              this={module.default}
              onSuccess={handleSuccessfulAuth}
              active={open}
              authIntent="login"
              privacyAccepted={false}
              registrationSource=""
              registrationPath=""
              label="Войти через Telegram"
            />
          {/await}
        {/if}
        <VkLoginButton
          onSuccess={handleSuccessfulAuth}
          authIntent="login"
          privacyAccepted={false}
          registrationSource=""
          registrationPath=""
          label="Войти через VK"
        />
      </div>

      <div class="flex items-center gap-3 text-xs text-slate-400 dark:text-zinc-500 mt-4">
        <span class="h-px flex-1 bg-slate-200 dark:bg-zinc-800"></span>
        или по почте
        <span class="h-px flex-1 bg-slate-200 dark:bg-zinc-800"></span>
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
        <button
          type="button"
          class="text-sm text-blue-600 hover:underline dark:text-blue-400"
          on:click={() => (authMode = 'reset')}
        >
          Забыли пароль?
        </button>
      </form>
    {:else if authMode === 'reset'}
      <div class="mt-4">
        <ResetPasswordForm onBack={() => (authMode = 'login')} />
      </div>
    {:else}
      <div class="mt-3 flex flex-col gap-3 rounded-xl border border-slate-200 bg-slate-50 px-4 py-4 text-sm text-slate-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-300">
        <label class="flex items-start gap-3">
          <input
            bind:checked={signupPrivacyAccepted}
            type="checkbox"
            class="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <span>
            Я согласен с
            <a
              href="/privacy"
              target="_blank"
              rel="noopener noreferrer"
              class="text-blue-600 hover:underline dark:text-blue-400"
            >
              политикой обработки персональных данных
            </a>
          </span>
        </label>
      </div>

      {#if signupMethod === 'email'}
        <div class="mt-4 flex flex-col gap-3">
          <button
            type="button"
            class="w-fit text-sm text-slate-500 transition hover:text-slate-900 dark:text-zinc-400 dark:hover:text-zinc-100"
            on:click={() => (signupMethod = 'options')}
          >
            ← Назад к способам регистрации
          </button>

          <SignupForm
            onSuccess={handleSuccessfulAuth}
            externalPrivacyAccepted={signupPrivacyAccepted}
            registrationSource={registrationSource}
            registrationPath={registrationPath}
          />
        </div>
      {:else}
        <div class="mt-4 flex flex-col gap-3">
          <button
            type="button"
            class="inline-flex w-full items-center justify-start gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm font-medium text-slate-900 transition dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-100"
            class:opacity-60={!signupPrivacyAccepted}
            class:hover:border-slate-300={signupPrivacyAccepted}
            class:hover:bg-slate-50={signupPrivacyAccepted}
            class:dark:hover:border-zinc-700={signupPrivacyAccepted}
            class:dark:hover:bg-zinc-900={signupPrivacyAccepted}
            on:click={() => requireSignupPrivacyAcceptance(() => (signupMethod = 'email'))}
          >
            <span class="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-700 dark:bg-zinc-800 dark:text-zinc-200">
              <Icon src={Envelope} size="18" solid />
            </span>
            <span>Зарегистрироваться через почту</span>
          </button>
          {#if telegramButtonModulePromise}
            {#await telegramButtonModulePromise then module}
              <svelte:component
                this={module.default}
                onSuccess={handleSuccessfulAuth}
                active={open}
                authIntent="signup"
                disabled={!signupPrivacyAccepted}
                privacyAccepted={signupPrivacyAccepted}
                registrationSource={registrationSource}
                registrationPath={registrationPath}
                label="Зарегистрироваться через Telegram"
              />
            {/await}
          {/if}
          <VkLoginButton
            onSuccess={handleSuccessfulAuth}
            authIntent="signup"
            disabled={!signupPrivacyAccepted}
            privacyAccepted={signupPrivacyAccepted}
            registrationSource={registrationSource}
            registrationPath={registrationPath}
            label="Зарегистрироваться через VK"
          />
        </div>
      {/if}
    {/if}
  </div>
</Modal>
