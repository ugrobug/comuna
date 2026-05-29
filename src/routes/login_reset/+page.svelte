<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { t } from '$lib/translations'
  import { Button, TextInput, toast } from 'mono-svelte'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { confirmPasswordReset, requestPasswordReset } from '$lib/siteAuth'

  let email = ''
  let password = ''
  let passwordConfirm = ''
  let loading = false

  $: uid = $page.url.searchParams.get('uid') || ''
  $: token = $page.url.searchParams.get('token') || ''
  $: isConfirmMode = Boolean(uid && token)

  async function submit() {
    loading = true
    try {
      await requestPasswordReset(email.trim())

      toast({
        content: 'Если аккаунт найден, письмо для восстановления отправлено.',
        type: 'success',
      })
    } catch (err) {
      toast({
        content: err as any,
        type: 'error',
      })
    }
    loading = false
  }

  async function confirmReset() {
    loading = true
    try {
      if (password !== passwordConfirm) {
        throw new Error('Пароли не совпадают')
      }
      await confirmPasswordReset({ uid, token, password })
      toast({
        content: 'Пароль обновлен, вы вошли в аккаунт.',
        type: 'success',
      })
      goto('/')
    } catch (err) {
      toast({
        content: err as any,
        type: 'error',
      })
    }
    loading = false
  }
</script>

<div class="my-auto max-w-xl mx-auto flex flex-col gap-2">
  {#if isConfirmMode}
    <Header>Новый пароль</Header>
    <p>Введите новый пароль для аккаунта.</p>
    <form class="mt-2 flex flex-col gap-4" on:submit|preventDefault={confirmReset}>
      <TextInput
        bind:value={password}
        label="Новый пароль"
        type="password"
        minlength={8}
        maxlength={60}
        required
      />
      <TextInput
        bind:value={passwordConfirm}
        label="Повторите пароль"
        type="password"
        minlength={8}
        maxlength={60}
        required
      />
      <Button color="primary" size="lg" {loading} disabled={loading} submit>
        Сохранить пароль
      </Button>
    </form>
  {:else}
    <Header>{$t('routes.resetLogin.title')}</Header>
    <p>Введите email аккаунта, и мы отправим ссылку для восстановления доступа.</p>
    <form class="mt-2 flex flex-col gap-4" on:submit|preventDefault={submit}>
      <TextInput
        bind:value={email}
        label={$t('form.email')}
        type="email"
        required
        placeholder="example@example.com"
      />
      <Button color="primary" size="lg" {loading} disabled={loading} submit>
        {$t('form.submit')}
      </Button>
    </form>
  {/if}
</div>
