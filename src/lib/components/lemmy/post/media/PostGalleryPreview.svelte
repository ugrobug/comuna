<script lang="ts">
  import { showImage } from '$lib/components/ui/ExpandableImage.svelte'
  import type { GalleryPreviewImage } from '$lib/gallery/types'

  export let images: GalleryPreviewImage[]
  export let blur = false
  $: visible = images.slice(0, 4)
</script>

<div class="gallery-preview" aria-label={`Галерея: ${images.length} изображений`}>
  {#each visible as image, index}
    <button
      type="button"
      class="gallery-preview__item"
      aria-label={`Открыть изображение ${index + 1} из ${images.length}`}
      on:click|stopPropagation={() => showImage(image.url, image.alt || '', images)}
    >
      <img src={image.preview_url || image.url} alt={image.alt || ''} width="640" height="480"
        loading="lazy" decoding="async" class:blurred={blur} />
      {#if index === 3 && images.length > 4}
        <span class="gallery-preview__more">+{images.length - 4}</span>
      {/if}
    </button>
  {/each}
</div>

<style>
  .gallery-preview { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 3px;
    overflow: hidden; border-radius: .75rem; width: 100%; }
  .gallery-preview__item { position: relative; overflow: hidden; min-width: 0; aspect-ratio: 4 / 3; background: #80808018; }
  .gallery-preview__item:first-child:nth-last-child(3) { grid-row: span 2; aspect-ratio: auto; }
  img { display: block; width: 100%; height: 100%; object-fit: cover; }
  .blurred { filter: blur(64px); }
  .gallery-preview__more { position: absolute; inset: 0; display: grid; place-items: center;
    background: #0007; color: white; font-size: 2rem; font-weight: 600; }
  button:focus-visible { outline: 3px solid #3b82f6; outline-offset: -3px; }
</style>
