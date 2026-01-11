<script lang="ts">
  import { toast } from 'mono-svelte'
  import { Button, TextInput } from 'mono-svelte'
  import ErrorContainer, { clearErrorScope, pushError } from '$lib/components/error/ErrorContainer.svelte'
  import { page } from '$app/stores'
  import { register } from '$lib/siteAuth'

  export let onSuccess: () => void

  let signupData = {
    username: '',
    email: '',
    password: '',
    passwordConfirm: '',
    loading: false,
  }

  async function handleSubmit() {
    signupData.loading = true
    clearErrorScope($page.route.id)

    try {
      if (signupData.password !== signupData.passwordConfirm) {
        throw new Error('Пароли не совпадают')
      }

      await register({
        username: signupData.username.trim(),
        email: signupData.email.trim() || undefined,
        password: signupData.password,
      })

      toast({ content: 'Регистрация успешна', type: 'success' })
      onSuccess()
    } catch (error) {
      pushError({
        message: (error as Error)?.message ?? 'Не удалось зарегистрироваться',
        scope: $page.route.id!,
      })
    }

    signupData.loading = false
  }
</script>

<form on:submit|preventDefault={handleSubmit} class="flex flex-col gap-5">
  <ErrorContainer class="pt-2" scope={$page.route.id} />

  <TextInput
    bind:value={signupData.username}
    label="Имя пользователя"
    placeholder="yourname"
    class="w-full"
    required
    minlength={3}
    maxlength={30}
  />

  <TextInput
    id="email"
    type="email"
    bind:value={signupData.email}
    label="Электронная почта"
    class="w-full"
  />

  <div class="flex flex-row gap-2">
    <TextInput
      id="password"
      bind:value={signupData.password}
      label="Пароль"
      type="password"
      minlength={8}
      maxlength={60}
      required
      class="w-full"
    />
    <TextInput
      id="password_confirm"
      bind:value={signupData.passwordConfirm}
      label="Повторите пароль"
      type="password"
      minlength={8}
      maxlength={60}
      required
      class="w-full"
    />
  </div>

  <Button
    loading={signupData.loading}
    disabled={signupData.loading}
    color="primary"
    size="lg"
    submit
  >
    Зарегистрироваться
  </Button>
</form>
