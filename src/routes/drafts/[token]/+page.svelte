<script lang="ts">
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { buildBackendPostPath } from '$lib/api/backend'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { Button, Spinner, toast } from 'mono-svelte'
  import {
    deleteUserPost,
    fetchSharedDraft,
    refreshSiteUser,
    siteUser,
    updateUserPost,
    type SiteUserPost,
  } from '$lib/siteAuth'
  import { siteUserPostToPostView } from '$lib/siteUserPostPreview'
  import { onMount } from 'svelte'

  export let data: { shareToken: string }

  let loading = true
  let actionLoading = false
  let draft: SiteUserPost | null = null
  let loadError = ''
  let loggedIn = false

  $: draftPostView = draft ? siteUserPostToPostView(draft) : null
  $: isDraftOwner = Boolean(
    $siteUser &&
      draft &&
      (
        draft.author?.username === $siteUser.username ||
        ($siteUser.authors ?? []).some((author) => author.username === draft.author?.username)
      )
  )
  $: editPath = draft ? `/account/edit-post/${draft.id}` : '/account/new-post'
  $: profileDraftsPath = $siteUser?.id ? `/id${$siteUser.id}` : '/settings'

  const publishDraft = async () => {
    if (!draft || actionLoading || !isDraftOwner) return
    actionLoading = true
    loadError = ''
    try {
      const updated = await updateUserPost(draft.id, { is_draft: false })
      toast({ content: 'Черновик опубликован', type: 'success' })
      await goto(buildBackendPostPath({ id: updated.id, title: updated.title }))
    } catch (error) {
      loadError = (error as Error)?.message ?? 'Не удалось опубликовать черновик'
    } finally {
      actionLoading = false
    }
  }

  const removeDraft = async () => {
    if (!draft || actionLoading || !isDraftOwner) return
    const confirmed = confirm('Удалить черновик?')
    if (!confirmed) return
    actionLoading = true
    loadError = ''
    try {
      await deleteUserPost(draft.id)
      toast({ content: 'Черновик удалён', type: 'success' })
      await goto(profileDraftsPath)
    } catch (error) {
      loadError = (error as Error)?.message ?? 'Не удалось удалить черновик'
    } finally {
      actionLoading = false
    }
  }

  onMount(() => {
    const loadDraft = async () => {
      loading = true
      loadError = ''
      try {
        const user = await refreshSiteUser()
        loggedIn = Boolean(user)
        if (!user) {
          loadError = 'Чтобы открыть черновик по ссылке, нужно войти на сайт.'
          return
        }
        draft = await fetchSharedDraft(data.shareToken)
      } catch (error) {
        loadError = (error as Error)?.message ?? 'Не удалось загрузить черновик'
      } finally {
        loading = false
      }
    }

    void loadDraft()
  })
</script>

<div class="mx-auto flex max-w-3xl flex-col gap-6">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Черновик по ссылке</h1>
  </Header>

  {#if loading}
    <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
      <Spinner size="sm" />
      Загрузка...
    </div>
  {:else if loadError}
    <div class="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200">
      <p>{loadError}</p>
      {#if !loggedIn}
        <div class="mt-4">
          <Button href="/settings">Войти</Button>
        </div>
      {/if}
    </div>
  {:else if draft}
    <div class="rounded-xl border border-slate-200 border-b-slate-300 bg-white p-4 dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900 sm:p-6">
      <div class="mb-4 text-xs uppercase tracking-[0.24em] text-slate-500 dark:text-zinc-400">
        Приватный предпросмотр черновика
      </div>
      {#if draftPostView}
        <Post
          post={draftPostView}
          actions={false}
          view="cozy"
          showFullBody={true}
          showReadMore={false}
          linkOverride={$page.url.pathname}
        />
      {/if}
    </div>
    {#if isDraftOwner}
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
  {/if}
</div>
