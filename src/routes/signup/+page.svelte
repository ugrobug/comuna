<script lang="ts">
  import { goto } from '$app/navigation'
  import { Button } from 'mono-svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { t } from '$lib/translations'

  let signupOpen = true
</script>

<svelte:head>
  <title>{$t('site.authModal.signupTab')}</title>
</svelte:head>

<div class="mx-auto my-auto flex w-full max-w-xl flex-col items-center gap-5 px-4 py-10 text-center">
  <p class="text-sm font-medium uppercase text-slate-500 dark:text-zinc-400">Tambur</p>
  <h1 class="text-3xl font-roboto font-medium text-slate-950 dark:text-zinc-50">
    {$t('site.authModal.signupTab')}
  </h1>
  <Button color="primary" size="lg" on:click={() => (signupOpen = true)}>
    {$t('site.authModal.signupSubmit')}
  </Button>
</div>

<LoginModal
  bind:open={signupOpen}
  initialMode="signup"
  registrationSource="signup_page"
  registrationPath="/signup"
  on:success={() => goto('/')}
/>
