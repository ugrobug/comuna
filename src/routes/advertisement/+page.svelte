<script>
  import StaticPageArticle from '$lib/components/static-pages/StaticPageArticle.svelte'
  import StaticPageSeo from '$lib/components/static-pages/StaticPageSeo.svelte'
  import { brandNameForLanguage } from '$lib/brand'
  import { EDITABLE_STATIC_PAGE_META } from '$lib/staticPageContent'
  import { locale } from '$lib/translations'

  export let data

  const meta = EDITABLE_STATIC_PAGE_META.advertisement
  $: pageHeading = data?.pageTitle || meta.heading
  $: seoTitle = `${pageHeading} — ${brandNameForLanguage($locale)}`
</script>

<div class="flex max-w-3xl flex-col gap-6">
  <StaticPageArticle heading={pageHeading} pageContent={data?.pageContent ?? ''} />
</div>

<StaticPageSeo
  title={seoTitle}
  description={meta.description}
  language={data?.language}
  languageVersions={data?.languageVersions}
/>
