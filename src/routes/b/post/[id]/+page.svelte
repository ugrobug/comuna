<script lang="ts">
  import { env } from '$env/dynamic/public'
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import PostComments from '$lib/components/site/PostComments.svelte'
  import { backendPostToPostView, buildBackendPostPath, buildPostReadUrl, buildPostViewUrl } from '$lib/api/backend'
  import { siteToken } from '$lib/siteAuth'
  import { deserializeEditorModel } from '$lib/util'

  export let data

  let postView: any = backendPostToPostView(data.post)
  let lastVisitedPostId: number | null = null

  const stripHtml = (value: string) =>
    value.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim()

  const extractFirstImage = (value: string) => {
    const match = value.match(/<img[^>]+src=["']([^"']+)["']/i)
    return match ? match[1] : null
  }

  const buildDescription = (value: string, max = 200) => {
    const raw = (value || '').trim()
    if (!raw) return ''

    const parseEditorPayload = (candidate: string): any | null => {
      try {
        const parsed = JSON.parse(candidate)
        if (parsed && typeof parsed === 'object' && Array.isArray(parsed.blocks)) {
          return parsed
        }
      } catch {
        // noop
      }

      if (!/^[A-Za-z0-9+/_-]*={0,2}$/.test(candidate)) return null
      const decoded = deserializeEditorModel(candidate)
      if (decoded && typeof decoded === 'object' && Array.isArray(decoded.blocks)) {
        return decoded
      }
      return null
    }

    const editorPayload = parseEditorPayload(raw)
    if (editorPayload) {
      const extraDescription = stripHtml(
        String(
          editorPayload?.additional?.metaDescription ||
            editorPayload?.additional?.previewDescription ||
            ''
        )
      )
      if (extraDescription) {
        return extraDescription.length <= max
          ? extraDescription
          : `${extraDescription.slice(0, max).trim()}…`
      }

      const blocks = Array.isArray(editorPayload.blocks) ? editorPayload.blocks : []
      for (const block of blocks) {
        const type = String(block?.type || '').toLowerCase()
        const data = block?.data || {}
        if (type === 'paragraph' && typeof data.text === 'string') {
          const clean = stripHtml(data.text)
          if (clean) {
            return clean.length <= max ? clean : `${clean.slice(0, max).trim()}…`
          }
        }
        if (type === 'header' && typeof data.text === 'string') {
          const clean = stripHtml(data.text)
          if (clean) {
            return clean.length <= max ? clean : `${clean.slice(0, max).trim()}…`
          }
        }
      }
    }

    const text = stripHtml(raw)
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

  const isPreviewImageCandidate = (value: string | null | undefined) => {
    if (!value) return false
    try {
      const imageUrl = new URL(value)
      return imageUrl.protocol === 'http:' || imageUrl.protocol === 'https:'
    } catch {
      return false
    }
  }

  const imageMimeByExtension = (value: string | null | undefined) => {
    if (!value) return ''
    const normalized = value.toLowerCase()
    if (normalized.includes('.png')) return 'image/png'
    if (normalized.includes('.jpg') || normalized.includes('.jpeg')) return 'image/jpeg'
    if (normalized.includes('.webp')) return 'image/webp'
    if (normalized.includes('.gif')) return 'image/gif'
    return ''
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
  $: postView = backendPostToPostView(data.post)
  $: authorName = data.post?.author?.title || data.post?.author?.username || 'Автор'
  $: authorUrl = data.post?.author?.username
    ? `${siteBaseUrl}/${data.post.author.username}`
    : undefined
  $: templatePoster =
    data.post?.template?.type === 'movie_review'
      ? (data.post?.template?.data?.poster_url ?? '')
      : data.post?.template?.type === 'music_release'
        ? (data.post?.template?.data?.cover_image_url ?? '')
        : ''
  $: firstImage = extractFirstImage(data.post?.content || '')
  $: firstImageAbsolute = ensureAbsoluteUrl(templatePoster || firstImage || '', siteBaseUrl)
  $: ogImage = isPreviewImageCandidate(firstImageAbsolute) ? firstImageAbsolute : ''
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
          image: ogImage ? [ogImage] : undefined,
        })
      : ''
  $: articleSchemaTag = buildJsonLdTag(articleSchema)

  const trackPostVisit = async (postId: number) => {
    try {
      const sessionKey = `comuna:post-view:${postId}`
      const alreadyCounted = sessionStorage.getItem(sessionKey) === '1'
      if (!alreadyCounted) {
        sessionStorage.setItem(sessionKey, '1')
        const viewResponse = await fetch(buildPostViewUrl(postId), { method: 'POST' })
        if (viewResponse.ok) {
          const payload = await viewResponse.json()
          if (typeof payload?.views_count === 'number' && data?.post?.id === postId) {
            postView = {
              ...postView,
              counts: {
                ...postView.counts,
                views: payload.views_count,
              },
            }
          }
        }
      }
    } catch (error) {
      console.error('Failed to record post view:', error)
    }

    const token = $siteToken
    if (!token) return
    try {
      await fetch(buildPostReadUrl(postId), {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
      })
    } catch (error) {
      console.error('Failed to mark post as read:', error)
    }
  }

  $: if (browser && data?.post?.id && data.post.id !== lastVisitedPostId) {
    lastVisitedPostId = data.post.id
    void trackPostVisit(data.post.id)
  }
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
  {#if ogImage}
    <meta property="og:image" content={ogImage} />
    <meta property="og:image:secure_url" content={ogImage} />
    <meta property="og:image:width" content="1200" />
    <meta property="og:image:height" content="630" />
    {#if ogImageType}
      <meta property="og:image:type" content={ogImageType} />
    {/if}
  {/if}
  {#if data.post?.created_at}
    <meta property="article:published_time" content={data.post.created_at} />
  {/if}
  {#if data.post?.rubric}
    <meta property="article:section" content={data.post.rubric} />
  {/if}

  <meta name="twitter:card" content={ogImage ? 'summary_large_image' : 'summary'} />
  {#if postTitle}
    <meta name="twitter:title" content={postTitle} />
  {/if}
  <meta name="twitter:description" content={metaDescription} />
  {#if ogImage}
    <meta name="twitter:image" content={ogImage} />
  {/if}

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
