<script lang="ts">
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import PostComments from '$lib/components/site/PostComments.svelte'
  import { backendPostToPostView, buildBackendPostPath, buildPostReadUrl } from '$lib/api/backend'
  import { onMount } from 'svelte'
  import { siteToken } from '$lib/siteAuth'

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

  const ensureAbsoluteUrl = (value: string | null | undefined, baseUrl: string) => {
    if (!value) return ''
    if (value.startsWith('http://') || value.startsWith('https://')) return value
    if (value.startsWith('//')) return `https:${value}`
    if (value.startsWith('/')) return `${baseUrl}${value}`
    return `${baseUrl}/${value}`
  }

  const isReliablePreviewImage = (value: string | null | undefined, baseUrl: string) => {
    if (!value) return false
    try {
      const imageUrl = new URL(value)
      const siteUrl = new URL(baseUrl)
      const isSameHost = imageUrl.host === siteUrl.host
      const looksLikeImage = /\.(png|jpe?g|webp|gif)(\?.*)?$/i.test(imageUrl.pathname + imageUrl.search)
      return isSameHost && looksLikeImage
    } catch {
      return false
    }
  }

  const imageMimeByExtension = (value: string) => {
    const normalized = value.toLowerCase()
    if (normalized.includes('.png')) return 'image/png'
    if (normalized.includes('.jpg') || normalized.includes('.jpeg')) return 'image/jpeg'
    if (normalized.includes('.webp')) return 'image/webp'
    if (normalized.includes('.gif')) return 'image/gif'
    return 'image/png'
  }

  const toJsonLd = (value: unknown) =>
    JSON.stringify(value)
      .replace(/</g, '\\u003c')
      .replace(/>/g, '\\u003e')
      .replace(/&/g, '\\u0026')

  const buildJsonLdTag = (json: string) =>
    json ? `<script type="application/ld+json">${json}</` + `script>` : ''

  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: canonicalPath = data.canonicalId ? `/b/post/${data.canonicalId}` : $page.url.pathname
  $: canonicalUrl = `${siteBaseUrl}${canonicalPath}`
  $: authorName = data.post?.author?.title || data.post?.author?.username || 'Автор'
  $: authorUrl = data.post?.author?.username
    ? `${siteBaseUrl}/${data.post.author.username}`
    : undefined
  $: firstImage = extractFirstImage(data.post?.content || '')
  $: firstImageAbsolute = firstImage ? ensureAbsoluteUrl(firstImage, siteBaseUrl) : ''
  $: fallbackOgImage = `${siteBaseUrl}/img/og-image-1200x630.png`
  $: ogImage = isReliablePreviewImage(firstImageAbsolute, siteBaseUrl) ? firstImageAbsolute : fallbackOgImage
  $: ogImageType = imageMimeByExtension(ogImage)
  $: postDescription = buildDescription(data.post?.content || '')
  $: metaDescription = postDescription || (env.PUBLIC_SITE_DESCRIPTION || 'Публикация на Comuna')
  $: postTitle = data.post?.title || ''
  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: metaTitle = postTitle ? `${postTitle} — ${siteTitle}` : siteTitle
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
          image: [ogImage],
        })
      : ''
  $: articleSchemaTag = buildJsonLdTag(articleSchema)

  onMount(async () => {
    if (!data?.post?.id) return
    const token = $siteToken
    if (!token) return
    try {
      await fetch(buildPostReadUrl(data.post.id), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
    } catch (error) {
      console.error('Failed to mark post as read:', error)
    }
  })
</script>

<svelte:head>
  <title>{metaTitle}</title>
  <link rel="canonical" href={canonicalUrl} />
  <meta name="description" content={metaDescription} />

  <meta property="og:locale" content="ru_RU" />
  <meta property="og:site_name" content={siteTitle} />
  <meta property="og:type" content="article" />
  <meta property="og:url" content={canonicalUrl} />
  {#if postTitle}
    <meta property="og:title" content={postTitle} />
  {/if}
  <meta property="og:description" content={metaDescription} />
  <meta property="og:image" content={ogImage} />
  <meta property="og:image:secure_url" content={ogImage} />
  <meta property="og:image:width" content="1200" />
  <meta property="og:image:height" content="630" />
  <meta property="og:image:type" content={ogImageType} />
  {#if data.post?.created_at}
    <meta property="article:published_time" content={data.post.created_at} />
  {/if}
  {#if data.post?.rubric}
    <meta property="article:section" content={data.post.rubric} />
  {/if}

  <meta name="twitter:card" content="summary_large_image" />
  {#if postTitle}
    <meta name="twitter:title" content={postTitle} />
  {/if}
  <meta name="twitter:description" content={metaDescription} />
  <meta name="twitter:image" content={ogImage} />

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
