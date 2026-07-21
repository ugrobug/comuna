<script lang="ts">
  import { page } from '$app/stores'
  import { env } from '$env/dynamic/public'
  import type { BackendStaticPageLanguageVersion } from '$lib/api/backend'

  export let title: string = ''
  export let description: string = ''
  export let language: string = 'ru'
  export let languageVersions: BackendStaticPageLanguageVersion[] = []

  $: siteBaseUrl = (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '')
  $: versions = Array.isArray(languageVersions)
    ? languageVersions.filter((version) => version?.hreflang && version?.path)
    : []
  $: originalVersion = versions.find((version) => version?.is_original) ?? versions[0]
  $: currentVersion = versions.find((version) => version?.language === language)
  $: canonicalPath = currentVersion?.path || originalVersion?.path || $page.url.pathname
  $: canonicalUrl = new URL(canonicalPath, `${siteBaseUrl}/`).toString()
  $: alternateLinks = [
    ...versions.map((version) => ({
      hreflang: version.hreflang,
      href: new URL(version.path, `${siteBaseUrl}/`).toString(),
    })),
    ...(originalVersion
      ? [
          {
            hreflang: 'x-default',
            href: new URL(originalVersion.path, `${siteBaseUrl}/`).toString(),
          },
        ]
      : []),
  ]
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
  {#each alternateLinks as alternate (alternate.hreflang)}
    <link rel="alternate" hreflang={alternate.hreflang} href={alternate.href} />
  {/each}
</svelte:head>
