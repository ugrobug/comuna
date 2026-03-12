<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { Button, Spinner, toast } from 'mono-svelte'
  import {
    deleteUserPost,
    fetchUserPost,
    refreshSiteUser,
    siteUser,
    updateUserPost,
    type SiteUserPost,
  } from '$lib/siteAuth'
  import { buildBackendPostPath } from '$lib/api/backend'
  import { siteUserPostToPostView } from '$lib/siteUserPostPreview'
  import { onMount } from 'svelte'

  export let data: { postId: number }

  let loading = true
  let actionLoading = false
  let loadError = ''
  let post: SiteUserPost | null = null

  $: postView = post ? siteUserPostToPostView(post) : null
  $: profileDraftsPath = $siteUser?.id ? `/id${$siteUser.id}` : '/settings'
  $: editPath = post ? `/account/edit-post/${post.id}` : '/account/new-post'

  const loadDraft = async () => {
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
    } catch (error) {
      loadError = (error as Error)?.message ?? 'Не удалось загрузить предпросмотр'
    } finally {
      loading = false
    }
  }

  const publishDraft = async () => {
    if (!post || actionLoading) return
    actionLoading = true
    loadError = ''
    try {
      const updated = await updateUserPost(post.id, { is_draft: false })
      toast({ content: 'Черновик опубликован', type: 'success' })
      await goto(buildBackendPostPath({ id: updated.id, title: updated.title }))
    } catch (error) {
      loadError = (error as Error)?.message ?? 'Не удалось опубликовать черновик'
    } finally {
      actionLoading = false
    }
  }

  const removeDraft = async () => {
    if (!post || actionLoading) return
    const confirmed = confirm('Удалить черновик?')
    if (!confirmed) return
    actionLoading = true
    loadError = ''
    try {
      await deleteUserPost(post.id)
      toast({ content: 'Черновик удалён', type: 'success' })
      await goto(profileDraftsPath)
    } catch (error) {
      loadError = (error as Error)?.message ?? 'Не удалось удалить черновик'
    } finally {
      actionLoading = false
    }
  }

  onMount(() => {
    void loadDraft()
  })
</script>

<div class="mx-auto flex max-w-3xl flex-col gap-6">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Предпросмотр публикации</h1>
  </Header>

  {#if loading}
    <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
      <Spinner size="sm" />
      Загрузка...
    </div>
  {:else if loadError}
    <div class="rounded-xl border border-slate-200 bg-white p-6 text-sm text-red-600 dark:border-zinc-800 dark:bg-zinc-950">
      {loadError}
    </div>
  {:else if post && postView}
    <div class="rounded-xl border border-slate-200 border-b-slate-300 bg-white p-4 dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900 sm:p-6">
      <div class="mb-4 text-xs uppercase tracking-[0.24em] text-slate-500 dark:text-zinc-400">
        Так публикация будет выглядеть после выхода
      </div>
      <Post
        post={postView}
        actions={false}
        view="cozy"
        showFullBody={true}
        showReadMore={false}
        linkOverride={$page.url.pathname}
      />
    </div>

    <div class="flex flex-wrap gap-2">
      <Button color="primary" on:click={publishDraft} loading={actionLoading} disabled={actionLoading}>
        Опубликовать
      </Button>
      <Button color="ghost" href={editPath} disabled={actionLoading}>
        Редактировать
      </Button>
      <Button color="ghost" on:click={removeDraft} disabled={actionLoading}>
        Удалить
      </Button>
    </div>
  {/if}
</div>
