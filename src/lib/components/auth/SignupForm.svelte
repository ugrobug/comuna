<script lang="ts">
  import { toast } from 'mono-svelte'
  import { Button, TextInput } from 'mono-svelte'
  import ErrorContainer, { clearErrorScope, pushError } from '$lib/components/error/ErrorContainer.svelte'
  import { page } from '$app/stores'
  import { register } from '$lib/siteAuth'
  import { t } from '$lib/translations'

  export let onSuccess: () => void
  export let externalPrivacyAccepted: boolean | null = null
  export let registrationSource = ''
  export let registrationPath = ''

  let signupData = {
    username: '',
    email: '',
    password: '',
    passwordConfirm: '',
    privacyAccepted: false,
    loading: false,
  }

  async function handleSubmit() {
    signupData.loading = true
    clearErrorScope($page.route.id)

    try {
      const privacyAccepted = externalPrivacyAccepted ?? signupData.privacyAccepted
      if (signupData.password !== signupData.passwordConfirm) {
        throw new Error($t('site.authModal.passwordMismatch'))
      }
      if (!privacyAccepted) {
        throw new Error($t('site.authModal.privacyRequired'))
      }

      await register({
        username: signupData.username.trim(),
        email: signupData.email.trim(),
        password: signupData.password,
        privacy_accepted: privacyAccepted,
        registration_source: registrationSource,
        registration_path: registrationPath,
      })

      toast({ content: $t('site.authModal.signupSuccess'), type: 'success' })
      onSuccess()
    } catch (error) {
      pushError({
        message: (error as Error)?.message ?? $t('site.authModal.signupError'),
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
    label={$t('site.authModal.username')}
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
    label={$t('site.authModal.email')}
    class="w-full"
    required
  />

  <div class="flex flex-row gap-2">
    <TextInput
      id="password"
      bind:value={signupData.password}
      label={$t('site.authModal.password')}
      type="password"
      minlength={8}
      maxlength={60}
      required
      class="w-full"
    />
    <TextInput
      id="password_confirm"
      bind:value={signupData.passwordConfirm}
      label={$t('site.authModal.passwordConfirm')}
      type="password"
      minlength={8}
      maxlength={60}
      required
      class="w-full"
    />
  </div>

  {#if externalPrivacyAccepted === null}
    <label class="flex items-start gap-3 text-sm text-slate-600 dark:text-zinc-300">
      <input
        bind:checked={signupData.privacyAccepted}
        type="checkbox"
        class="mt-1 h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900"
        required
      />
      <span>
        {$t('site.authModal.privacyAgreePrefix')}
        <a
          href="/privacy"
          target="_blank"
          rel="noopener noreferrer"
          class="text-blue-600 hover:underline dark:text-blue-400"
        >
          {$t('site.authModal.privacyPolicy')}
        </a>
      </span>
    </label>
  {/if}

  <Button
    loading={signupData.loading}
    disabled={signupData.loading}
    color="primary"
    size="lg"
    submit
  >
    {$t('site.authModal.signupSubmit')}
  </Button>
</form>
