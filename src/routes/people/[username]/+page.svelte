<script lang="ts">
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'
  import Avatar from '$lib/components/ui/Avatar.svelte'
  import RelativeDate from '$lib/components/util/RelativeDate.svelte'
  import Markdown from '$lib/components/markdown/Markdown.svelte'
  import type {
    BackendCommentPersonaComment,
    BackendCommentPersonaProfile,
  } from '$lib/api/backend'

  export let data

  let persona: BackendCommentPersonaProfile | null = data.persona ?? null
  let comments: BackendCommentPersonaComment[] = data.comments ?? []

  const formatNumber = (value?: number) => (value || value === 0 ? value.toLocaleString('ru-RU') : '0')

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: displayName = persona?.display_name || (persona?.username ? `@${persona.username}` : 'Участник')
  $: handle = persona?.username ? `@${persona.username}` : '@user'
  $: title = `${displayName} — ${siteTitle}`
  $: description = persona?.bio || `${displayName} — профиль участника сообщества на ${siteTitle}.`
  $: canonicalUrl = new URL(
    persona?.profile_url || $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
</script>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>

<div class="mx-auto flex max-w-4xl flex-col gap-6">
  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-5 sm:p-6">
    <div class="flex flex-col sm:flex-row gap-5 items-start">
      <Avatar width={80} alt={displayName} />
      <div class="min-w-0 flex-1 flex flex-col gap-3">
        <div>
          <h1 class="text-2xl font-semibold text-slate-900 dark:text-zinc-100 break-words">
            {displayName}
          </h1>
          <div class="text-sm text-slate-500 dark:text-zinc-400">{handle}</div>
        </div>
        {#if persona?.bio}
          <p class="text-sm text-slate-700 dark:text-zinc-300 leading-6">
            {persona.bio}
          </p>
        {/if}
        <div class="flex flex-wrap gap-3 text-sm text-slate-600 dark:text-zinc-300">
          <span class="rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1">
            Комментариев: {formatNumber(persona?.comments_count)}
          </span>
          <span class="rounded-full bg-slate-100 dark:bg-zinc-800 px-3 py-1">
            Постов в обсуждении: {formatNumber(persona?.posts_count)}
          </span>
        </div>
      </div>
    </div>
  </section>

  <section class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-5 sm:p-6">
    <div class="mb-4 flex items-center justify-between gap-3">
      <h2 class="text-lg font-semibold text-slate-900 dark:text-zinc-100">Комментарии</h2>
      <span class="text-sm text-slate-500 dark:text-zinc-400">{comments.length}</span>
    </div>

    {#if comments.length}
      <div class="flex flex-col gap-4">
        {#each comments as comment (comment.id)}
          <article class="rounded-2xl border border-slate-200 dark:border-zinc-800 bg-slate-50/70 dark:bg-zinc-950/40 p-4">
            <div class="flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
              {#if comment.post?.path}
                <a
                  href={comment.post.path}
                  class="text-sm font-medium text-slate-900 dark:text-zinc-100 hover:text-sky-600 dark:hover:text-sky-400 transition"
                >
                  {comment.post.title}
                </a>
              {/if}
              <RelativeDate date={new Date(comment.created_at)} />
              <span>Лайки: {formatNumber(comment.likes_count)}</span>
            </div>
            <div class="mt-3 text-sm text-slate-800 dark:text-zinc-100">
              <Markdown source={comment.body} />
            </div>
          </article>
        {/each}
      </div>
    {:else}
      <p class="text-sm text-slate-500 dark:text-zinc-400">Комментариев пока нет.</p>
    {/if}
  </section>
</div>
