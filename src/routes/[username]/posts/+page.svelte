<script lang="ts">
  import { t } from '$lib/translations'

  export let data
  $: void data
</script>

<div class="text-base text-slate-500">{$t('site.authorProfile.redirecting')}</div>
