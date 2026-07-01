<script lang="ts">
  import TelegramLoginButton from '$lib/components/telegram/TelegramLoginButton.svelte'

  export let onSuccess: (() => void) | null = null
  export let label = ''
  export let helperText = ''
  export let active = true
  export let disabled = false
  export let privacyAccepted = false
  export let authIntent: 'login' | 'signup' = 'login'
</script>

<TelegramLoginButton {onSuccess} {label} {helperText} {active} {disabled} {privacyAccepted} {authIntent} />
