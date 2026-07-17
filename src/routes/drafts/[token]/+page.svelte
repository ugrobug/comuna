<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { buildBackendPostPath } from '$lib/api/backend'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import {
    createDraftBlockComment,
    deleteUserPost,
    fetchDraftBlockComments,
    fetchSharedDraft,
    refreshSiteUser,
    replyToDraftBlockComment,
    setDraftBlockCommentResolved,
    siteUser,
    updateUserPost,
    type DraftBlockCommentThread,
    type SiteUserPost,
  } from '$lib/siteAuth'
  import { siteUserPostToPostView } from '$lib/siteUserPostPreview'
  import { locale, t } from '$lib/translations'
  import { Button, Spinner, toast } from 'mono-svelte'
  import { onMount, tick } from 'svelte'

  export let data: { shareToken: string }

  let loading = true
  let actionLoading = false
  let draft: SiteUserPost | null = null
  let threads: DraftBlockCommentThread[] = []
  let selectedBlockId = ''
  let newComment = ''
  let replyDrafts: Record<number, string> = {}
  let submittingBlock = false
  let busyThreadId: number | null = null
  let loadError = ''
  let commentError = ''
  let loggedIn = false
  let reviewPanel: HTMLElement | null = null

  $: draftPostView = draft ? siteUserPostToPostView(draft) : null
  $: draftAuthorUsername = draft?.author?.username
  $: isDraftOwner = Boolean(
    $siteUser &&
      draftAuthorUsername &&
      (draftAuthorUsername === $siteUser.username ||
        ($siteUser.authors ?? []).some((author) => author.username === draftAuthorUsername))
  )
  $: editPath = draft ? `/account/edit-post/${draft.id}` : '/account/new-post'
  $: profileDraftsPath = $siteUser?.id ? `/id${$siteUser.id}` : '/settings'
  $: selectedThreads = selectedBlockId
    ? threads.filter((thread) => thread.block_id === selectedBlockId)
    : threads
  $: draftCommentCounts = threads.reduce<Record<string, number>>((counts, thread) => {
    if (!thread.resolved_at && thread.block_exists) {
      counts[thread.block_id] = (counts[thread.block_id] || 0) + 1
    }
    return counts
  }, {})

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

  const scrollToBlock = async (blockId: string) => {
    selectedBlockId = blockId
    await tick()
    const escaped = typeof CSS !== 'undefined' && CSS.escape ? CSS.escape(blockId) : blockId
    document
      .querySelector(`[data-draft-block-id="${escaped}"]`)
      ?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  const selectBlock = async (event: CustomEvent<{ blockId: string }>) => {
    selectedBlockId = event.detail.blockId
    commentError = ''
    await tick()
    if (window.matchMedia('(max-width: 1023px)').matches) {
      reviewPanel?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }

  const addThread = async () => {
    const body = newComment.trim()
    if (!selectedBlockId || !body || submittingBlock) return
    submittingBlock = true
    commentError = ''
    try {
      const thread = await createDraftBlockComment(data.shareToken, selectedBlockId, body)
      threads = [...threads, thread]
      newComment = ''
      toast({ content: $t('site.draftReview.commentAdded'), type: 'success' })
    } catch (error) {
      commentError = (error as Error)?.message || $t('site.draftReview.saveError')
    } finally {
      submittingBlock = false
    }
  }

  const addReply = async (thread: DraftBlockCommentThread) => {
    const body = String(replyDrafts[thread.id] || '').trim()
    if (!body || busyThreadId !== null) return
    busyThreadId = thread.id
    commentError = ''
    try {
      const comment = await replyToDraftBlockComment(data.shareToken, thread.id, body)
      threads = threads.map((item) =>
        item.id === thread.id ? { ...item, comments: [...item.comments, comment] } : item
      )
      replyDrafts = { ...replyDrafts, [thread.id]: '' }
    } catch (error) {
      commentError = (error as Error)?.message || $t('site.draftReview.saveError')
    } finally {
      busyThreadId = null
    }
  }

  const toggleResolved = async (thread: DraftBlockCommentThread) => {
    if (!thread.can_resolve || busyThreadId !== null) return
    busyThreadId = thread.id
    commentError = ''
    try {
      const updated = await setDraftBlockCommentResolved(
        data.shareToken,
        thread.id,
        !thread.resolved_at
      )
      threads = threads.map((item) => (item.id === updated.id ? updated : item))
    } catch (error) {
      commentError = (error as Error)?.message || $t('site.draftReview.saveError')
    } finally {
      busyThreadId = null
    }
  }

  const publishDraft = async () => {
    if (!draft || actionLoading || !isDraftOwner) return
    actionLoading = true
    loadError = ''
    try {
      const updated = await updateUserPost(draft.id, { is_draft: false })
      toast({ content: $t('site.draftReview.published'), type: 'success' })
      await goto(buildBackendPostPath({ id: updated.id, title: updated.title }))
    } catch (error) {
      loadError = (error as Error)?.message ?? $t('site.draftReview.publishError')
    } finally {
      actionLoading = false
    }
  }

  const removeDraft = async () => {
    if (!draft || actionLoading || !isDraftOwner) return
    if (!confirm($t('site.draftReview.deleteConfirm'))) return
    actionLoading = true
    loadError = ''
    try {
      await deleteUserPost(draft.id)
      toast({ content: $t('site.draftReview.deleted'), type: 'success' })
      await goto(profileDraftsPath)
    } catch (error) {
      loadError = (error as Error)?.message ?? $t('site.draftReview.deleteError')
    } finally {
      actionLoading = false
    }
  }

  onMount(() => {
    const loadDraft = async () => {
      loading = true
      loadError = ''
      let blockToScroll = ''
      try {
        const user = await refreshSiteUser()
        loggedIn = Boolean(user)
        if (!user) {
          loadError = $t('site.draftReview.loginRequired')
          return
        }
        ;[draft, threads] = await Promise.all([
          fetchSharedDraft(data.shareToken),
          fetchDraftBlockComments(data.shareToken),
        ])
        const hashThreadId = Number(window.location.hash.replace('#draft-comment-', ''))
        const hashThread = threads.find((thread) => thread.id === hashThreadId)
        if (hashThread) {
          selectedBlockId = hashThread.block_id
          blockToScroll = hashThread.block_id
        }
      } catch (error) {
        loadError = (error as Error)?.message ?? $t('site.draftReview.loadError')
      } finally {
        loading = false
        if (blockToScroll) {
          await tick()
          await scrollToBlock(blockToScroll)
        }
      }
    }

    void loadDraft()
  })
</script>

<div class="flex max-w-7xl flex-col gap-6">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">{$t('site.draftReview.pageTitle')}</h1>
  </Header>

  {#if loading}
    <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
      <Spinner size="sm" />
      {$t('site.draftReview.loading')}
    </div>
  {:else if loadError}
    <div class="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200">
      <p>{loadError}</p>
      {#if !loggedIn}
        <div class="mt-4">
          <Button href="/settings">{$t('site.draftReview.signIn')}</Button>
        </div>
      {/if}
    </div>
  {:else if draft}
    <div class="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:items-start">
      <div class="min-w-0">
        <div class="rounded-lg border border-slate-200 border-b-slate-300 bg-white p-4 dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900 sm:p-6">
          <div class="mb-4 text-xs font-semibold uppercase text-slate-500 dark:text-zinc-400">
            {$t('site.draftReview.privatePreview')}
          </div>
          {#if draftPostView}
            <Post
              post={draftPostView}
              actions={false}
              view="cozy"
              showFullBody={true}
              showReadMore={false}
              linkOverride={$page.url.pathname}
              draftReviewEnabled={true}
              {draftCommentCounts}
              on:draftblockcomment={selectBlock}
            />
          {/if}
        </div>
        {#if isDraftOwner}
          <div class="mt-4 flex flex-wrap gap-2">
            <Button color="primary" on:click={publishDraft} loading={actionLoading} disabled={actionLoading}>
              {$t('site.draftReview.publish')}
            </Button>
            <Button color="ghost" href={editPath} disabled={actionLoading}>
              {$t('site.draftReview.edit')}
            </Button>
            <Button color="ghost" on:click={removeDraft} disabled={actionLoading}>
              {$t('site.draftReview.delete')}
            </Button>
          </div>
        {/if}
      </div>

      <aside bind:this={reviewPanel} class="min-w-0 scroll-mt-20 lg:sticky lg:top-20">
        <div class="mb-4 flex items-center justify-between gap-3 border-b border-slate-200 pb-3 dark:border-zinc-800">
          <div>
            <h2 class="text-base font-bold text-slate-900 dark:text-zinc-100">
              {$t('site.draftReview.title')}
            </h2>
            <p class="mt-1 text-xs text-slate-500 dark:text-zinc-400">
              {selectedBlockId
                ? $t('site.draftReview.selectedBlock')
                : $t('site.draftReview.selectBlock')}
            </p>
          </div>
          {#if selectedBlockId}
            <button
              type="button"
              class="text-xs font-semibold text-cyan-700 hover:underline dark:text-cyan-300"
              on:click={() => (selectedBlockId = '')}
            >
              {$t('site.draftReview.showAll')}
            </button>
          {/if}
        </div>

        {#if selectedBlockId}
          <form class="mb-4" on:submit|preventDefault={addThread}>
            <label for="draft-block-comment" class="sr-only">{$t('site.draftReview.newComment')}</label>
            <textarea
              id="draft-block-comment"
              bind:value={newComment}
              rows="3"
              maxlength="4000"
              class="w-full resize-y rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-cyan-600 focus:ring-2 focus:ring-cyan-600/20 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
              placeholder={$t('site.draftReview.placeholder')}
            ></textarea>
            <div class="mt-2 flex justify-end">
              <Button type="submit" color="primary" size="sm" loading={submittingBlock} disabled={!newComment.trim() || submittingBlock}>
                {$t('site.draftReview.send')}
              </Button>
            </div>
          </form>
        {/if}

        {#if commentError}
          <p class="mb-3 text-sm text-red-600 dark:text-red-400">{commentError}</p>
        {/if}

        <div class="space-y-3">
          {#each selectedThreads as thread (thread.id)}
            <article
              id={`draft-comment-${thread.id}`}
              class:opacity-65={Boolean(thread.resolved_at)}
              class="rounded-lg border border-slate-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900"
            >
              <button
                type="button"
                class="mb-3 flex w-full items-center gap-2 text-left"
                on:click={() => scrollToBlock(thread.block_id)}
              >
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
                  <span class="block truncate text-sm font-semibold text-slate-900 dark:text-zinc-100">{displayName(thread)}</span>
                  <span class="block text-xs text-slate-500 dark:text-zinc-400">{formatDate(thread.created_at)}</span>
                </span>
                {#if thread.resolved_at}
                  <span class="text-xs font-semibold text-emerald-700 dark:text-emerald-400">{$t('site.draftReview.resolved')}</span>
                {/if}
              </button>

              {#if !thread.block_exists}
                <p class="mb-2 text-xs text-amber-700 dark:text-amber-400">{$t('site.draftReview.blockRemoved')}</p>
              {/if}

              <div class="space-y-3">
                {#each thread.comments as comment}
                  <div class="text-sm">
                    <div class="mb-1 flex items-baseline justify-between gap-2">
                      <span class="font-semibold text-slate-800 dark:text-zinc-200">
                        {comment.user.display_name || comment.user.username}
                      </span>
                      <span class="shrink-0 text-[0.7rem] text-slate-400 dark:text-zinc-500">{formatDate(comment.created_at)}</span>
                    </div>
                    <p class="whitespace-pre-wrap break-words text-slate-700 dark:text-zinc-300">{comment.body}</p>
                  </div>
                {/each}
              </div>

              <form class="mt-3 border-t border-slate-100 pt-3 dark:border-zinc-800" on:submit|preventDefault={() => addReply(thread)}>
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
                    type="submit"
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
              {selectedBlockId
                ? $t('site.draftReview.noBlockComments')
                : $t('site.draftReview.noComments')}
            </div>
          {/each}
        </div>
      </aside>
    </div>
  {/if}
</div>
