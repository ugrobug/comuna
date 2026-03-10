<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import SectionTitle from '$lib/components/ui/SectionTitle.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import PostBody from '$lib/components/lemmy/post/PostBody.svelte'
  import EditorJS from '$lib/components/editor/EditorJS.svelte'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import { backendPostToPostView, buildBackendPostPath } from '$lib/api/backend'
  import { refreshSiteUser, siteUser, updateStaticPageContent } from '$lib/siteAuth'
  import { userSettings } from '$lib/settings'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'
  import { Button, toast } from 'mono-svelte'
  import { onMount } from 'svelte'

  export let data

  const title = `О проекте — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  const description =
    'Comuna помогает Telegram-каналам получать органический трафик из поисковых систем за счет публикации контента на сайте.'
  let isEditing = false
  let isSaving = false
  let pageContent = data?.pageContent ?? ''
  let editorValue = pageContent
  $: canEdit = !!$siteUser?.is_staff
  $: hiddenAuthorKeys = new Set(
    ($userSettings.hiddenAuthors ?? []).map((value) => value.toLowerCase())
  )
  $: visiblePosts = (data?.posts ?? []).filter((backendPost) => {
    const key = (backendPost.author?.username ?? '').trim().toLowerCase()
    return !key || !hiddenAuthorKeys.has(key)
  })
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
  onMount(() => {
    refreshSiteUser().catch(() => null)
  })

  const startEditing = () => {
    editorValue = pageContent
    isEditing = true
  }

  const cancelEditing = () => {
    editorValue = pageContent
    isEditing = false
  }

  const savePage = async () => {
    if (!canEdit) return
    isSaving = true
    try {
      const updated = await updateStaticPageContent('about', {
        title: 'О проекте',
        content: editorValue,
      })
      pageContent = updated.content ?? ''
      editorValue = pageContent
      isEditing = false
      toast({ content: 'Страница сохранена', type: 'success' })
    } catch (error) {
      toast({
        content: error instanceof Error ? error.message : 'Не удалось сохранить страницу',
        type: 'error',
      })
    } finally {
      isSaving = false
    }
  }
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <div class="flex w-full items-center justify-between gap-3">
      <h1 class="text-2xl font-bold">О проекте</h1>
      {#if canEdit && !isEditing}
        <Button size="sm" color="secondary" on:click={startEditing}>Редактировать</Button>
      {/if}
    </div>
  </Header>

  {#if isEditing}
    <div class="rounded-xl border border-slate-200 dark:border-zinc-800 p-4">
      <EditorJS bind:value={editorValue} showPostSettings={false} />
      <div class="mt-4 flex items-center gap-2">
        <Button on:click={savePage} disabled={isSaving}>
          {#if isSaving}
            Сохранение...
          {:else}
            Сохранить
          {/if}
        </Button>
        <Button color="secondary" on:click={cancelEditing} disabled={isSaving}>
          Отмена
        </Button>
      </div>
    </div>
  {:else}
    <div class="text-base leading-relaxed">
      <PostBody body={pageContent} showFullBody={true} />
    </div>
  {/if}

  <SectionTitle class="text-lg font-semibold">Обновления Comuna</SectionTitle>
  {#if visiblePosts?.length}
    <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
      {#each visiblePosts as backendPost (backendPost.id)}
        {@const postView = backendPostToPostView(backendPost, backendPost.author)}
        <Post
          post={postView}
          class="feed-shortcut-post"
          view="cozy"
          actions={true}
          showReadMore={false}
          showFullBody={false}
          linkOverride={buildBackendPostPath(backendPost)}
          userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
        />
      {/each}
    </div>
  {:else}
    <p class="text-base text-slate-500">Пока нет обновлений.</p>
  {/if}
</div>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
