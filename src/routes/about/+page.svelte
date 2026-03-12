<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import SectionTitle from '$lib/components/ui/SectionTitle.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import StaticPageArticle from '$lib/components/static-pages/StaticPageArticle.svelte'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import { backendPostToPostView, buildBackendPostPath } from '$lib/api/backend'
  import { userSettings } from '$lib/settings'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'
  import { EDITABLE_STATIC_PAGE_META } from '$lib/staticPageContent'

  export let data

  const meta = EDITABLE_STATIC_PAGE_META.about
  const title = `${meta.heading} — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`

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
</script>

<div class="flex max-w-3xl flex-col gap-6">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">{meta.heading}</h1>
  </Header>

  <StaticPageArticle heading={meta.heading} pageContent={data?.pageContent ?? ''} />

  <SectionTitle class="text-lg font-semibold">Обновления Comuna</SectionTitle>
  {#if visiblePosts?.length}
    <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
      {#each visiblePosts as backendPost (backendPost.id)}
        {@const postView = /** @type {any} */ (backendPostToPostView(backendPost, backendPost.author))}
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
  <meta name="description" content={meta.description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={meta.description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
