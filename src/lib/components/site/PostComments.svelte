<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte'
  import { browser } from '$app/environment'
  import {
    buildPostCommentsUrl,
    buildQuestionAnswerUrl,
    type BackendQuestionAnswer,
  } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import { locale, t } from '$lib/translations'
  import SiteCommentForm from '$lib/components/site/comments/SiteCommentForm.svelte'
  import SiteCommentItem from '$lib/components/site/comments/SiteCommentItem.svelte'
  import type { SiteComment, SiteCommentMask, SiteCommentNode } from '$lib/components/site/comments/types'
  import { Icon, CheckCircle } from 'svelte-hero-icons'
  import { Modal } from 'mono-svelte'

  export let postId: number
  export let postAuthor: string | null = null
  export let commentsUrl: string | null = null
  export let language: string | null = null
  export let questionAnswer: BackendQuestionAnswer | null = null

  const dispatch = createEventDispatcher<{
    comment: SiteComment
    questionanswerchange: BackendQuestionAnswer
  }>()
  let comments: SiteComment[] = []
  let commentTree: SiteCommentNode[] = []
  let loading = false
  let error = ''
  let commentMasks: SiteCommentMask[] = []
  let lastToken: string | null = null
  let lastPostId = postId
  let lastCommentsUrl = commentsUrl
  let lastLanguage = ''
  let mounted = false
  let answerSelectorOpen = false
  let selectingAnswerId: number | null = null
  let answerSelectionError = ''
  let acceptNextOwnComment = false
  let answerMutationVersion = 0
  $: availableAnswers = comments.filter((comment) => !comment.is_deleted)

  $: effectiveCommentsLanguage = language || $locale || 'ru'

  const buildTree = (items: SiteComment[]): SiteCommentNode[] => {
    const nodes = new Map<number, SiteCommentNode>()
    const roots: SiteCommentNode[] = []

    items.forEach((comment) => {
      nodes.set(comment.id, { comment, children: [] })
    })

    items.forEach((comment) => {
      const node = nodes.get(comment.id)
      if (!node) return
      if (comment.is_accepted_answer) {
        roots.push(node)
      } else if (comment.parent_id && nodes.has(comment.parent_id)) {
        nodes.get(comment.parent_id)!.children.push(node)
      } else {
        roots.push(node)
      }
    })

    return roots.sort((left, right) => {
      const acceptedOrder = Number(Boolean(right.comment.is_accepted_answer)) - Number(Boolean(left.comment.is_accepted_answer))
      if (acceptedOrder) return acceptedOrder
      return left.comment.created_at.localeCompare(right.comment.created_at)
    })
  }

  const rebuildTree = () => {
    commentTree = buildTree(comments)
  }

  const normalizeList = (items: SiteComment[]) =>
    items.slice().sort((a, b) => a.created_at.localeCompare(b.created_at))

  const loadComments = async () => {
    if (!browser) return
    const mutationVersion = answerMutationVersion
    loading = true
    error = ''
    try {
      const response = await fetch(commentsUrl || buildPostCommentsUrl(postId, effectiveCommentsLanguage), {
        headers: $siteToken
          ? {
              Authorization: `Bearer ${$siteToken}`,
            }
          : undefined,
      })
      if (!response.ok) {
        throw new Error($t('site.comments.errors.load'))
      }
      const data = await response.json()
      if (mutationVersion !== answerMutationVersion) {
        loading = false
        return
      }
      comments = normalizeList((data.comments ?? []) as SiteComment[])
      if (data.question_answer) {
        questionAnswer = data.question_answer as BackendQuestionAnswer
        dispatch('questionanswerchange', questionAnswer)
      }
      commentMasks =
        $siteUser?.is_staff && Array.isArray(data.comment_masks)
          ? ((data.comment_masks as SiteCommentMask[]) ?? [])
          : []
      rebuildTree()
    } catch (err) {
      error = (err as Error)?.message ?? $t('site.comments.errors.loadFallback')
    }
    loading = false
  }

  const selectQuestionAnswer = async (commentId: number) => {
    if (!$siteToken || selectingAnswerId !== null) return false
    const previousQuestionAnswer = questionAnswer
    const previousComments = comments
    const optimisticQuestionAnswer: BackendQuestionAnswer = {
      ...(questionAnswer ?? {}),
      is_solved: true,
      accepted_comment_id: commentId,
      solved_at: new Date().toISOString(),
      can_select_answer: questionAnswer?.can_select_answer ?? true,
    }

    selectingAnswerId = commentId
    answerMutationVersion += 1
    answerSelectionError = ''
    questionAnswer = optimisticQuestionAnswer
    comments = comments.map((comment) => ({
      ...comment,
      is_accepted_answer: comment.id === commentId,
    }))
    rebuildTree()
    dispatch('questionanswerchange', optimisticQuestionAnswer)
    answerSelectorOpen = false

    try {
      const response = await fetch(buildQuestionAnswerUrl(postId), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${$siteToken}`,
        },
        body: JSON.stringify({ comment_id: commentId }),
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || !data.question_answer) {
        throw new Error(data.error || $t('site.comments.question.errors.select'))
      }
      questionAnswer = data.question_answer as BackendQuestionAnswer
      comments = comments.map((comment) => ({
        ...comment,
        is_accepted_answer: comment.id === questionAnswer?.accepted_comment_id,
      }))
      rebuildTree()
      dispatch('questionanswerchange', questionAnswer)
      return true
    } catch (err) {
      questionAnswer = previousQuestionAnswer
      comments = previousComments
      rebuildTree()
      if (previousQuestionAnswer) {
        dispatch('questionanswerchange', previousQuestionAnswer)
      }
      answerSelectionError = (err as Error)?.message || $t('site.comments.question.errors.select')
      answerSelectorOpen = true
      return false
    } finally {
      selectingAnswerId = null
    }
  }

  const upsertComment = async (comment: SiteComment) => {
    const index = comments.findIndex((item) => item.id === comment.id)
    if (index >= 0) {
      comments = comments.map((item) => (item.id === comment.id ? comment : item))
    } else {
      comments = normalizeList([...comments, comment])
    }
    rebuildTree()
    dispatch('comment', comment)
    if (acceptNextOwnComment && !comment.parent_id) {
      acceptNextOwnComment = false
      await selectQuestionAnswer(comment.id)
    }
  }

  export const openAnswerSelector = () => {
    answerSelectionError = ''
    answerSelectorOpen = true
  }

  const writeAndAcceptAnswer = () => {
    acceptNextOwnComment = true
    answerSelectorOpen = false
    setTimeout(() => {
      const form = document.querySelector('#question-answer-comment-form')
      form?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      const textarea = form?.querySelector('textarea') as HTMLTextAreaElement | null
      textarea?.focus()
    })
  }

  const markDeleted = (commentId: number) => {
    comments = comments.map((item) =>
      item.id === commentId ? { ...item, is_deleted: true, body: '' } : item
    )
    rebuildTree()
  }

  onMount(() => {
    mounted = true
    lastLanguage = effectiveCommentsLanguage
    loadComments()
  })

  $: if ($siteToken !== lastToken) {
    lastToken = $siteToken
    loadComments()
  }

  $: if (postId !== lastPostId) {
    lastPostId = postId
    loadComments()
  }

  $: if (commentsUrl !== lastCommentsUrl) {
    lastCommentsUrl = commentsUrl
    loadComments()
  }

  $: if (mounted && effectiveCommentsLanguage !== lastLanguage) {
    lastLanguage = effectiveCommentsLanguage
    loadComments()
  }
</script>

<Modal bind:open={answerSelectorOpen}>
  <span slot="title">{$t('site.comments.question.selectTitle')}</span>
  <div class="flex max-h-[60vh] flex-col gap-3 overflow-y-auto">
    {#if answerSelectionError}
      <p class="text-sm text-red-600 dark:text-red-400">{answerSelectionError}</p>
    {/if}
    {#if availableAnswers.length}
      <p class="text-sm text-slate-600 dark:text-zinc-300">
        {$t('site.comments.question.selectHint')}
      </p>
      <div class="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 dark:divide-zinc-700 dark:border-zinc-700">
        {#each availableAnswers as comment (comment.id)}
          <button
            type="button"
            class="flex w-full items-start gap-3 bg-white px-4 py-3 text-left transition hover:bg-slate-50 disabled:opacity-60 dark:bg-zinc-900 dark:hover:bg-zinc-800"
            disabled={selectingAnswerId !== null}
            on:click={() => selectQuestionAnswer(comment.id)}
          >
            <Icon
              src={CheckCircle}
              size="20"
              class={comment.is_accepted_answer ? 'mt-0.5 text-emerald-600' : 'mt-0.5 text-slate-400'}
            />
            <span class="min-w-0">
              <span class="block text-sm font-semibold text-slate-900 dark:text-zinc-100">
                {comment.user.display_name || comment.user.username}
              </span>
              <span class="mt-1 block line-clamp-3 text-sm text-slate-600 dark:text-zinc-300">
                {comment.body}
              </span>
            </span>
          </button>
        {/each}
      </div>
    {:else}
      <p class="text-sm leading-6 text-slate-600 dark:text-zinc-300">
        {$t('site.comments.question.noComments')}
      </p>
      <button
        type="button"
        class="inline-flex w-fit items-center gap-2 rounded-md bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-700"
        on:click={writeAndAcceptAnswer}
      >
        {$t('site.comments.question.writeAnswer')}
      </button>
    {/if}
  </div>
</Modal>

<section id="comments" class="mt-10">
  <div class="flex items-center justify-between mb-5">
    <h2 class="text-xl font-semibold">{$t('site.comments.title')}</h2>
    <span class="text-sm text-slate-500">{comments.filter((c) => !c.is_deleted).length}</span>
  </div>

  {#if error}
    <p class="text-sm text-red-600 mb-4">{error}</p>
  {/if}

  {#if loading}
    <p class="text-sm text-slate-500">{$t('site.comments.loading')}</p>
  {:else if comments.length === 0}
    <p class="text-sm text-slate-500">{$t('site.comments.empty')}</p>
  {:else}
    <ul class="flex flex-col gap-4">
      {#each commentTree as node (node.comment.id)}
        <SiteCommentItem
          {node}
          {postId}
          {postAuthor}
          {commentMasks}
          submitUrl={commentsUrl}
          on:reply={(event) => upsertComment(event.detail)}
          on:update={(event) => upsertComment(event.detail)}
          on:remove={(event) => markDeleted(event.detail)}
        />
      {/each}
    </ul>
  {/if}

  <div class="mt-8" id="question-answer-comment-form">
    {#if !$siteUser}
      <p class="text-sm text-slate-500 dark:text-zinc-400 mb-4">
        {$t('site.comments.loginPrompt')}
      </p>
    {/if}

    <SiteCommentForm
      {postId}
      {commentMasks}
      submitUrl={commentsUrl}
      placeholder={$t('site.comments.placeholder')}
      on:comment={(event) => upsertComment(event.detail)}
    />
  </div>
</section>
