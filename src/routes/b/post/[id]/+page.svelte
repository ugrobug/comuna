<script lang="ts">
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import PostComments from '$lib/components/site/PostComments.svelte'
  import { backendPostToPostView, buildBackendPostPath } from '$lib/api/backend'

  export let data

  const postView = backendPostToPostView(data.post)

  const stripHtml = (value: string) =>
    value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()

  const extractFirstImage = (value: string) => {
    const match = value.match(/<img[^>]+src=["']([^"']+)["']/i)
    return match ? match[1] : null
  }

  const buildDescription = (value: string, max = 200) => {
    const text = stripHtml(value)
    if (!text) return ''
    if (text.length <= max) return text
    return `${text.slice(0, max).trim()}…`
  }

  const toJsonLd = (value: unknown) =>
    JSON.stringify(value)
      .replace(/</g, '\\u003c')
      .replace(/>/g, '\\u003e')
      .replace(/&/g, '\\u0026')

  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalUrl = `${siteBaseUrl}${$page.url.pathname}`
  $: authorName = data.post?.author?.title || data.post?.author?.username || 'Автор'
  $: authorUrl = data.post?.author?.username
    ? `${siteBaseUrl}/${data.post.author.username}`
    : undefined
  $: firstImage = extractFirstImage(data.post?.content || '')
  $: postDescription = buildDescription(data.post?.content || '')
  $: articleSchema =
    data.post
      ? toJsonLd({
          '@context': 'https://schema.org',
          '@type': 'BlogPosting',
          headline: data.post.title,
          name: data.post.title,
          description: postDescription || undefined,
          url: canonicalUrl,
          mainEntityOfPage: { '@type': 'WebPage', '@id': canonicalUrl },
          datePublished: data.post.created_at,
          dateModified: data.post.created_at,
          inLanguage: 'ru-RU',
          articleSection: data.post.rubric || undefined,
          author: {
            '@type': 'Person',
            name: authorName,
            url: authorUrl,
            sameAs: data.post.author?.channel_url || undefined,
          },
          publisher: {
            '@type': 'Organization',
            name: env.PUBLIC_SITE_TITLE || 'Comuna',
            url: siteBaseUrl,
            logo: {
              '@type': 'ImageObject',
              url: `${siteBaseUrl}/favicon_120x120.svg`,
            },
          },
          image: firstImage ? [firstImage] : undefined,
        })
      : ''
  $: articleSchemaTag = articleSchema
    ? `<script type="application/ld+json">${articleSchema}</script>`
    : ''
</script>

<svelte:head>
  {@html articleSchemaTag}
</svelte:head>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Публикация</h1>
  </Header>

  <Post
    post={postView}
    view="cozy"
    actions={true}
    showReadMore={false}
    showFullBody={true}
    linkOverride={buildBackendPostPath(data.post)}
    userUrlOverride={data.post.author?.username ? `/${data.post.author.username}` : undefined}
    communityUrlOverride={data.post.rubric_slug ? `/rubrics/${data.post.rubric_slug}/posts` : undefined}
    subscribeUrl={data.post.channel_url ?? data.post.author?.channel_url}
    subscribeLabel="Подписаться"
  />

  <PostComments postId={data.post.id} postAuthor={data.post.author?.username ?? null} />
</div>
