<script lang="ts">
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { feedKeyboardShortcuts } from '$lib/actions/feedKeyboardShortcuts'
  import {
    backendPostCommunityPath,
    backendPostToPostView,
    buildBackendPostPath,
    isSpecialProjectPost,
    type BackendPost,
  } from '$lib/api/backend'

  export let posts: BackendPost[] = []
  export let loadingMore = false
</script>

{#if posts.length}
  <div class="flex flex-col gap-6" use:feedKeyboardShortcuts>
    {#each posts as backendPost (backendPost.id)}
      {@const postView = backendPostToPostView(backendPost, backendPost.author)}
      <Post
        post={postView}
        class="feed-shortcut-post rounded-2xl border border-slate-200/80 bg-white/95 px-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85 sm:px-5"
        view="cozy"
        actions={true}
        showReadMore={false}
        showFullBody={false}
        linkOverride={buildBackendPostPath(backendPost)}
        userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
        communityUrlOverride={backendPostCommunityPath(backendPost)}
        subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
        subscribeLabel="Подписаться"
        hideSubscribe={isSpecialProjectPost(backendPost)}
      />
    {/each}
  </div>
  {#if loadingMore}
    <div class="text-sm text-slate-500">Загрузка...</div>
  {/if}
{/if}
