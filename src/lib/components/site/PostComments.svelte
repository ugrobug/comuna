<script lang="ts">
  import { onMount } from 'svelte'
  import { browser } from '$app/environment'
  import { buildPostCommentsUrl } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'
  import SiteCommentForm from '$lib/components/site/comments/SiteCommentForm.svelte'
  import SiteCommentItem from '$lib/components/site/comments/SiteCommentItem.svelte'
  import type { SiteComment, SiteCommentNode } from '$lib/components/site/comments/types'

  export let postId: number
  export let postAuthor: string | null = null

  let comments: SiteComment[] = []
  let commentTree: SiteCommentNode[] = []
  let loading = false
  let error = ''
  let lastToken: string | null = null
  let lastPostId = postId

  const buildTree = (items: SiteComment[]): SiteCommentNode[] => {
    const nodes = new Map<number, SiteCommentNode>()
    const roots: SiteCommentNode[] = []

    items.forEach((comment) => {
      nodes.set(comment.id, { comment, children: [] })
    })

    items.forEach((comment) => {
      const node = nodes.get(comment.id)
      if (!node) return
      if (comment.parent_id && nodes.has(comment.parent_id)) {
        nodes.get(comment.parent_id)!.children.push(node)
      } else {
        roots.push(node)
      }
    })

    return roots
  }

  const rebuildTree = () => {
    commentTree = buildTree(comments)
  }

  const normalizeList = (items: SiteComment[]) =>
    items.slice().sort((a, b) => a.created_at.localeCompare(b.created_at))

  const loadComments = async () => {
    if (!browser) return
    loading = true
    error = ''
    try {
      const response = await fetch(buildPostCommentsUrl(postId), {
        headers: $siteToken
          ? {
              Authorization: `Bearer ${$siteToken}`,
            }
          : undefined,
      })
      if (!response.ok) {
        throw new Error('Не удалось загрузить комментарии')
      }
      const data = await response.json()
      comments = normalizeList((data.comments ?? []) as SiteComment[])
      rebuildTree()
    } catch (err) {
      error = (err as Error)?.message ?? 'Ошибка загрузки'
    }
    loading = false
  }

  const upsertComment = (comment: SiteComment) => {
    const index = comments.findIndex((item) => item.id === comment.id)
    if (index >= 0) {
      comments = comments.map((item) => (item.id === comment.id ? comment : item))
    } else {
      comments = normalizeList([...comments, comment])
    }
    rebuildTree()
  }

  const markDeleted = (commentId: number) => {
    comments = comments.map((item) =>
      item.id === commentId ? { ...item, is_deleted: true, body: '' } : item
    )
    rebuildTree()
  }

  onMount(() => {
    loadComments()
  })

  $: if ($siteToken !== lastToken) {
    lastToken = $siteToken
    loadComments()
  }

  $: if (postId !== lastPostId) {
    lastPostId = postId
    loadComments()
  }
</script>

<section id="comments" class="mt-10">
  <div class="flex items-center justify-between mb-5">
    <h2 class="text-xl font-semibold">Комментарии</h2>
    <span class="text-sm text-slate-500">{comments.filter((c) => !c.is_deleted).length}</span>
  </div>

  {#if !$siteUser}
    <p class="text-sm text-slate-500 dark:text-zinc-400 mb-4">
      Войдите, чтобы участвовать в обсуждении.
    </p>
  {/if}

  <div class="mb-8">
    <SiteCommentForm
      {postId}
      placeholder="Поделитесь мнением..."
      on:comment={(event) => upsertComment(event.detail)}
    />
  </div>

  {#if error}
    <p class="text-sm text-red-600 mb-4">{error}</p>
  {/if}

  {#if loading}
    <p class="text-sm text-slate-500">Загрузка...</p>
  {:else if comments.length === 0}
    <p class="text-sm text-slate-500">Комментариев пока нет.</p>
  {:else}
    <ul class="flex flex-col gap-6">
      {#each commentTree as node (node.comment.id)}
        <SiteCommentItem
          {node}
          {postId}
          {postAuthor}
          on:reply={(event) => upsertComment(event.detail)}
          on:update={(event) => upsertComment(event.detail)}
          on:remove={(event) => markDeleted(event.detail)}
        />
      {/each}
    </ul>
  {/if}
</section>
