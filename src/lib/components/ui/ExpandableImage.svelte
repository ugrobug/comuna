<script lang="ts" context="module">
  import { pushState } from '$app/navigation'

  export type ExpandableImageGalleryItem = {
    url: string
    alt?: string | null
  }

  export function normalizeGalleryItems(
    items: Array<string | ExpandableImageGalleryItem> = [],
    fallbackUrl = '',
    fallbackAlt = ''
  ): ExpandableImageGalleryItem[] {
    const normalized: ExpandableImageGalleryItem[] = []
    const seen = new Set<string>()

    for (const item of items) {
      const url = typeof item === 'string' ? item : item?.url
      if (!url || seen.has(url)) continue
      seen.add(url)
      normalized.push({
        url,
        alt: typeof item === 'string' ? '' : item.alt || '',
      })
    }

    if (fallbackUrl && !seen.has(fallbackUrl)) {
      normalized.unshift({ url: fallbackUrl, alt: fallbackAlt })
    }

    return normalized
  }

  export function showImage(
    url: string,
    alt: string = '',
    gallery: Array<string | ExpandableImageGalleryItem> = []
  ) {
    const openImageGallery = normalizeGalleryItems(gallery, url, alt)
    pushState('', {
      openImage: url,
      openImageAlt: alt,
      openImageGallery,
    })
  }
</script>

<script lang="ts">
  import { replaceState } from '$app/navigation'
  import { page } from '$app/stores'
  import { Button, Material, toast } from 'mono-svelte'
  import {
    ArrowDownTray,
    ChevronLeft,
    ChevronRight,
    Icon,
    MagnifyingGlassMinus,
    MagnifyingGlassPlus,
    Share,
    XMark,
  } from 'svelte-hero-icons'
  import { backOut, elasticOut, expoOut } from 'svelte/easing'
  import { fade, fly, scale } from 'svelte/transition'
  import { focusTrap } from 'svelte-focus-trap'
  import { t } from '$lib/translations'

  /**
   * The full-resolution image URL
   */
  export let alt: string = ''

  let zoomed = false
  let sharing = false
  let lastOpenImageUrl = ''

  $: openImageUrl = typeof $page.state.openImage === 'string' ? $page.state.openImage : ''
  $: openImageAlt = typeof $page.state.openImageAlt === 'string' ? $page.state.openImageAlt : alt
  $: galleryItems = normalizeGalleryItems($page.state.openImageGallery || [], openImageUrl, openImageAlt)
  $: currentIndex = Math.max(
    0,
    galleryItems.findIndex((item) => item.url === openImageUrl)
  )
  $: currentImage = galleryItems[currentIndex] || { url: openImageUrl, alt: openImageAlt }
  $: hasGalleryNavigation = galleryItems.length > 1 && Boolean(openImageUrl)
  $: if (openImageUrl !== lastOpenImageUrl) {
    lastOpenImageUrl = openImageUrl
    zoomed = false
  }

  function closeImage() {
    history.back()
  }

  function showGalleryImage(index: number) {
    if (!hasGalleryNavigation) return
    const nextIndex = (index + galleryItems.length) % galleryItems.length
    const nextImage = galleryItems[nextIndex]
    if (!nextImage?.url) return
    replaceState('', {
      ...$page.state,
      openImage: nextImage.url,
      openImageAlt: nextImage.alt || '',
      openImageGallery: galleryItems,
    })
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key == 'Escape') {
      closeImage()
      return
    }
    if (!hasGalleryNavigation) return
    if (e.key == 'ArrowLeft') {
      e.preventDefault()
      showGalleryImage(currentIndex - 1)
    } else if (e.key == 'ArrowRight') {
      e.preventDefault()
      showGalleryImage(currentIndex + 1)
    }
  }

  async function downloadImage(url: string) {
    sharing = true
    const response = await fetch(url)

    const blob = await response.blob()

    const file = new File([blob], `photon_image.webp`, { type: blob.type })

    sharing = false
    return file
  }
</script>

{#if openImageUrl}
  <!-- svelte-ignore a11y-no-noninteractive-tabindex -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-positive-tabindex -->
  <div
    class="fixed top-0 left-0 w-screen h-[100svh] overflow-auto bg-white/50 dark:bg-black/50
    flex flex-col z-[100] backdrop-blur-sm"
    transition:fade={{ duration: 150 }}
    on:click={closeImage}
    on:keydown={handleKeydown}
    use:focusTrap
  >
    {#if hasGalleryNavigation}
      <button
        type="button"
        class="fixed left-3 top-1/2 z-20 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-full border border-white/20 bg-black/55 text-white shadow-lg backdrop-blur transition-colors hover:bg-black/75 sm:left-6"
        aria-label="Предыдущее изображение"
        title="Предыдущее изображение"
        on:click={(e) => {
          e.stopPropagation()
          showGalleryImage(currentIndex - 1)
        }}
      >
        <Icon src={ChevronLeft} size="24" mini />
      </button>
      <button
        type="button"
        class="fixed right-3 top-1/2 z-20 grid h-11 w-11 -translate-y-1/2 place-items-center rounded-full border border-white/20 bg-black/55 text-white shadow-lg backdrop-blur transition-colors hover:bg-black/75 sm:right-6"
        aria-label="Следующее изображение"
        title="Следующее изображение"
        on:click={(e) => {
          e.stopPropagation()
          showGalleryImage(currentIndex + 1)
        }}
      >
        <Icon src={ChevronRight} size="24" mini />
      </button>
    {/if}
    <img
      width={400}
      height={400}
      src={openImageUrl}
      class="{zoomed
        ? 'object-cover'
        : 'object-contain'} max-w-max mx-auto my-auto overscroll-contain bg-white dark:bg-zinc-900"
      class:max-w-screen-md={!zoomed}
      class:w-full={!zoomed}
      class:min-h-screen={zoomed}
      class:min-w-screen={zoomed}
      class:w-max={zoomed}
      transition:scale={{ start: 0.95, easing: expoOut, duration: 250 }}
      alt={currentImage.alt || openImageAlt || ''}
    />
    <div
      class="sticky z-10 bottom-4 left-1/2 -translate-x-1/2 w-max"
      transition:fly={{ duration: 350, y: 14, easing: backOut }}
    >
      <Material
        class="gap-1 p-2 flex flex-row items-center dark:bg-zinc-950"
        rounding="full"
        padding="none"
        color="uniform"
        on:click={(e) => e.stopPropagation()}
      >
        {#if hasGalleryNavigation}
          <div class="px-3 text-sm font-medium text-slate-700 dark:text-zinc-200">
            {currentIndex + 1}/{galleryItems.length}
          </div>
        {/if}
        <Button
          download
          href={openImageUrl}
          color="tertiary"
          size="square-lg"
          rounding="pill"
          title={$t('routes.profile.media.download')}
        >
          <Icon src={ArrowDownTray} size="20" micro />
        </Button>
        <Button
          on:click={async () => {
            if (navigator.share) {
              const file = await downloadImage(openImageUrl)

              navigator?.share?.({
                files: [file],
              })
            } else {
              navigator.clipboard.writeText(openImageUrl)
              toast({ content: $t('toast.copied') })
            }
          }}
          color="tertiary"
          size="square-lg"
          rounding="pill"
          title={$t('post.actions.more.share')}
          loading={sharing}
        >
          <Icon src={Share} size="20" micro slot="prefix" />
        </Button>
        <Button
          on:click={() => {
            zoomed = !zoomed
          }}
          color="tertiary"
          size="square-lg"
          rounding="pill"
          title={zoomed ? $t('post.image.zoomOut') : $t('post.image.zoomIn')}
        >
          <Icon
            src={zoomed ? MagnifyingGlassMinus : MagnifyingGlassPlus}
            size="20"
            micro
          />
        </Button>
        <Button
          on:click={closeImage}
          color="tertiary"
          size="square-lg"
          rounding="pill"
          title={$t('post.image.close')}
        >
          <Icon src={XMark} size="20" micro slot="prefix" />
        </Button>
      </Material>
    </div>
  </div>
{/if}

<button on:click={closeImage} class="contents {$$props.class}">
  <slot />
</button>
