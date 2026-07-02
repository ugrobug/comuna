<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import {
    backendPostCommunityPath,
    backendAuthorPath,
    backendPostToPostView,
    buildBackendPostPath,
    isSpecialProjectPost,
    type BackendComunCategory,
    type BackendPost,
  } from '$lib/api/backend'
  import { t } from '$lib/translations'

  export let posts: BackendPost[] = []
  export let loadingMore = false
  export let hideCommunity = false
  export let hideTitle = false
  export let comunCategories: BackendComunCategory[] = []
  export let currentWelcomePostId: number | null | undefined = undefined
  export let postClass =
    'feed-shortcut-post rounded-2xl border border-slate-200/80 bg-white/95 px-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85 sm:px-5'

  const dispatch = createEventDispatcher()

  const handleHide = (index: number, event: CustomEvent) => {
    posts = posts.toSpliced(index, 1)
    dispatch('hide', event.detail)
  }

  const forward = (event: CustomEvent) => {
    dispatch(event.type, event.detail)
  }
</script>

{#if posts.length}
  <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
    {#each posts as backendPost, index (backendPost.id)}
      {@const postView = backendPostToPostView(backendPost, backendPost.author)}
      <Post
        post={postView}
        class={postClass}
        view="cozy"
        actions={true}
        showReadMore={false}
        showFullBody={false}
        {hideCommunity}
        {hideTitle}
        linkOverride={buildBackendPostPath(backendPost)}
        userUrlOverride={backendAuthorPath(backendPost.author)}
        communityUrlOverride={backendPostCommunityPath(backendPost)}
        subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
        subscribeLabel={$t('site.sidebar.recommended.subscribe')}
        hideSubscribe={isSpecialProjectPost(backendPost)}
        {comunCategories}
        {currentWelcomePostId}
        on:hide={(event) => handleHide(index, event)}
        on:categorychange={forward}
        on:pinned={forward}
        on:unpinned={forward}
      />
    {/each}
  </div>
  {#if loadingMore}
    <div class="text-sm text-slate-500">{$t('site.sidebar.myFeedSection.loadingPosts')}</div>
  {/if}
{/if}
