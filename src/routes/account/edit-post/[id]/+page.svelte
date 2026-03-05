<script lang="ts">
  import { goto } from '$app/navigation'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { Button, Spinner, TextInput, toast } from 'mono-svelte'
  import TipTapEditor from '$lib/components/editor/TipTapEditor.svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { buildBackendPostPath } from '$lib/api/backend'
  import {
    fetchUserPost,
    refreshSiteUser,
    siteUser,
    updateUserPost,
    type SiteUserPost,
  } from '$lib/siteAuth'
  import type { PostTemplateType } from '$lib/postTemplates'
  import { deserializeEditorModel } from '$lib/util'
  import { onMount } from 'svelte'

  export let data: { postId: number }

  let loading = true
  let loadError = ''
  let post: SiteUserPost | null = null

  let editTitle = ''
  let editContent = ''
  let editTags = ''
  let isJsonContent = true
  let editTemplateType: '' | PostTemplateType = ''
  let saving = false
  let saveError = ''

  const detectContentType = (content: string): boolean => {
    if (!content || content.trim() === '') {
      return true
    }
    if (content.trim().startsWith('<') && content.trim().endsWith('>')) {
      return false
    }
    try {
      const parsed = JSON.parse(content)
      return parsed && typeof parsed === 'object' && 'blocks' in parsed
    } catch {
      try {
        const isBase64 = /^[A-Za-z0-9+/]*={0,2}$/.test(content)
        if (!isBase64) {
          return false
        }
        const decoded = deserializeEditorModel(content)
        return decoded && typeof decoded === 'object' && 'blocks' in decoded
      } catch {
        return false
      }
    }
  }

  const stripHtml = (value: string) =>
    value.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ').trim()

  const fillForm = (currentPost: SiteUserPost) => {
    editTitle = currentPost.title || ''
    editContent = currentPost.content || ''
    editTemplateType =
      currentPost.template?.type === 'movie_review' ||
      currentPost.template?.type === 'post_vote_poll' ||
      currentPost.template?.type === 'music_release'
        ? currentPost.template.type
        : ''
    const tagNames = (currentPost.tags ?? []).map((tag) =>
      typeof tag === 'string' ? tag : tag.name
    )
    editTags = tagNames.join(', ')
    isJsonContent = detectContentType(editContent)
  }

  const loadPost = async () => {
    loading = true
    loadError = ''
    try {
      const user = await refreshSiteUser()
      if (!user) {
        await goto('/settings')
        return
      }
      const loadedPost = await fetchUserPost(data.postId)
      post = loadedPost
      fillForm(loadedPost)
    } catch (err) {
      loadError = (err as Error)?.message ?? 'Не удалось загрузить пост'
    } finally {
      loading = false
    }
  }

  const saveEdit = async () => {
    if (!post) return
    saving = true
    saveError = ''
    try {
      const trimmedContent = editContent.trim()
      if (isJsonContent) {
        if (!trimmedContent) {
          saveError = 'Текст поста не может быть пустым'
          saving = false
          return
        }
      } else {
        const hasText = stripHtml(trimmedContent).length > 0
        if (!hasText) {
          saveError = 'Текст поста не может быть пустым'
          saving = false
          return
        }
      }

      const tags = editTags
        .split(',')
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0)

      const updated = await updateUserPost(post.id, {
        title: editTitle,
        content: trimmedContent,
        tags,
      })
      post = updated
      fillForm(updated)
      toast({ content: 'Пост обновлен', type: 'success' })
    } catch (err) {
      saveError = (err as Error)?.message ?? 'Не удалось сохранить изменения'
    } finally {
      saving = false
    }
  }

  onMount(() => {
    loadPost()
  })
</script>

<div class="flex flex-col gap-6 max-w-4xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Редактирование поста</h1>
  </Header>

  {#if loading}
    <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
      <Spinner size="sm" />
      Загрузка...
    </div>
  {:else if loadError}
    <p class="text-sm text-red-600">{loadError}</p>
  {:else if post}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-4 sm:p-6 flex flex-col gap-4">
      <TextInput label="Заголовок" bind:value={editTitle} />
      <TextInput label="Теги (через запятую)" bind:value={editTags} />

      <div class="flex flex-col gap-2">
        {#if isJsonContent}
          <EditorJS
            bind:value={editContent}
            placeholder="Текст поста"
            postTemplateType={editTemplateType}
            enableAutosave={false}
            postId={post.id}
            showPostSettings={false}
          />
        {:else}
          <TipTapEditor
            bind:value={editContent}
            placeholder="Текст поста"
            includeMetaTags={false}
            allowMedia={false}
          />
        {/if}
      </div>

      {#if saveError}
        <p class="text-sm text-red-600">{saveError}</p>
      {/if}

      <div class="flex flex-wrap gap-2">
        <Button color="primary" on:click={saveEdit} loading={saving} disabled={saving}>
          Сохранить
        </Button>
        <Button color="ghost" href="/settings" disabled={saving}>
          Назад к настройкам
        </Button>
        <Button
          color="ghost"
          href={buildBackendPostPath({ id: post.id, title: post.title })}
          target="_blank"
          rel="noreferrer"
          disabled={saving}
        >
          Открыть пост
        </Button>
      </div>
    </div>
  {/if}
</div>
