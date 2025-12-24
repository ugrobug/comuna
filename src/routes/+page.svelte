<script lang="ts" context="module">
</script>

<script lang="ts">
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { t } from '$lib/translations.js'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { backendPostToPostView } from '$lib/api/backend'

  export let data

  // Определяем канонический URL для главной страницы
  $: canonicalUrl = new URL('/', $page.url.origin).toString();
</script>
<div class="flex flex-col gap-2 max-w-full w-full min-w-0">
  <header class="flex flex-col gap-4 relative">
    <Header pageHeader>
      {$t('routes.frontpage.title')}
    </Header>
  </header>
  {#if data.posts?.length}
    <div class="flex flex-col gap-6">
      {#each data.posts as backendPost (backendPost.id)}
        {@const postView = backendPostToPostView(backendPost, backendPost.author)}
        <Post
          post={postView}
          view="cozy"
          actions={true}
          linkOverride={`/b/post/${backendPost.id}`}
          userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
          communityUrlOverride={backendPost.rubric_slug ? `/rubrics/${backendPost.rubric_slug}/posts` : undefined}
          subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
          subscribeLabel="Подписаться"
        />
      {/each}
    </div>
  {:else}
    <div class="text-base text-slate-500">Пока нет публикаций.</div>
  {/if}
</div>

<svelte:head>
  <title>{env.PUBLIC_SITE_TITLE}</title>
  <meta name="description" content={env.PUBLIC_SITE_DESCRIPTION} />
  
  <!-- Open Graph теги -->
  <meta property="og:title" content={env.PUBLIC_OG_TITLE} />
  <meta property="og:description" content={env.PUBLIC_OG_DESCRIPTION} />
  <meta property="og:image" content={env.PUBLIC_OG_IMAGE} />
  <meta property="og:url" content={env.PUBLIC_OG_URL} />
  <meta property="og:type" content="website" />
  
  <!-- Twitter теги -->
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content={env.PUBLIC_TWITTER_TITLE} />
  <meta name="twitter:description" content={env.PUBLIC_TWITTER_DESCRIPTION} />
  
  <!-- Дополнительные мета-теги -->
  <meta name="robots" content="index, follow" />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
