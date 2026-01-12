<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import { Icon, Heart, ChatBubbleOvalLeft, PencilSquare, Trash } from 'svelte-hero-icons'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import RelativeDate from '$lib/components/util/RelativeDate.svelte'
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { buildCommentLikeUrl, buildCommentDetailUrl } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import SiteCommentForm from './SiteCommentForm.svelte'
  import type { SiteComment, SiteCommentNode } from './types'

  export let node: SiteCommentNode
  export let depth = 0
  export let postId: number
  export let postAuthor: string | null = null

  const dispatch = createEventDispatcher<{
    reply: SiteComment
    update: SiteComment
    remove: number
  }>()

  let replying = false
  let editing = false
  let liking = false
  let deleting = false
  let showLoginModal = false

  $: isAuthor = postAuthor && node.comment.user.username === postAuthor
  $: isDeleted = Boolean(node.comment.is_deleted)
  $: commentDate = new Date(node.comment.created_at)
  $: edited =
    node.comment.updated_at &&
    new Date(node.comment.updated_at).getTime() > commentDate.getTime()

  const forward = (event: CustomEvent) => {
    dispatch(event.type, event.detail)
  }

  const setComment = (comment: SiteComment) => {
    node = { ...node, comment }
  }

  async function toggleLike() {
    if (!$siteToken) {
      showLoginModal = true
      return
    }
    if (liking || isDeleted) return
    liking = true
    try {
      const response = await fetch(buildCommentLikeUrl(node.comment.id), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${$siteToken}`,
        },
      })
      const data = await response.json()
      if (response.ok && data) {
        setComment({
          ...node.comment,
          likes_count: data.likes_count ?? node.comment.likes_count ?? 0,
          liked_by_me: data.liked ?? !node.comment.liked_by_me,
        })
      }
    } finally {
      liking = false
    }
  }

  async function deleteComment() {
    if (!$siteToken) {
      showLoginModal = true
      return
    }
    if (deleting || isDeleted) return
    deleting = true
    try {
      const response = await fetch(buildCommentDetailUrl(node.comment.id), {
        method: 'DELETE',
        headers: {
          Authorization: `Bearer ${$siteToken}`,
        },
      })
      if (response.ok) {
        setComment({
          ...node.comment,
          is_deleted: true,
          body: '',
        })
        dispatch('remove', node.comment.id)
      }
    } finally {
      deleting = false
    }
  }
</script>

<LoginModal bind:open={showLoginModal} />

<li class="relative flex flex-col gap-3 rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-4 shadow-sm">
  <div class="flex gap-3">
    <Avatar width={depth > 0 ? 28 : 36} alt={node.comment.user.username} />
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 text-xs text-slate-500 dark:text-zinc-400 flex-wrap">
        <span class="text-sm font-semibold text-slate-900 dark:text-zinc-100">
          @{node.comment.user.username}
        </span>
        {#if isAuthor}
          <span class="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-600">
            Автор
          </span>
        {/if}
        <RelativeDate date={commentDate} />
        {#if edited}
          <span class="text-[11px] text-slate-400">изменено</span>
        {/if}
      </div>

      {#if editing}
        <div class="mt-3">
          <SiteCommentForm
            {postId}
            commentId={node.comment.id}
            initialBody={node.comment.body}
            submitLabel="Сохранить"
            showCancel={true}
            autoFocus={true}
            on:comment={(event) => {
              setComment(event.detail)
              editing = false
              dispatch('update', event.detail)
            }}
            on:cancel={() => (editing = false)}
          />
        </div>
      {:else}
        <div class="mt-2 text-sm text-slate-800 dark:text-zinc-100">
          {#if isDeleted}
            <span class="italic text-slate-500">Комментарий удален</span>
          {:else}
            <Markdown source={node.comment.body} />
          {/if}
        </div>
      {/if}

      {#if !editing}
        <div class="mt-3 flex items-center gap-3 text-xs text-slate-500 dark:text-zinc-400">
          <button
            type="button"
            class="flex items-center gap-1 hover:text-slate-700 dark:hover:text-zinc-200 transition"
            on:click={() => (replying = !replying)}
            disabled={isDeleted}
          >
            <Icon src={ChatBubbleOvalLeft} size="14" mini />
            Ответить
          </button>
          <button
            type="button"
            class="flex items-center gap-1 hover:text-slate-700 dark:hover:text-zinc-200 transition {node
              .comment.liked_by_me
              ? 'text-rose-500'
              : ''}"
            on:click={toggleLike}
            disabled={liking || isDeleted}
          >
            <Icon src={Heart} size="14" mini />
            {node.comment.likes_count ?? 0}
          </button>
          {#if node.comment.can_edit}
            <button
              type="button"
              class="flex items-center gap-1 hover:text-slate-700 dark:hover:text-zinc-200 transition"
              on:click={() => (editing = !editing)}
            >
              <Icon src={PencilSquare} size="14" mini />
              Редактировать
            </button>
            <button
              type="button"
              class="flex items-center gap-1 hover:text-rose-600 transition"
              on:click={deleteComment}
              disabled={deleting}
            >
              <Icon src={Trash} size="14" mini />
              Удалить
            </button>
          {/if}
        </div>
      {/if}

      {#if replying}
        <div class="mt-3">
          <SiteCommentForm
            {postId}
            parentId={node.comment.id}
            placeholder="Ответить..."
            submitLabel="Ответить"
            showCancel={true}
            autoFocus={true}
            on:comment={(event) => {
              replying = false
              dispatch('reply', event.detail)
            }}
            on:cancel={() => (replying = false)}
          />
        </div>
      {/if}
    </div>
  </div>

  {#if node.children.length > 0}
    <ul class="mt-4 ml-4 pl-4 border-l border-slate-200 dark:border-zinc-800 flex flex-col gap-4">
      {#each node.children as child (child.comment.id)}
        <SiteCommentItem
          node={child}
          depth={depth + 1}
          {postId}
          {postAuthor}
          on:reply={forward}
          on:update={forward}
          on:remove={forward}
        />
      {/each}
    </ul>
  {/if}
</li>
