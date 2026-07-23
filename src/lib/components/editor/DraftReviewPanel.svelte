<script lang="ts">
  import {
    replyToDraftBlockComment,
    setDraftBlockCommentResolved,
    type DraftBlockCommentThread,
  } from '$lib/siteAuth'
  import { locale, t } from '$lib/translations'
  import { Button } from 'mono-svelte'
  import { Icon, XMark } from 'svelte-hero-icons'
  import { createEventDispatcher } from 'svelte'

  export let shareToken = ''
  export let blockId = ''
  export let threads: DraftBlockCommentThread[] = []

  const dispatch = createEventDispatcher<{ close: void }>()

  let replyDrafts: Record<number, string> = {}
  let busyThreadId: number | null = null
  let errorMessage = ''

  $: selectedThreads = threads.filter((thread) => thread.block_id === blockId)

  const formatDate = (value: string) => {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return new Intl.DateTimeFormat($locale || 'ru', {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  }

  const displayName = (thread: DraftBlockCommentThread) => {
    const user = thread.comments[0]?.user
    return user?.display_name || user?.username || $t('site.draftReview.user')
  }

  const addReply = async (thread: DraftBlockCommentThread) => {
    const body = String(replyDrafts[thread.id] || '').trim()
    if (!shareToken || !body || busyThreadId !== null) return

    busyThreadId = thread.id
    errorMessage = ''
    try {
      const comment = await replyToDraftBlockComment(shareToken, thread.id, body)
      threads = threads.map((item) =>
        item.id === thread.id ? { ...item, comments: [...item.comments, comment] } : item
      )
      replyDrafts = { ...replyDrafts, [thread.id]: '' }
    } catch (error) {
      errorMessage = (error as Error)?.message || $t('site.draftReview.saveError')
    } finally {
      busyThreadId = null
    }
  }

  const toggleResolved = async (thread: DraftBlockCommentThread) => {
    if (!shareToken || !thread.can_resolve || busyThreadId !== null) return

    busyThreadId = thread.id
    errorMessage = ''
    try {
      const updated = await setDraftBlockCommentResolved(
        shareToken,
        thread.id,
        !thread.resolved_at
      )
      threads = threads.map((item) => (item.id === updated.id ? updated : item))
    } catch (error) {
      errorMessage = (error as Error)?.message || $t('site.draftReview.saveError')
    } finally {
      busyThreadId = null
    }
  }
</script>

<aside class="draft-review-panel min-w-0 scroll-mt-20 lg:sticky lg:top-20">
  <div class="flex items-start justify-between gap-3 border-b border-slate-200 pb-3 dark:border-zinc-800">
    <div class="min-w-0">
      <h2 class="text-base font-bold text-slate-900 dark:text-zinc-100">
        {$t('site.draftReview.title')}
      </h2>
      <p class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
        {$t('site.draftReview.selectedBlock')}
      </p>
    </div>
    <button
      type="button"
      class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
      aria-label={$t('site.draftReview.close')}
      on:click={() => dispatch('close')}
    >
      <Icon src={XMark} size="18" mini />
    </button>
  </div>

  {#if errorMessage}
    <p class="mt-3 text-sm text-red-600 dark:text-red-400">{errorMessage}</p>
  {/if}

  <div>
    {#each selectedThreads as thread (thread.id)}
      <article
        id={`draft-comment-${thread.id}`}
        class:opacity-65={Boolean(thread.resolved_at)}
        class="border-b border-slate-200 py-4 last:border-b-0 dark:border-zinc-800"
      >
        <div class="mb-3 flex items-center gap-2">
          {#if thread.comments[0]?.user.avatar_url}
            <img
              src={thread.comments[0].user.avatar_url}
              alt=""
              class="h-7 w-7 shrink-0 rounded-full object-cover"
            />
          {:else}
            <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs font-bold text-slate-600 dark:bg-zinc-700 dark:text-zinc-200">
              {displayName(thread).slice(0, 1).toUpperCase()}
            </span>
          {/if}
          <span class="min-w-0 flex-1">
            <span class="block truncate text-sm font-semibold text-slate-900 dark:text-zinc-100">
              {displayName(thread)}
            </span>
            <span class="block text-xs text-slate-500 dark:text-zinc-400">
              {formatDate(thread.created_at)}
            </span>
          </span>
          {#if thread.resolved_at}
            <span class="text-xs font-semibold text-emerald-700 dark:text-emerald-400">
              {$t('site.draftReview.resolved')}
            </span>
          {/if}
        </div>

        {#if !thread.block_exists}
          <p class="mb-2 text-xs text-amber-700 dark:text-amber-400">
            {$t('site.draftReview.blockRemoved')}
          </p>
        {/if}

        <div class="space-y-3">
          {#each thread.comments as comment}
            <div class="text-sm">
              <div class="mb-1 flex items-baseline justify-between gap-2">
                <span class="font-semibold text-slate-800 dark:text-zinc-200">
                  {comment.user.display_name || comment.user.username}
                </span>
                <span class="shrink-0 text-[0.7rem] text-slate-400 dark:text-zinc-500">
                  {formatDate(comment.created_at)}
                </span>
              </div>
              <p class="whitespace-pre-wrap break-words text-slate-700 dark:text-zinc-300">
                {comment.body}
              </p>
            </div>
          {/each}
        </div>

        <form
          class="mt-3 border-t border-slate-100 pt-3 dark:border-zinc-800"
          on:submit|preventDefault={() => addReply(thread)}
        >
          <textarea
            value={replyDrafts[thread.id] || ''}
            on:input={(event) => {
              replyDrafts = {
                ...replyDrafts,
                [thread.id]: (event.currentTarget as HTMLTextAreaElement).value,
              }
            }}
            rows="2"
            maxlength="4000"
            class="w-full resize-y rounded-md border border-slate-300 bg-white px-2.5 py-2 text-sm text-slate-900 outline-none focus:border-cyan-600 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
            placeholder={$t('site.draftReview.replyPlaceholder')}
          ></textarea>
          <div class="mt-2 flex items-center justify-between gap-2">
            {#if thread.can_resolve}
              <button
                type="button"
                class="text-xs font-semibold text-slate-600 hover:underline dark:text-zinc-300"
                disabled={busyThreadId !== null}
                on:click={() => toggleResolved(thread)}
              >
                {thread.resolved_at
                  ? $t('site.draftReview.reopen')
                  : $t('site.draftReview.resolve')}
              </button>
            {:else}
              <span></span>
            {/if}
            <Button
              submit={true}
              color="ghost"
              size="sm"
              loading={busyThreadId === thread.id}
              disabled={!String(replyDrafts[thread.id] || '').trim() || busyThreadId !== null}
            >
              {$t('site.draftReview.reply')}
            </Button>
          </div>
        </form>
      </article>
    {:else}
      <div class="py-8 text-center text-sm text-slate-500 dark:text-zinc-400">
        {$t('site.draftReview.noBlockComments')}
      </div>
    {/each}
  </div>
</aside>

<style>
  .draft-review-panel {
    max-height: calc(100vh - 6rem);
    overflow-y: auto;
  }

  @media (max-width: 1023px) {
    .draft-review-panel {
      max-height: none;
      overflow-y: visible;
    }
  }
</style>
