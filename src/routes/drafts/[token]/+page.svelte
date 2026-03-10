<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import PostBody from '$lib/components/lemmy/post/PostBody.svelte'
  import { Button, Spinner } from 'mono-svelte'
  import { fetchSharedDraft, refreshSiteUser, type SiteUserPost } from '$lib/siteAuth'
  import { onMount } from 'svelte'

  export let data: { shareToken: string }

  let loading = true
  let draft: SiteUserPost | null = null
  let loadError = ''
  let loggedIn = false

  const formatDate = (value?: string | null) => {
    if (!value) return ''
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return ''
    return new Intl.DateTimeFormat('ru-RU', {
      day: '2-digit',
      month: 'long',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(date)
  }

  onMount(() => {
    const loadDraft = async () => {
      loading = true
      loadError = ''
      try {
        const user = await refreshSiteUser()
        loggedIn = Boolean(user)
        if (!user) {
          loadError = 'Чтобы открыть черновик по ссылке, нужно войти на сайт.'
          return
        }
        draft = await fetchSharedDraft(data.shareToken)
      } catch (error) {
        loadError = (error as Error)?.message ?? 'Не удалось загрузить черновик'
      } finally {
        loading = false
      }
    }

    void loadDraft()
  })
</script>

<div class="mx-auto flex max-w-4xl flex-col gap-6">
  <Header pageHeader>
    <h1 class="text-2xl font-bold">Черновик по ссылке</h1>
  </Header>

  {#if loading}
    <div class="flex items-center gap-2 text-sm text-slate-500 dark:text-zinc-400">
      <Spinner size="sm" />
      Загрузка...
    </div>
  {:else if loadError}
    <div class="rounded-xl border border-slate-200 bg-white p-6 text-sm text-slate-700 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-200">
      <p>{loadError}</p>
      {#if !loggedIn}
        <div class="mt-4">
          <Button href="/settings">Войти</Button>
        </div>
      {/if}
    </div>
  {:else if draft}
    <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950 sm:p-7">
      <div class="flex flex-col gap-3 border-b border-slate-200 pb-5 dark:border-zinc-800">
        <div class="text-xs uppercase tracking-[0.24em] text-slate-500 dark:text-zinc-400">
          Приватный предпросмотр черновика
        </div>
        <h2 class="text-3xl font-semibold text-slate-950 dark:text-zinc-50">
          {draft.title || 'Без заголовка'}
        </h2>
        <div class="flex flex-wrap gap-x-4 gap-y-2 text-sm text-slate-500 dark:text-zinc-400">
          <span>@{draft.author?.username || 'author'}</span>
          {#if draft.rubric}
            <span>{draft.rubric}</span>
          {/if}
          <span>Обновлён {formatDate(draft.updated_at || draft.created_at)}</span>
        </div>
        {#if draft.tags?.length}
          <div class="flex flex-wrap gap-2 pt-1">
            {#each draft.tags as tag}
              <span class="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600 dark:border-zinc-700 dark:text-zinc-300">
                #{typeof tag === 'string' ? tag : tag.name}
              </span>
            {/each}
          </div>
        {/if}
      </div>

      <div class="pt-6">
        <PostBody
          body={draft.content || ''}
          title={draft.title || ''}
          template={draft.template}
          showFullBody={true}
          collapsible={false}
          allowPollVoting={false}
          postId={null}
        />
      </div>
    </article>
  {/if}
</div>
