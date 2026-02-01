<script lang="ts">
  import type { PostView } from 'lemmy-js-client'
  import { isImage, isVideo } from '$lib/ui/image.js'
  import { getInstance } from '$lib/lemmy.js'
  import PostActions from '$lib/components/lemmy/post/PostActions.svelte'
  import { userSettings } from '$lib/settings.js'
  import PostLink from '$lib/components/lemmy/post/link/PostLink.svelte'
  import PostMeta from '$lib/components/lemmy/post/PostMeta.svelte'
  import { Badge, Button, Material, toast } from 'mono-svelte'
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import ExpandableImage from '$lib/components/ui/ExpandableImage.svelte'
  import {
    bestImageURL,
    mediaType,
    postLink,
  } from '$lib/components/lemmy/post/helpers.js'
  import Empty from '$lib/components/helper/Empty.svelte'
  import { publishedToDate } from '$lib/components/util/date.js'
  import {
    ArrowUp,
    ChatBubbleOvalLeft,
    Icon,
    VideoCamera,
  } from 'svelte-hero-icons'
  import PostMedia from '$lib/components/lemmy/post/media/PostMedia.svelte'
  import PostMediaCompact from '$lib/components/lemmy/post/media/PostMediaCompact.svelte'
  import PostBody from './PostBody.svelte'
  import { profile } from '$lib/auth'

  export let post: PostView
  export let actions: boolean = true
  export let hideCommunity = false
  export let view = $userSettings.view
  export let hideTitle: boolean = false
  export let linkOverride: string | undefined = undefined
  export let showReadMore: boolean = true
  export let showFullBody: boolean = false
  export let communityUrlOverride: string | undefined = undefined
  export let userUrlOverride: string | undefined = undefined
  export let subscribeUrl: string | undefined = undefined
  export let subscribeLabel: string = 'Подписаться'
  export let disableUserLink: boolean | undefined = undefined

  $: postUrl = linkOverride ?? postLink(post.post)
  $: isBackendPost = Boolean(linkOverride)
  $: type = mediaType(post.post.url, view)
  $: rule = getTagRule(backendTags.map((tag) => ({ content: tag })))
  $: communityName = post.community?.name || ''
  $: communityTitle = post.community?.title || ''
  $: backendTags = (post.post as { tags?: string[] }).tags ?? []
  $: autoDisableUserLink =
    disableUserLink ??
    (communityName.toLowerCase() === 'comuna' ||
      communityTitle.toLowerCase() === 'comuna')

  $: hideBody =
    $userSettings.posts.deduplicateEmbed &&
    post.post.embed_description == post.post.body &&
    view != 'compact'

  function getTagRule(tags: { content: string }[]): 'blur' | 'hide' | undefined {
    const tagContent = tags.map((t) => t.content.toLowerCase())

    let rule: 'blur' | 'hide' | undefined
    if ($userSettings.nsfwBlur && (post.post.nsfw || post.community.nsfw))
      rule = 'blur'
    tagContent.forEach((tag) => {
      if ($userSettings.tagRules?.[tag])
        rule = $userSettings.tagRules?.[tag] ?? rule
      if (rule == 'hide') return rule
    })

    return rule
  }
</script>

<!-- 
  @component
  This is the sole component for displaying posts.
  It adapts to all kinds of form factors for different contexts, such as feeds, full post view, and crosspost list.
-->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-noninteractive-tabindex -->
<div
  class="post post-preview relative max-w-full min-w-0 w-full
  group
  {$userSettings.leftAlign ? 'left-align' : ''}
  {view == 'compact' ? 'py-3 list-type compact' : ''}
  {view == 'list' ? 'py-5 list-type' : ''}
  {view == 'cozy' ? 'pt-4 pb-4 list-type flex flex-col gap-2' : ''}
  {$$props.class ?? ''}"
  id={post.post.id.toString()}
  style={$$props.style ?? ''}
>
  <PostMeta
    community={post.community}
    showCommunity={!hideCommunity}
    user={post.creator}
    published={publishedToDate(post.post.published)}
    badges={{
      deleted: post.post.deleted,
      removed: post.post.removed,
      locked: post.post.locked,
      featured: post.post.featured_local || post.post.featured_community,
      nsfw: post.post.nsfw || post.community.nsfw,
      saved: post.saved,
      admin: post.creator_is_admin,
      moderator: post.creator_is_moderator,
    }}
    subscribed={$profile?.user?.follows
      .map((c) => c.community.id)
      .includes(post.community.id)
      ? 'Subscribed'
      : 'NotSubscribed'}
    id={post.post.id}
    read={post.read}
    style="grid-area: meta;"
    edited={post.post.updated}
    {view}
    {communityUrlOverride}
    {userUrlOverride}
    disableUserLink={autoDisableUserLink}
    {subscribeUrl}
    {subscribeLabel}
  >
    <slot name="badges" slot="badges" />
  </PostMeta>

  <!-- Оборачиваем заголовок в ссылку -->
  {#if post.post.name}
    <a 
      href={postUrl}
      class="block no-underline hover:underline"
      style="grid-area: title;"
      data-sveltekit-preload-data="off"
    >
      <div class="text-2xl font-medium text-black dark:text-white" style="margin-bottom: 0;">
        {post.post.name}
      </div>
    </a>
  {/if}

  {#key post.post.url}
    <div
      style="grid-area:embed;"
      class={view == 'list' || view == 'compact' ? '' : 'contents'}
    >
      {#if rule != 'hide'}
        <PostMedia
          post={post.post}
          blur={rule == 'blur' ? true : undefined}
          {view}
          {type}
          linkOverride={postUrl}
        />
      {/if}
    </div>
    {#if view == 'list' || view == 'compact'}
      <PostMediaCompact
        post={post.post}
        {type}
        class="{$userSettings.leftAlign
          ? 'mr-3'
          : 'ml-3'} flex-shrink no-list-margin"
        style="grid-area: media;"
        blur={rule == 'blur' ? true : undefined}
        {view}
        linkOverride={postUrl}
      />
    {/if}
  {/key}

  <!-- Оборачиваем тело поста в ссылку -->
  {#if post.post.body && !post.post.nsfw && view != 'compact' && !hideBody && rule != 'hide'}
    {#if showFullBody}
      <div style="grid-area: body;">
        <PostBody
          element="section"
          body={post.post.body}
          title={post.post.name}
          {view}
          clickThrough={true}
          {showFullBody}
          class="relative text-slate-600 dark:text-zinc-400"
        />
        {#if backendTags.length}
          <div class="mt-4 flex flex-wrap gap-2">
            {#each backendTags as tag}
              <a
                href={`/tags/${encodeURIComponent(tag)}`}
                class="rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1 text-xs font-medium text-slate-600 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700"
                rel="nofollow"
              >
                #{tag}
              </a>
            {/each}
          </div>
        {/if}
        {#if subscribeUrl}
          <div class="mt-4">
            <Button
              size="sm"
              color="primary"
              href={subscribeUrl}
              target="_blank"
              rel="nofollow noopener"
              class="h-10 !min-h-[2.5rem] max-w-max !px-4 inline-flex items-center gap-2 whitespace-nowrap dark:!bg-primary-900 dark:!text-white dark:!border-transparent dark:hover:!brightness-110"
            >
              <img src="/img/logos/telegram_logo.svg" alt="Telegram" class="w-4 h-4" />
              <span class="text-white whitespace-nowrap">Подписаться на телеграм автора</span>
            </Button>
          </div>
        {/if}
      </div>
    {:else}
      <a
        href={postUrl}
        class="block no-underline hover:no-underline"
        style="grid-area: body;"
        data-sveltekit-preload-data="off"
      >
        <PostBody
          element="section"
          body={post.post.body}
          title={post.post.name}
          {view}
          clickThrough={false}
          {showFullBody}
          class="relative text-slate-600 dark:text-zinc-400"
        />
      </a>
    {/if}
  {/if}

  <!-- Возвращаем отдельную ссылку "читать далее" -->
  {#if showReadMore}
    <a
      href={postUrl}
      class="post-read-more text-sm text-accent-500 hover:underline mt-2 block"
      style="grid-area: read-more;"
      data-sveltekit-preload-data="off"
    >
      Читать далее
    </a>
  {/if}

  {#if actions}
    <PostActions
      on:hide
      {post}
      style="grid-area: actions;"
      {view}
      backendPostId={isBackendPost ? post.post.id : null}
      backendPostUrl={isBackendPost ? postUrl : null}
      backendComments={isBackendPost ? post.counts.comments : null}
      backendLikes={isBackendPost ? post.counts.score : null}
    />
  {:else if view == 'compact'}
    <div class="flex flex-row items-center gap-2 text-sm">
      <Badge>
        <Icon src={ArrowUp} slot="icon" size="14" micro />
        {post.counts.score}
      </Badge>
      <Badge>
        <Icon src={ChatBubbleOvalLeft} slot="icon" size="14" micro />
        {post.counts.comments}
      </Badge>
    </div>
  {/if}

  <div class="absolute overflow-hidden inset-0 sm:rounded-xl opacity-0 -z-50 no-list-margin" />
</div>

<style lang="postcss">
  .post {
    text-decoration: none;
    color: inherit; /* Сохраняем цвет текста */
  }

  .post:hover {
    text-decoration: none;
  }

  .list-type {
    grid-template-areas: 
      'meta media' 
      'title media' 
      'body media' 
      'embed embed' 
      'actions actions'
      'read-more read-more';
    grid-template-columns: minmax(0, 1fr) auto;
    width: 100%;
    height: 100%;
  }

  .list-type.left-align {
    grid-template-areas: 
      'media meta' 
      'media title' 
      'media body' 
      'embed embed' 
      'actions actions'
      'read-more read-more';
    grid-template-columns: auto minmax(0, 1fr);
  }

  /* Обновляем media queries тоже */
  @media (min-width: 480px) {
    .list-type.compact {
      grid-template-areas: 
        'meta media' 
        'title media' 
        'body media' 
        'embed media' 
        'actions media'
        'read-more media';
    }
  }

  @media (min-width: 480px) {
    .list-type.compact.left-align {
      grid-template-areas: 
        'media meta' 
        'media title' 
        'media body' 
        'media embed' 
        'media actions'
        'media read-more';
    }
  }

  :global(.compact > *:not(.no-list-margin):not(:first-child)) {
    margin-top: 0.3rem;
  }

  :global(.list-type:not(.compact) > *:not(.no-list-margin):not(:first-child)) {
    margin-top: 0.5rem;
  }

  .post-preview a:hover {
    text-decoration: none;
  }

  a.post-read-more:hover {
    text-decoration: underline;
  }

  /* Стили для кнопки Primary в постах */
  :global(.post .btn-primary) {
    background-color: var(--btn-primary-background);
    color: var(--btn-primary-color);
    border: 1px solid var(--btn-primary-border);
    border-radius: var(--btn-primary-border-radius);
    padding: var(--btn-primary-padding-y) var(--btn-primary-padding-x);
    font-size: var(--btn-primary-font-size);
    font-weight: var(--btn-primary-font-weight);
    line-height: var(--btn-primary-line-height);
    transition: var(--btn-primary-transition);
    box-shadow: var(--btn-primary-shadow);
    width: var(--btn-primary-width);
    display: var(--btn-primary-display);
    align-items: var(--btn-primary-align-items);
    justify-content: var(--btn-primary-justify-content);
  }

  :global(.post .btn-primary:hover) {
    background-color: var(--btn-primary-background-hover);
    color: var(--btn-primary-color);
    text-decoration: none;
    box-shadow: var(--btn-primary-shadow-hover);
  }
</style>
