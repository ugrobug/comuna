<script>
  import StaticPageArticle from '$lib/components/static-pages/StaticPageArticle.svelte'
  import { env } from '$env/dynamic/public'
  import { EDITABLE_STATIC_PAGE_META } from '$lib/staticPageContent'

  export let data

  const meta = EDITABLE_STATIC_PAGE_META.rules
  const seoTitle = `${meta.heading} — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
</script>

<div class="flex max-w-3xl flex-col gap-6">
  <StaticPageArticle heading={meta.heading} pageContent={data?.pageContent ?? ''} />
</div>

<svelte:head>
  <title>{seoTitle}</title>
  <meta name="description" content={meta.description} />
  <meta property="og:title" content={seoTitle} />
  <meta property="og:description" content={meta.description} />
  <meta property="og:type" content="website" />
</svelte:head>
