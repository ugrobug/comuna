<script lang="ts">
  import NotificationHistoryPanel from '$lib/components/notifications/NotificationHistoryPanel.svelte'
  import { siteUser } from '$lib/siteAuth'
  import { t } from '$lib/translations'
</script>

<svelte:head>
  <title>{$t('settings.notifications.title')}</title>
  <meta name="robots" content="noindex, nofollow" />
</svelte:head>

<div class="mx-auto flex w-full max-w-3xl flex-col gap-5">
  <h1 class="text-2xl font-semibold text-slate-950 dark:text-zinc-50">
    {$t('settings.notifications.title')}
  </h1>

  {#if $siteUser}
    <section class="rounded-lg border border-slate-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900 sm:p-5">
      <NotificationHistoryPanel />
    </section>
  {:else}
    <section class="rounded-lg border border-slate-200 bg-white p-5 text-center dark:border-zinc-800 dark:bg-zinc-900">
      <a
        href="/account?next=%2Fnotifications"
        class="inline-flex min-h-10 items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-700"
      >
        {$t('account.login')}
      </a>
    </section>
  {/if}
</div>
