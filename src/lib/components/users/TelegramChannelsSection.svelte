<script lang="ts">
  import type { SiteUser } from '$lib/siteAuth'
  import { t } from '$lib/translations'
  import { Button } from 'mono-svelte'
  import { createEventDispatcher } from 'svelte'

  export let siteUser: SiteUser | null = null
  export let verificationCode = ''
  export let verificationCodeLoading = false
  export let verificationCodeError = ''
  export let creatingComunByAuthorId: number | null = null

  const dispatch = createEventDispatcher<{
    loadCode: void
    createComun: { id?: number; username: string }
  }>()
</script>

<div class="flex flex-col gap-4">
  <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
    <h3 class="text-base font-semibold mb-2">{$t('settings.telegramChannels.adminConfirmTitle')}</h3>
    <p class="text-sm text-slate-500 dark:text-zinc-400">
      {$t('settings.telegramChannels.adminConfirmDescription')}
    </p>
    <div class="mt-4 flex flex-wrap items-center gap-3">
      <Button
        size="sm"
        color="primary"
        on:click={() => dispatch('loadCode')}
        loading={verificationCodeLoading}
        disabled={verificationCodeLoading}
      >
        {$t('settings.telegramChannels.getCode')}
      </Button>
      {#if verificationCode}
        <div class="rounded-lg bg-slate-100 dark:bg-zinc-900 px-4 py-2 text-sm font-mono">
          {verificationCode}
        </div>
      {/if}
    </div>
    {#if verificationCodeError}
      <p class="text-sm text-red-600 mt-3">{verificationCodeError}</p>
    {/if}
    <p class="text-sm text-slate-500 dark:text-zinc-400 mt-4">
      {$t('settings.telegramChannels.sendCodeToBot')} @comuna_tg_bot.
    </p>
  </div>

  <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
    <h3 class="text-base font-semibold mb-2">{$t('settings.telegramChannels.confirmedTitle')}</h3>
    {#if siteUser?.is_author && siteUser.authors.length}
      <ul class="flex flex-col gap-3 text-sm">
        {#each siteUser.authors as author}
          <li class="flex flex-col gap-1">
            <div>
              @{author.username}
              {#if author.title}
                <span class="text-slate-500 dark:text-zinc-400">— {author.title}</span>
              {/if}
            </div>
            <div class="text-xs text-slate-500 dark:text-zinc-400">
              {$t('settings.telegramChannels.mode')}: {author.auto_publish === false ? $t('settings.telegramChannels.modeReview') : $t('settings.telegramChannels.modeAuto')}
              <span class="mx-1">•</span>
              {$t('settings.telegramChannels.delay')}: {author.publish_delay_days ? `${author.publish_delay_days} ${$t('settings.telegramChannels.delayDaysSuffix')}` : $t('settings.telegramChannels.noDelay')}
              <span class="mx-1">•</span>
              {$t('settings.telegramChannels.comments')}: {author.notify_comments ? $t('settings.telegramChannels.commentsNotify') : $t('settings.telegramChannels.commentsSilent')}
              {#if author.author_rating !== undefined}
                <span class="mx-1">•</span>
                {$t('settings.telegramChannels.rating')}: {author.author_rating}
              {/if}
            </div>
            {#if author.invite_url}
              <a
                class="text-xs text-blue-600 hover:underline dark:text-blue-400"
                href={author.invite_url}
                target="_blank"
                rel="noreferrer"
              >
                {$t('settings.telegramChannels.inviteLink')}
              </a>
            {/if}
            <div class="mt-2 flex flex-wrap items-center gap-2">
              {#if author.linked_comun_slug}
                <a
                  class="inline-flex items-center rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                  href={`/comuns/${author.linked_comun_slug}`}
                >
                  {author.linked_comun_name ? `${$t('settings.telegramChannels.openCommunity')} ${author.linked_comun_name}` : $t('settings.telegramChannels.openCommunity')}
                </a>
                <a
                  class="inline-flex items-center rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                  href={`/comuns/${author.linked_comun_slug}/settings`}
                >
                  {$t('settings.telegramChannels.communitySettings')}
                </a>
              {:else}
                <Button
                  size="sm"
                  on:click={() => dispatch('createComun', author)}
                  loading={creatingComunByAuthorId === author.id}
                  disabled={creatingComunByAuthorId !== null}
                >
                  {$t('settings.telegramChannels.createFromChannel')}
                </Button>
              {/if}
            </div>
          </li>
        {/each}
      </ul>
    {:else}
      <p class="text-sm text-slate-500 dark:text-zinc-400">{$t('settings.telegramChannels.emptyConfirmed')}</p>
    {/if}
  </div>
</div>
