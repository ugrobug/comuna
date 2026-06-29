<script lang="ts">
  import { photonify } from './plugins'
  import { getSafeUrl, isExternalUrl } from '$lib/security/url'

  export let href = ''
  export let title = undefined

  export const parseURL = (href: string) => {
    try {
      return new URL(href)
    } catch (e) {
      return undefined
    }
  }

  $: photonified = photonify(href)
  $: safeHref = getSafeUrl(photonified ?? href, {
    allowedProtocols: ['http:', 'https:', 'mailto:'],
    allowRelative: true,
    normalizeBareExternal: true,
  })
  $: externalHref = isExternalUrl(safeHref)
</script>

{#if safeHref}
  <a
    href={safeHref}
    target={externalHref ? '_blank' : undefined}
    {title}
    rel="nofollow ugc noopener noreferrer"
    class="hover:underline text-sky-600 dark:text-sky-500 no-underline"
  >
    <slot />
  </a>
{:else}
  <span class="text-slate-700 dark:text-zinc-300">
    <slot />
  </span>
{/if}
