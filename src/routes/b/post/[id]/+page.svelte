<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { backendPostToPostView, buildBackendPostPath } from '$lib/api/backend'

  export let data

  const postView = backendPostToPostView(data.post)
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Публикация</h1>
  </Header>

  <Post
    post={postView}
    view="cozy"
    actions={true}
    showReadMore={false}
    showFullBody={true}
    linkOverride={buildBackendPostPath(data.post)}
    userUrlOverride={data.post.author?.username ? `/${data.post.author.username}` : undefined}
    communityUrlOverride={data.post.rubric_slug ? `/rubrics/${data.post.rubric_slug}/posts` : undefined}
    subscribeUrl={data.post.channel_url ?? data.post.author?.channel_url}
    subscribeLabel="Подписаться"
  />
</div>
