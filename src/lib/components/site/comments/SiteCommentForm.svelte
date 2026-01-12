<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import { Button } from 'mono-svelte'
  import MarkdownEditor from '$lib/components/markdown/MarkdownEditor.svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { buildCommentDetailUrl, buildPostCommentsUrl } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import type { SiteComment } from './types'

  export let postId: number
  export let parentId: number | null = null
  export let commentId: number | null = null
  export let initialBody = ''
  export let placeholder = 'Напишите комментарий...'
  export let submitLabel = 'Отправить'
  export let autoFocus = false
  export let showCancel = false

  const dispatch = createEventDispatcher<{
    comment: SiteComment
    cancel: void
  }>()

  let value = initialBody
  let loading = false
  let error = ''
  let showLoginModal = false
  let lastCommentId = commentId

  $: if (commentId !== lastCommentId) {
    lastCommentId = commentId
    value = initialBody
    error = ''
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
