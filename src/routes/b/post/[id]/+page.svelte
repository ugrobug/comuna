<script lang="ts">
  import { env } from '$env/dynamic/public'
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { onMount } from 'svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import PostComments from '$lib/components/site/PostComments.svelte'
  import {
    backendPostCommunityPath,
    backendPostToPostView,
    buildBackendPostPath,
    buildPostDetailUrl,
    buildPostReadUrl,
    buildPostViewUrl,
    isSpecialProjectPost,
  } from '$lib/api/backend'
  import { refreshSiteUser, siteToken } from '$lib/siteAuth'
  import { parseSerializedEditorModel, looksLikeSerializedEditorModel } from '$lib/util'
  import { locale, t } from '$lib/translations'

  export let data

  let postData = data.post
  let lastRoutePost = data.post
  let postView: any = backendPostToPostView(postData, undefined, { includePreviewMedia: false })
  let lastVisitedPostId: number | null = null
  let lastAuthenticatedPostKey = ''
  let showOriginalPost = false

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
      return parseSerializedEditorModel(candidate)
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

    if (looksLikeSerializedEditorModel(raw)) return ''
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

  const formatLanguageName = (language: string, uiLocale: string) => {
    const fallback = $t(`site.language.names.${language}`) || language.toUpperCase()
    try {
      const DisplayNames = (Intl as any).DisplayNames
      if (!DisplayNames) return fallback
      const label = new DisplayNames([uiLocale || 'ru'], { type: 'language' }).of(language)
      if (!label) return fallback
      return label.charAt(0).toLocaleUpperCase(uiLocale || 'ru') + label.slice(1)
    } catch {
      return fallback
    }
  }

  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: currentLanguage = postData?.language || data.language || 'ru'
  $: translationUnavailable = Boolean(postData?.translation_unavailable)
  $: translationUnavailableTitle = $t('site.post.unavailable.title')
  $: translationUnavailableBody = $t('site.post.unavailable.body')
  $: translationUnavailableVersions = $t('site.post.unavailable.versions')
  $: canonicalPath =
    data.canonicalPath ||
    (data.canonicalId ? buildBackendPostPath(postData, currentLanguage) : $page.url.pathname)
  $: canonicalUrl = `${siteBaseUrl}${canonicalPath}`
  $: languageVersions = Array.isArray(postData?.language_versions)
    ? postData.language_versions
    : Array.isArray(data.languageVersions)
      ? data.languageVersions
      : []
  $: russianVersion = languageVersions.find((version) => version?.language === 'ru')
  $: alternateLinks = [
    ...languageVersions
      .filter((version) => version?.hreflang && version?.path)
      .map((version) => ({
        hreflang: version.hreflang,
        href: `${siteBaseUrl}${version.path}`,
      })),
    ...(russianVersion?.path
      ? [{ hreflang: 'x-default', href: `${siteBaseUrl}${russianVersion.path}` }]
      : []),
  ]
  $: availableVersionLinks = languageVersions
    .filter((version) => version?.language !== currentLanguage && version?.path)
    .map((version) => ({
      language: version.language,
      label: $t(`site.language.names.${version.language}`) || String(version.language).toUpperCase(),
      href: version.path,
    }))
  $: originalPostLanguage = postData?.original_language || 'ru'
  $: originalPostLanguageLabel = formatLanguageName(originalPostLanguage, $locale || 'ru')
  $: canShowOriginalPost = Boolean(
    postData?.is_translated &&
      postData?.original_content &&
      (postData.original_content !== postData.content || postData.original_title !== postData.title)
  )
  $: displayedPostData =
    showOriginalPost && canShowOriginalPost
      ? {
          ...postData,
          title: postData.original_title || postData.title,
          content: postData.original_content || postData.content,
        }
      : postData
  $: if (data.post !== lastRoutePost) {
    lastRoutePost = data.post
    postData = data.post
    lastAuthenticatedPostKey = ''
    showOriginalPost = false
  }
  $: if (!canShowOriginalPost && showOriginalPost) {
    showOriginalPost = false
  }
  $: postView = backendPostToPostView(displayedPostData, undefined, { includePreviewMedia: false })
  $: authorName = postData?.author?.title || postData?.author?.username || $t('site.post.author')
  $: authorUrl = postData?.author?.username
    ? `${siteBaseUrl}/${postData.author.username}`
    : undefined
  $: templatePoster =
    postData?.template?.type === 'movie_review'
      ? (postData?.template?.data?.poster_url ?? '')
      : postData?.template?.type === 'music_release'
        ? (postData?.template?.data?.cover_image_url ?? '')
        : ''
  $: firstImage = extractFirstImage(postData?.content || '')
  $: firstImageAbsolute = ensureAbsoluteUrl(templatePoster || firstImage || '', siteBaseUrl)
  $: ogImage = isPreviewImageCandidate(firstImageAbsolute) ? firstImageAbsolute : ''
  $: ogImageType = imageMimeByExtension(ogImage)
  $: postDescription = buildDescription(postData?.content || '')
  $: metaDescription = translationUnavailable
    ? translationUnavailableBody
    : postDescription || (env.PUBLIC_SITE_DESCRIPTION || $t('site.post.defaultDescription'))
  $: postTitle = postData?.title || ''
  $: socialTitle = translationUnavailable ? translationUnavailableTitle : postTitle
  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Тамбур'
  $: metaTitle = translationUnavailable
    ? `${translationUnavailableTitle} — ${siteTitle}`
    : postTitle
      ? `${postTitle} — ${siteTitle}`
      : siteTitle
  $: articleSchema =
    postData && !translationUnavailable
      ? toJsonLd({
          '@context': 'https://schema.org',
          '@type': 'BlogPosting',
          headline: postData.title,
          name: postData.title,
          description: postDescription || undefined,
          url: canonicalUrl,
          mainEntityOfPage: { '@type': 'WebPage', '@id': canonicalUrl },
          datePublished: postData.created_at,
          dateModified: postData.created_at,
          inLanguage: postData.language_locale || 'ru-RU',
          author: {
            '@type': 'Person',
            name: authorName,
            url: authorUrl,
            sameAs: postData.author?.channel_url || undefined,
          },
          publisher: {
            '@type': 'Organization',
            name: env.PUBLIC_SITE_TITLE || 'Тамбур',
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

  const refreshPostForCurrentUser = async () => {
    if (!browser || !postData?.id) return
    if (translationUnavailable) return
    const token = $siteToken
    if (!token) return
    const refreshKey = `${postData.id}:${token}`
    if (refreshKey === lastAuthenticatedPostKey) return
    lastAuthenticatedPostKey = refreshKey
    try {
      const response = await fetch(buildPostDetailUrl(postData.id, currentLanguage), {
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      const payload = await response.json().catch(() => null)
      if (response.ok && payload?.post?.id === postData.id) {
        postData = payload.post
      }
    } catch (error) {
      console.error('Failed to refresh post for current user:', error)
    }
  }

  const trackPostVisit = async (postId: number) => {
    try {
      const sessionKey = `comuna:post-view:${postId}`
      const alreadyCounted = sessionStorage.getItem(sessionKey) === '1'
      if (!alreadyCounted) {
        sessionStorage.setItem(sessionKey, '1')
        const viewResponse = await fetch(buildPostViewUrl(postId), { method: 'POST' })
        if (viewResponse.ok) {
          const payload = await viewResponse.json()
          if (typeof payload?.views_count === 'number' && postData?.id === postId) {
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

  const schedulePostVisitTracking = (postId: number) => {
    const run = () => void trackPostVisit(postId)
    if ('requestIdleCallback' in window) {
      window.requestIdleCallback(run, { timeout: 2500 })
      return
    }
    globalThis.setTimeout(run, 1000)
  }

  $: if (browser && postData?.id && !translationUnavailable && $siteToken) {
    void refreshPostForCurrentUser()
  }

  onMount(() => {
    refreshSiteUser().then(() => refreshPostForCurrentUser()).catch(() => refreshPostForCurrentUser())
  })

  $: if (browser && postData?.id && !translationUnavailable && postData.id !== lastVisitedPostId) {
    lastVisitedPostId = postData.id
    schedulePostVisitTracking(postData.id)
  }
</script>

<svelte:head>
  <title>{metaTitle}</title>
  <link rel="canonical" href={canonicalUrl} />
  {#each alternateLinks as alternate (alternate.hreflang)}
    <link rel="alternate" hreflang={alternate.hreflang} href={alternate.href} />
  {/each}
  {#if translationUnavailable}
    <meta name="robots" content="noindex, follow" />
  {/if}
  <meta name="description" content={metaDescription} />

  <meta property="og:locale" content={postData?.og_locale || 'ru_RU'} />
  <meta property="og:site_name" content={siteTitle} />
  <meta property="og:type" content="article" />
  <meta property="og:url" content={canonicalUrl} />
  {#if socialTitle}
    <meta property="og:title" content={socialTitle} />
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
  {#if postData?.created_at && !translationUnavailable}
    <meta property="article:published_time" content={postData.created_at} />
  {/if}

  <meta name="twitter:card" content={ogImage ? 'summary_large_image' : 'summary'} />
  {#if socialTitle}
    <meta name="twitter:title" content={socialTitle} />
  {/if}
  <meta name="twitter:description" content={metaDescription} />
  {#if ogImage}
    <meta name="twitter:image" content={ogImage} />
  {/if}

  {@html articleSchemaTag}
</svelte:head>

<div class="flex flex-col gap-6 max-w-3xl">
  {#if translationUnavailable}
    <section class="rounded-xl border border-slate-200 border-b-slate-300 bg-white p-5 dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900 sm:p-6">
      <h1 class="text-xl font-semibold text-slate-950 dark:text-zinc-50">
        {translationUnavailableTitle}
      </h1>
      <p class="mt-3 text-sm leading-6 text-slate-600 dark:text-zinc-300">
        {translationUnavailableBody}
      </p>
      {#if availableVersionLinks.length}
        <div class="mt-5">
          <h2 class="text-sm font-medium text-slate-900 dark:text-zinc-100">
            {translationUnavailableVersions}
          </h2>
          <div class="mt-3 flex flex-wrap gap-2">
            {#each availableVersionLinks as version (version.language)}
              <a
                class="rounded-md border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:border-zinc-600 dark:hover:bg-zinc-800"
                href={version.href}
              >
                {version.label}
              </a>
            {/each}
          </div>
        </div>
      {/if}
    </section>
  {:else}
    <div class="rounded-xl border border-slate-200 border-b-slate-300 bg-white p-4 dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900 sm:p-6">
      {#if canShowOriginalPost}
        <div class="mb-3 flex flex-wrap items-center gap-1.5 text-xs text-slate-500 dark:text-zinc-400">
          <span>{$t('site.post.originalLanguagePrefix')} {originalPostLanguageLabel}</span>
          <span aria-hidden="true">-</span>
          <button
            type="button"
            class="font-medium text-sky-700 transition hover:text-sky-800 hover:underline dark:text-sky-300 dark:hover:text-sky-200"
            on:click={() => (showOriginalPost = !showOriginalPost)}
          >
            {showOriginalPost ? $t('site.post.hideOriginal') : $t('site.post.showOriginal')}
          </button>
        </div>
      {/if}
      <Post
        class="post-detail-post-compact-top"
        post={postView}
        view="cozy"
        actions={true}
        showReadMore={false}
        showFullBody={true}
        linkOverride={canonicalPath}
        userUrlOverride={postData.author?.username ? `/${postData.author.username}` : undefined}
        communityUrlOverride={backendPostCommunityPath(postData)}
        subscribeUrl={postData.channel_url ?? postData.author?.channel_url}
        subscribeLabel={$t('site.post.subscribe')}
        hideSubscribe={isSpecialProjectPost(postData)}
      />
    </div>

    <PostComments
      postId={postData.id}
      postAuthor={postData.author?.username ?? null}
      language={currentLanguage}
    />
  {/if}
</div>

<style>
  :global(.post.post-detail-post-compact-top) {
    padding-top: 0;
  }
</style>
