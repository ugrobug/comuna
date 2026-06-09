<script lang="ts">
  import { optimizeImageURL } from '$lib/components/lemmy/post/helpers'
  import { findClosestNumber } from '$lib/util.js'

  const sizes = [16, 24, 32, 48, 64, 96, 128, 256, 512]

  export let url: string | undefined = undefined
  export let alt: string = ''
  export let title: string = ''
  export let circle: boolean = true
  export let width: number = 28
  export let res: number | undefined = undefined
  export let class_: string = ''
  let className = ''
  export { className as class }
  export let slot: string | undefined = undefined
  $: void slot

  // Базовые классы для всех аватаров
  const baseClasses = "aspect-square object-cover overflow-hidden flex-shrink-0 border border-slate-300 dark:border-zinc-700"

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

  const hueFor = (value: string) => {
    let hash = 0
    for (const char of value || '?') {
      hash = (hash * 31 + char.charCodeAt(0)) % 360
    }
    return hash
  }

  $: fallbackSeed = alt || title || ''
  $: fallbackInitials = getInitials(fallbackSeed)
  $: fallbackHue = hueFor(fallbackSeed || fallbackInitials)
  $: extraClasses = [class_, className].filter(Boolean).join(' ')
  $: normalizedUrl = (url || '').trim() || undefined
  let failedUrl: string | undefined = undefined
  $: imageUrl = normalizedUrl && failedUrl !== normalizedUrl ? normalizedUrl : undefined

  function handleImageError() {
    failedUrl = imageUrl
  }
</script>

{#if imageUrl}
  <img
    loading="lazy"
    srcset={generateSrcSet(imageUrl, width)}
    src={optimizeImageURL(imageUrl, width)}
    {alt}
    {width}
    title=""
    class="{baseClasses} {circle ? 'rounded-full' : 'rounded-lg'} {extraClasses}"
    style="width: {width}px; height: {width}px"
    on:error={handleImageError}
  />
{:else}
  <div
    class="{baseClasses} {circle ? 'rounded-full' : 'rounded-lg'} flex items-center justify-center text-xs font-semibold text-white {extraClasses}"
    style="width: {width}px; height: {width}px; background: linear-gradient(135deg, hsl({fallbackHue} 72% 42%), hsl({(fallbackHue + 42) % 360} 72% 54%));"
    aria-label={alt || title || 'Avatar'}
  >
    <span>{fallbackInitials}</span>
  </div>
{/if}
