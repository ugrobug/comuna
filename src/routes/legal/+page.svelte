<script lang="ts">
  import SiteCard from '$lib/components/lemmy/SiteCard.svelte'
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { site } from '$lib/lemmy'
  import { t } from '$lib/translations'
  import { Button, Modal, Spinner } from 'mono-svelte'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'

  let siteOpen: boolean = false

  const title = `Правовая информация — ${env.PUBLIC_SITE_TITLE || 'Comuna'}`
  const description = 'Юридическая информация и документы проекта Comuna.'
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
</script>

<div class="flex flex-row w-full">
  {#if $site}
    <div class="flex flex-col flex-1 gap-4">
      <Header pageHeader>{$t('routes.legal.title')}</Header>
      <Markdown
        source={$site.site_view.local_site.legal_information ??
          $t('routes.legal.noLegal')}
      />
    </div>
  {:else}
    <Spinner />
  {/if}
</div>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
