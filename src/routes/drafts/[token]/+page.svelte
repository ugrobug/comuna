<script lang="ts">
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { Button, Spinner } from 'mono-svelte'
  import { fetchSharedDraft, refreshSiteUser, type SiteUserPost } from '$lib/siteAuth'
  import { siteUserPostToPostView } from '$lib/siteUserPostPreview'
  import { onMount } from 'svelte'

  export let data: { shareToken: string }

  let loading = true
  let draft: SiteUserPost | null = null
  let loadError = ''
  let loggedIn = false

  $: draftPostView = draft ? siteUserPostToPostView(draft) : null

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

<div class="mx-auto flex max-w-4xl flex-col gap-6">
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
    <div class="rounded-2xl border border-slate-200 bg-white px-4 py-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 sm:px-6 sm:py-6">
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
  {/if}
</div>
