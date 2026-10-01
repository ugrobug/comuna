<script lang="ts">
  import Empty from '$lib/components/helper/Empty.svelte'
  import PostLink from '$lib/components/lemmy/post/link/PostLink.svelte'
  import {
    bestImageURL,
    postLink,
    type MediaType,
    iframeType,
  } from '$lib/components/lemmy/post/helpers.js'
  import ExpandableImage, {
    showImage,
  } from '$lib/components/ui/ExpandableImage.svelte'
  import { userSettings } from '$lib/settings.js'
  import type { Post } from 'lemmy-js-client'
  import PostIframe from './PostIframe.svelte'
  import { Button, Material, modal } from 'mono-svelte'
  import { onMount } from 'svelte'
  import { ArrowDownTray, Icon } from 'svelte-hero-icons'
  import PostImage from './PostImage.svelte'
  import PostGalleryPreview from './PostGalleryPreview.svelte'
  import type { GalleryPreviewImage } from '$lib/gallery/types'

  export let view: 'card' | 'cozy' | 'list' | 'compact' = 'cozy'
  export let post: Post
  export let type: MediaType = 'none'
  export let opened: boolean | undefined = undefined
  export let blur: boolean = post.nsfw && $userSettings.nsfwBlur
  export let linkOverride: string | undefined = undefined
  $: gallery = (post as Post & { preview_gallery?: GalleryPreviewImage[] }).preview_gallery || []
</script>

<!-- 
  @component
  This component will show either
  - A media item (pictures, videos) (large form factor posts only)
  - Embed link/card.
-->
{#if gallery.length > 1 && (view == 'cozy' || view == 'card')}
  <PostGalleryPreview images={gallery} {blur} />
{:else if type == 'image' && (view == 'cozy' || view == 'card')}
  <PostImage {post} {blur} {linkOverride} />
{:else if (type == 'iframe' || type == 'video') && (view == 'cozy' || view == 'card') && post.url}
  <PostIframe
    thumbnail={post.thumbnail_url}
    type={iframeType(post.url)}
    url={post.url}
    {opened}
  />
{:else if type == 'embed' && post.url}
  <PostLink
    url={post.url}
    thumbnail_url={view != 'list' ? post.thumbnail_url : undefined}
    nsfw={post.nsfw}
    embed_description={post.embed_description}
    embed_title={post.embed_title}
    {view}
  />
{/if}
