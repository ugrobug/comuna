<script lang="ts">
  import { onMount } from 'svelte'
  import { Button } from 'mono-svelte'
  import { buildPostCommentsUrl } from '$lib/api/backend'
  import { siteToken, siteUser } from '$lib/siteAuth'

  export let postId: number

  let comments: Array<{ id: number; body: string; created_at: string; user: { username: string } }> = []
  let loading = false
  let submitting = false
  let error = ''
  let body = ''

  const loadComments = async () => {
    loading = true
    error = ''
    try {
      const response = await fetch(buildPostCommentsUrl(postId))
      if (!response.ok) {
        throw new Error('Не удалось загрузить комментарии')
      }
      const data = await response.json()
      comments = data.comments ?? []
    } catch (err) {
      error = (err as Error)?.message ?? 'Ошибка загрузки'
    }
    loading = false
  }

  const submitComment = async () => {
    if (!$siteToken) {
      error = 'Войдите, чтобы оставить комментарий'
      return
    }
    if (!body.trim()) {
      error = 'Введите текст комментария'
      return
    }
    submitting = true
    error = ''
    try {
      const response = await fetch(buildPostCommentsUrl(postId), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${$siteToken}`,
        },
        body: JSON.stringify({ body: body.trim() }),
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.error || 'Не удалось отправить комментарий')
      }
      if (data?.comment) {
        comments = [...comments, data.comment]
        body = ''
      }
    } catch (err) {
      error = (err as Error)?.message ?? 'Ошибка отправки'
    }
    submitting = false
  }

  onMount(() => {
    loadComments()
  })
</script>

<section id="comments" class="mt-8">
  <h2 class="text-xl font-semibold mb-4">Комментарии</h2>

  {#if $siteUser}
    <div class="mb-6">
      <textarea
        bind:value={body}
        rows="4"
        class="w-full rounded-lg border border-slate-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 p-3 text-sm"
        placeholder="Напишите комментарий..."
      ></textarea>
      <div class="flex justify-end mt-2">
        <Button
          size="sm"
          color="primary"
          on:click={submitComment}
          loading={submitting}
          disabled={submitting}
        >
          Отправить
        </Button>
      </div>
    </div>
  {:else}
    <p class="text-sm text-slate-500 dark:text-zinc-400 mb-6">
      Войдите, чтобы оставлять комментарии.
    </p>
  {/if}

  {#if error}
    <p class="text-sm text-red-600 mb-4">{error}</p>
  {/if}

  {#if loading}
    <p class="text-sm text-slate-500">Загрузка...</p>
  {:else if comments.length === 0}
    <p class="text-sm text-slate-500">Комментариев пока нет.</p>
  {:else}
    <div class="flex flex-col gap-4">
      {#each comments as comment}
        <div class="border border-slate-200 dark:border-zinc-800 rounded-lg p-4">
          <div class="text-sm text-slate-500 dark:text-zinc-400 mb-2">
            @{comment.user.username}
            <span class="ml-2">{new Date(comment.created_at).toLocaleString('ru-RU')}</span>
          </div>
          <div class="text-sm text-slate-800 dark:text-zinc-200 whitespace-pre-line">{comment.body}</div>
        </div>
      {/each}
    </div>
  {/if}
</section>
