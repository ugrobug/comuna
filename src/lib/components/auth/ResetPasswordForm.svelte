<script lang="ts">
  import { Button, TextInput } from 'mono-svelte'
  import { t } from '$lib/translations'
  import ErrorContainer, { clearErrorScope, pushError } from '$lib/components/error/ErrorContainer.svelte'
  import { page } from '$app/stores'
  import { requestPasswordReset } from '$lib/siteAuth'
  import { toast } from 'mono-svelte'

  export let onBack: () => void

  let resetData = {
    email: '',
    loading: false,
  }

  async function handleReset() {
    resetData.loading = true
    clearErrorScope($page.route.id)

    try {
      await requestPasswordReset(resetData.email.trim())

      toast({ content: 'Если аккаунт найден, письмо для восстановления отправлено.', type: 'success' })
      onBack()
    } catch (error) {
      pushError({
        message: (error as Error)?.message ?? 'Не удалось отправить письмо',
        scope: $page.route.id!,
      })
    }
    resetData.loading = false
  }
</script>

<form on:submit|preventDefault={handleReset} class="flex flex-col gap-5">
  <ErrorContainer class="pt-2" scope={$page.route.id} />

  <div class="flex flex-row w-full items-center gap-2">
    <TextInput
      id="email"
      type="email"
      bind:value={resetData.email}
      label={$t('form.email')}
      class="flex-1"
      required
    />
  </div>

  <Button
    loading={resetData.loading}
    disabled={resetData.loading}
    color="primary"
    size="lg"
    submit
  >
    {$t('form.submit')}
  </Button>

  <hr class="border-slate-200 dark:border-zinc-800" />
  
  <div class="flex flex-row items-center justify-center">
    <Button 
      rounding="pill" 
      color="ghost" 
      on:click={onBack}
      type="button"
      element="button"
    >
      {$t('common.back')}
    </Button>
  </div>
</form> 
