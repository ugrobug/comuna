<script>
  import StaticPageArticle from '$lib/components/static-pages/StaticPageArticle.svelte'
  import { brandNameForLanguage } from '$lib/brand'
  import { APPS_PAGE_LOCALIZATION } from '$lib/staticPageContent'
  import { normalizePostLanguage } from '$lib/postLanguages'
  import { locale } from '$lib/translations'

  export let data

  $: meta = APPS_PAGE_LOCALIZATION[normalizePostLanguage(data?.language)]
  $: pageHeading = data?.pageTitle || meta.title
  $: seoTitle = `${pageHeading} — ${brandNameForLanguage($locale)}`
</script>

<div class="flex max-w-3xl flex-col gap-6">
  <StaticPageArticle heading={pageHeading} pageContent={data?.pageContent ?? ''} />
</div>

<svelte:head>
  <title>{seoTitle}</title>
  <meta name="description" content={meta.description} />
  <meta property="og:title" content={seoTitle} />
  <meta property="og:description" content={meta.description} />
  <meta property="og:type" content="website" />
</svelte:head>
