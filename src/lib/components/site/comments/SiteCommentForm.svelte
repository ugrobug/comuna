<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import { browser } from '$app/environment'
  import { Button } from 'mono-svelte'
  import MarkdownEditor from '$lib/components/markdown/MarkdownEditor.svelte'
  import LoginModal from '$lib/components/auth/LoginModal.svelte'
  import { buildCommentDetailUrl, buildPostCommentsUrl } from '$lib/api/backend'
  import { siteToken, siteUser, uploadSiteImage } from '$lib/siteAuth'
  import { optimizeImageURL } from '$lib/components/lemmy/post/helpers'
  import { getSafeUrl } from '$lib/security/url'
  import { Icon, XMark } from 'svelte-hero-icons'
  import { composeCommentBody, splitCommentBodyImages } from './imageMarkdown'
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
  export let submitUrl: string | null = null

  const dispatch = createEventDispatcher<{
    comment: SiteComment
    cancel: void
  }>()

  let value = ''
  let imageUrls: string[] = []
  let loading = false
  let error = ''
  let showLoginModal = false
  let lastCommentId = commentId
  let lastInitialBody = initialBody
  let selectedMaskKey = ''
  let masksInitialized = false
  let loginPromptedForDraft = false
  let lastObservedValue = value
  const COMMENT_MASK_STORAGE_KEY = 'comuna.admin.comment.mask'

  function resetDraft(nextBody: string) {
    const parsed = splitCommentBodyImages(nextBody)
    value = parsed.text
    imageUrls = parsed.imageUrls
    lastObservedValue = value
  }

  resetDraft(initialBody)

  $: canChooseMask = Boolean($siteUser?.is_staff && !commentId && commentMasks.length > 0)

  $: if (commentId !== lastCommentId || initialBody !== lastInitialBody) {
    lastCommentId = commentId
    lastInitialBody = initialBody
    resetDraft(initialBody)
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

  $: if (value !== lastObservedValue) {
    lastObservedValue = value
    if (!$siteToken && value.trim() && !loginPromptedForDraft) {
      showLoginModal = true
      loginPromptedForDraft = true
    }
  }

  $: if ($siteToken || !value.trim()) {
    loginPromptedForDraft = false
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

  async function uploadCommentImage(image: File) {
    if (!$siteToken) {
      showLoginModal = true
      throw new Error('Войдите, чтобы загрузить изображение')
    }
    return uploadSiteImage(image)
  }

  function addImageUrls(urls: string[]) {
    imageUrls = Array.from(new Set([...imageUrls, ...urls]))
  }

  function removeImageUrl(url: string) {
    imageUrls = imageUrls.filter((item) => item !== url)
  }

  function imagePreviewUrl(url: string) {
    const safeUrl = getSafeUrl(url, { allowRelative: true })
    return safeUrl ? optimizeImageURL(safeUrl, 320) : ''
  }

  async function submit() {
    if (!$siteToken) {
      showLoginModal = true
      return
    }
    const body = composeCommentBody(value, imageUrls)
    if (!body) {
      error = 'Введите текст комментария'
      return
    }

    loading = true
    error = ''

    try {
      const payload: Record<string, unknown> = {
        body,
      }
      if (parentId) {
        payload.parent_id = parentId
      }
      if (canChooseMask && selectedMaskKey) {
        payload.mask_key = selectedMaskKey
      }

      const response = await fetch(
        commentId ? buildCommentDetailUrl(commentId) : submitUrl || buildPostCommentsUrl(postId),
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
          imageUrls = []
          lastObservedValue = ''
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
          <option value={mask.key}>{mask.display_name || `@${mask.username}`}</option>
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
    images={true}
    imageUploadHandler={uploadCommentImage}
    imageInsertMode="event"
    on:images={(event) => addImageUrls(event.detail)}
  />
  {#if imageUrls.length}
    <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
      {#each imageUrls as imageUrl, index (imageUrl)}
        {@const previewUrl = imagePreviewUrl(imageUrl)}
        {#if previewUrl}
          <div
            class="relative aspect-[4/3] overflow-hidden rounded-lg border border-slate-200 bg-slate-100 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <img
              src={previewUrl}
              alt={`Изображение ${index + 1}`}
              class="h-full w-full object-cover"
            />
            <button
              type="button"
              class="absolute right-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-white/90 text-slate-700 shadow-sm transition hover:bg-white hover:text-rose-600 dark:bg-zinc-950/90 dark:text-zinc-200"
              title="Удалить изображение"
              aria-label="Удалить изображение"
              on:click={() => removeImageUrl(imageUrl)}
              disabled={loading}
            >
              <Icon src={XMark} size="16" micro />
            </button>
          </div>
        {/if}
      {/each}
    </div>
  {/if}
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
