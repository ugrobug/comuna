<script lang="ts">
  import { optimizeImageURL } from '$lib/components/lemmy/post/helpers'
  import { findClosestNumber } from '$lib/util.js'
  import { browser } from '$app/environment'
  import { onMount } from 'svelte'

  const sizes = [16, 24, 32, 48, 64, 96, 128, 256, 512]

  export let url: string | undefined = undefined
  export let alt: string = ''
  export let title: string = ''
  export let circle: boolean = true
  export let width: number = 28
  export let res: number | undefined = undefined
  export let class_: string = ''

  // Базовые классы для всех аватаров
  const baseClasses = "aspect-square object-cover overflow-hidden flex-shrink-0 border border-slate-300 dark:border-zinc-700"
  let svgMarkup = ''

  const optimizeUrl = (
    url: string | undefined,
    res: number
  ): string | undefined => {
    if (url === undefined) return

    try {
      const urlObj = new URL(url)
      urlObj.searchParams.append('format', 'webp')
      if (res > -1) {
        urlObj.searchParams.append(
          'thumbnail',
          findClosestNumber(sizes, res).toString()
        )
      }

      return urlObj.toString()
    } catch (e) {
      return undefined
    }
  }

  $: optimizedURLs = [2, 3, 6, -1].map((n) =>
    optimizeUrl(url, (res || width) * n)
  )

  function generateSrcSet(url: string, baseWidth: number) {
    const sizes = [
      { width: baseWidth, multiplier: '1x' },
      { width: baseWidth * 1.5, multiplier: '2x' },
      { width: baseWidth * 4, multiplier: '4x' },
      { width: baseWidth * 6, multiplier: '6x' }
    ]
    
    return sizes
      .map(size => `${optimizeImageURL(url, size.width)} ${size.multiplier}`)
      .join(', ')
  }

  const getInitials = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return '?'
    const parts = trimmed.split(/\s+/).filter(Boolean)
    const letters = parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? '')
    return letters.join('') || trimmed[0]?.toUpperCase() || '?'
  }

  const fallbackInitials = getInitials(alt || title || '')

  onMount(async () => {
    if (!browser) return
    try {
      const [{ createAvatar }, initials] = await Promise.all([
        import('@dicebear/core'),
        import('@dicebear/initials'),
      ])
      svgMarkup = createAvatar(initials, { seed: alt || title || fallbackInitials }).toString()
    } catch (error) {
      svgMarkup = ''
    }
  })
</script>

{#if url}
  <img
    loading="lazy"
    srcset={generateSrcSet(url, width)}
    src={optimizeImageURL(url, width)}
    {alt}
    {width}
    title=""
    class="{baseClasses} {circle ? 'rounded-full' : 'rounded-lg'} {class_}"
    style="width: {width}px; height: {width}px"
  />
{:else}
  <div
    class="{baseClasses} {circle ? 'rounded-full' : 'rounded-lg'}"
    style="width: {width}px; height: {width}px"
  >
    {#if browser && svgMarkup}
      {@html svgMarkup}
    {:else}
      <span class="w-full h-full flex items-center justify-center text-xs font-semibold text-slate-600 dark:text-zinc-200">
        {fallbackInitials}
      </span>
    {/if}
  </div>
{/if}
