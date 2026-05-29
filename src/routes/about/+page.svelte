<script>
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import StaticPageArticle from '$lib/components/static-pages/StaticPageArticle.svelte'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'
  import { EDITABLE_STATIC_PAGE_META } from '$lib/staticPageContent'

  export let data

  const meta = EDITABLE_STATIC_PAGE_META.about
  const title = `${meta.heading} — ${env.PUBLIC_SITE_TITLE || 'Тамбур'}`
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
