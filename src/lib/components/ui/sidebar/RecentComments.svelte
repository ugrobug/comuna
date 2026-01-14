<script lang="ts">
  import { onMount } from 'svelte'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import RelativeDate from '$lib/components/util/RelativeDate.svelte'
  import { ChatBubbleLeftEllipsis, Icon } from 'svelte-hero-icons'
  import { buildBackendPostPath, buildRecentCommentsUrl } from '$lib/api/backend'

  type RecentComment = {
    id: number
    body: string
    created_at: string
    user: {
      username: string
    }
    post: {
      id: number
      title: string
    }
  }

  let comments: RecentComment[] = []
  let loading = true
  let error: string | null = null

  const buildPostLink = (comment: RecentComment) =>
    `${buildBackendPostPath(comment.post)}#comments`

  const previewBody = (body: string) => {
    const normalized = body.replace(/\s+/g, ' ').trim()
    if (normalized.length <= 160) return normalized
    return `${normalized.slice(0, 160)}...`
  }

  async function fetchRecentComments() {
    try {
      const response = await fetch(buildRecentCommentsUrl(5))
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }
      const data = await response.json()
      comments = data.comments ?? []
    } catch (e: unknown) {
      error = e instanceof Error ? e.message : 'Неизвестная ошибка'
    } finally {
      loading = false
    }
  }

  onMount(fetchRecentComments)
</script>

<div class="flex flex-col gap-2 bg-white dark:bg-zinc-900 rounded-xl p-4">
  <span class="text-base font-normal text-slate-900 dark:text-zinc-200 mb-2">
    Свежие комментарии
  </span>

  {#if loading}
    <div class="animate-pulse space-y-3">
      {#each Array(4) as _}
        <div class="h-4 bg-slate-100 dark:bg-zinc-800 rounded"></div>
      {/each}
    </div>
  {:else if error}
    <div class="text-sm text-red-500">
      {error}
    </div>
  {:else if comments.length === 0}
    <div class="text-sm text-slate-500 dark:text-zinc-400">
      Комментариев пока нет
    </div>
  {:else}
    <div class="flex flex-col divide-y divide-slate-200 dark:divide-zinc-800">
      {#each comments as comment}
        <a
          href={buildPostLink(comment)}
          class="block group py-3 first:pt-1 last:pb-1"
        >
          <div class="flex items-start gap-2">
            <Avatar
              url={undefined}
              alt={comment.user.username}
              width={28}
              class_="w-7 h-7 rounded-full"
            />
            <div class="flex flex-col gap-1 min-w-0">
              <div class="flex items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                <span class="font-medium text-slate-900 dark:text-zinc-200">
                  {comment.user.username}
                </span>
                <span>•</span>
                <RelativeDate date={new Date(comment.created_at)} />
              </div>
              <div class="text-sm text-slate-700 dark:text-zinc-300">
                {previewBody(comment.body)}
              </div>
              <div class="text-xs text-slate-500 dark:text-zinc-400 truncate">
                <Icon src={ChatBubbleLeftEllipsis} size="12" class="inline-block mr-1" />
                {comment.post.title}
              </div>
            </div>
          </div>
        </a>
      {/each}
    </div>
  {/if}
</div>
