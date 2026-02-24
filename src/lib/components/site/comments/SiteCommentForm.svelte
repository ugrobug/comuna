<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import { browser } from '$app/environment'
  import { Button } from 'mono-svelte'
  import MarkdownEditor from '$lib/components/markdown/MarkdownEditor.svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { buildCommentDetailUrl, buildPostCommentsUrl } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import type { SiteComment, SiteCommentMask } from './types'

  export let postId: number
  export let parentId: number | null = null
  export let commentId: number | null = null
  export let initialBody = ''
  export let placeholder = 'Напишите комментарий...'
  export let submitLabel = 'Отправить'
  export let autoFocus = false
  export let showCancel = false
  export let commentMasks: SiteCommentMask[] = []

  const dispatch = createEventDispatcher<{
    comment: SiteComment
    cancel: void
  }>()

  let value = initialBody
  let loading = false
  let error = ''
  let showLoginModal = false
  let lastCommentId = commentId
  let selectedMaskKey = ''
  let masksInitialized = false
  const COMMENT_MASK_STORAGE_KEY = 'comuna.admin.comment.mask'

  $: canChooseMask = Boolean($siteUser?.is_staff && !commentId && commentMasks.length > 0)

  $: if (commentId !== lastCommentId) {
    lastCommentId = commentId
    value = initialBody
    error = ''
  }

  $: if (canChooseMask && !masksInitialized) {
    masksInitialized = true
    if (browser) {
      const saved = localStorage.getItem(COMMENT_MASK_STORAGE_KEY) || ''
      if (saved && commentMasks.some((mask) => mask.key === saved)) {
        selectedMaskKey = saved
      }
    }
  }

  $: if (!canChooseMask) {
    selectedMaskKey = ''
    masksInitialized = false
  }

  function updateMaskSelection(nextKey: string) {
    selectedMaskKey = nextKey
    if (!browser) return
    if (nextKey) {
      localStorage.setItem(COMMENT_MASK_STORAGE_KEY, nextKey)
    } else {
      localStorage.removeItem(COMMENT_MASK_STORAGE_KEY)
    }
  }

  function handleMaskChange(event: Event) {
    const target = event.currentTarget as HTMLSelectElement | null
    updateMaskSelection(target?.value || '')
  }

  async function submit() {
    if (!$siteToken) {
      showLoginModal = true
      return
    }
    if (!value.trim()) {
      error = 'Введите текст комментария'
      return
    }

    loading = true
    error = ''

    try {
      const payload: Record<string, unknown> = {
        body: value.trim(),
      }
      if (parentId) {
        payload.parent_id = parentId
      }
      if (canChooseMask && selectedMaskKey) {
        payload.mask_key = selectedMaskKey
      }

      const response = await fetch(
        commentId ? buildCommentDetailUrl(commentId) : buildPostCommentsUrl(postId),
        {
          method: commentId ? 'PATCH' : 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${$siteToken}`,
          },
          body: JSON.stringify(payload),
        }
      )

      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.error || 'Не удалось отправить комментарий')
      }

      if (data?.comment) {
        dispatch('comment', data.comment as SiteComment)
        if (!commentId) {
          value = ''
        }
      }
    } catch (err) {
      error = (err as Error)?.message ?? 'Ошибка отправки'
    }

    loading = false
  }
</script>

<LoginModal bind:open={showLoginModal} />

<div class="flex flex-col gap-3">
  {#if canChooseMask}
    <div class="flex flex-col gap-1">
      <label for={`comment-mask-${postId}-${parentId ?? 'root'}-${commentId ?? 'new'}`} class="text-xs font-medium text-slate-600 dark:text-zinc-400">
        Писать как
      </label>
      <select
        id={`comment-mask-${postId}-${parentId ?? 'root'}-${commentId ?? 'new'}`}
        class="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        value={selectedMaskKey}
        on:change={handleMaskChange}
      >
        <option value="">Мой аккаунт (@{$siteUser?.username})</option>
        {#each commentMasks as mask}
          <option value={mask.key}>@{mask.username}</option>
        {/each}
      </select>
      <p class="text-xs text-slate-500 dark:text-zinc-500">
        Только для администраторов. Выбранная маска сохранится для следующих комментариев.
      </p>
    </div>
  {/if}

  <MarkdownEditor
    bind:value
    placeholder={placeholder}
    rows={4}
    {autoFocus}
    tools={true}
    previewButton={false}
    images={false}
  />
  {#if error}
    <p class="text-sm text-red-600">{error}</p>
  {/if}
  <div class="flex items-center justify-end gap-2">
    {#if showCancel}
      <Button
        size="sm"
        color="ghost"
        on:click={() => dispatch('cancel')}
        disabled={loading}
      >
        Отмена
      </Button>
    {/if}
    <Button
      size="sm"
      color="primary"
      on:click={submit}
      loading={loading}
      disabled={loading}
    >
      {submitLabel}
    </Button>
  </div>
</div>
