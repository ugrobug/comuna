<script lang="ts">
  import { ChatBubbleLeftRight, Icon, Trophy } from 'svelte-hero-icons'
  import {
    buildBackendPostPath,
    buildComunGlossaryPath,
    buildComunKnowledgeBasePath,
    buildComunRoadmapPath,
    type BackendComun,
    type BackendComunTopPost,
  } from '$lib/api/backend'
  import { formatTopAuthorNumber } from '$lib/ratings/topAuthors'
  import { locale, t } from '$lib/translations'

  export let comun: BackendComun | null = null

  type SidebarMember = {
    id?: number | null
    username?: string | null
    display_name?: string | null
    is_deleted?: boolean
    isCreator?: boolean
  }

  let moderatorsExpanded = false
  let lastComunSlug = ''

  const displayName = (user?: SidebarMember | null) => {
    const name = (user?.display_name ?? '').trim()
    if (name) return name
    const username = (user?.username ?? '').trim()
    return username ? `@${username}` : $t('site.sidebar.comunInfo.user')
  }

  const userInitial = (user?: SidebarMember | null) =>
    ((user?.display_name ?? user?.username ?? '?').trim().slice(0, 1) || '?').toUpperCase()

  const authorTitle = (post?: BackendComunTopPost | null) =>
    (post?.author?.title ?? post?.author?.username ?? '').trim() || $t('site.sidebar.comunInfo.author')

  const formatPostDate = (value?: string | null) => {
    const raw = (value ?? '').trim()
    if (!raw) return ''
    const date = new Date(raw)
    if (Number.isNaN(date.getTime())) return ''
    return new Intl.DateTimeFormat($locale || 'ru', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
    }).format(date).replace('.', '')
  }

  const topPostPath = (post: BackendComunTopPost) =>
    post.path || buildBackendPostPath({ id: post.id, title: post.title })

  const externalUrl = (value?: string | null) => {
    const raw = (value ?? '').trim()
    if (!raw) return ''
    if (/^[a-z][a-z0-9+.-]*:\/\//i.test(raw)) return raw
    if (raw.startsWith('//')) return `https:${raw}`
    return `https://${raw.replace(/^\/+/, '')}`
  }

  $: creator = comun?.creator
  $: moderators = comun?.moderators ?? []
  $: websiteUrl = externalUrl(comun?.website_url)
  $: glossaryPath = comun?.slug ? buildComunGlossaryPath(comun.slug) : '/comuns'
  $: knowledgeBasePath = comun?.slug ? buildComunKnowledgeBasePath(comun.slug) : '/comuns'
  $: roadmapPath = comun?.slug ? buildComunRoadmapPath(comun.slug) : '/comuns'
  $: if ((comun?.slug ?? '') !== lastComunSlug) {
    lastComunSlug = comun?.slug ?? ''
    moderatorsExpanded = false
  }
  $: moderatorList = (() => {
    const seen = new Set<number>()
    const result: SidebarMember[] = []

    if (creator?.id) {
      seen.add(creator.id)
      result.push({ ...creator, isCreator: true })
    } else if (creator?.username || creator?.display_name) {
      result.push({ ...creator, isCreator: true })
    }

    for (const moderator of moderators) {
      if (moderator?.id && seen.has(moderator.id)) continue
      if (moderator?.id) {
        seen.add(moderator.id)
      }
      result.push({
        id: moderator.id,
        username: moderator.username,
        display_name: moderator.display_name,
        isCreator: creator?.id === moderator.id,
      })
    }

    return result
  })()
  $: visibleModerators = moderatorsExpanded ? moderatorList : moderatorList.slice(0, 2)
  $: hiddenModeratorsCount = Math.max(moderatorList.length - visibleModerators.length, 0)
  $: topPosts = comun?.top_posts ?? []
</script>

<div class="flex flex-col gap-4">
  {#if websiteUrl}
    <a
      href={websiteUrl}
      target="_blank"
      rel="nofollow noopener noreferrer"
      class="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-100 dark:hover:bg-zinc-800"
    >
      {$t('site.sidebar.comunInfo.website')}
    </a>
  {/if}

  {#if comun?.rules_text}
    <section class="rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
      <details>
        <summary class="cursor-pointer list-none text-base font-semibold text-slate-900 dark:text-zinc-100">
          <span class="flex items-center justify-between gap-3">
            <span>{$t('site.sidebar.comunInfo.rules')}</span>
            <svg
              viewBox="0 0 20 20"
              class="h-4 w-4 shrink-0 text-slate-500 dark:text-zinc-400"
              fill="none"
              stroke="currentColor"
              stroke-width="1.8"
              stroke-linecap="round"
              stroke-linejoin="round"
              aria-hidden="true"
            >
              <path d="M5 7.5 10 12.5 15 7.5"></path>
            </svg>
          </span>
        </summary>
        <div class="mt-3 whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
          {comun.rules_text}
        </div>
      </details>
    </section>
  {/if}

  {#if comun?.glossary_enabled}
    <a
      href={glossaryPath}
      class="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-100 dark:hover:bg-zinc-800"
    >
      {$t('site.sidebar.comunInfo.glossary')}
    </a>
  {/if}

  {#if comun?.roadmap_enabled}
    <a
      href={roadmapPath}
      class="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-100 dark:hover:bg-zinc-800"
    >
      {$t('site.sidebar.comunInfo.roadmap')}
    </a>
  {/if}

  {#if comun?.knowledge_base_enabled}
    <a
      href={knowledgeBasePath}
      class="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-100 dark:hover:bg-zinc-800"
    >
      {$t('site.sidebar.comunInfo.knowledgeBase')}
    </a>
  {/if}

  {#if moderatorList.length}
    <section class="rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
      <div class="text-base font-semibold text-slate-900 dark:text-zinc-100">{$t('site.sidebar.comunInfo.moderators')}</div>
      <div class="mt-4 flex flex-col gap-3">
        {#each visibleModerators as moderator}
          <div class="flex items-center gap-3">
            <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-slate-100 text-sm font-semibold text-slate-700 dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
              {userInitial(moderator)}
            </div>
            <div class="min-w-0 flex-1">
              {#if moderator.id && !moderator.is_deleted}
                <a
                  href={`/id${moderator.id}`}
                  class="block truncate text-sm font-medium text-slate-900 hover:underline dark:text-zinc-100"
                  title={moderator.username ? $t('site.sidebar.comunInfo.profileUsername', { username: moderator.username }) : $t('site.sidebar.comunInfo.profileUser')}
                >
                  {displayName(moderator)}
                </a>
              {:else}
                <div class="truncate text-sm font-medium text-slate-900 dark:text-zinc-100">
                  {displayName(moderator)}
                </div>
              {/if}
              <div class="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500 dark:text-zinc-400">
                {#if moderator.username && !moderator.is_deleted}
                  <span>@{moderator.username}</span>
                {/if}
                {#if moderator.isCreator}
                  <span class="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-medium text-slate-700 dark:bg-zinc-800 dark:text-zinc-300">
                    {$t('site.sidebar.comunInfo.creator')}
                  </span>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
      {#if moderatorList.length > 2}
        <button
          type="button"
          class="mt-4 inline-flex w-full items-center justify-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-800"
          on:click={() => {
            moderatorsExpanded = !moderatorsExpanded
          }}
        >
          {#if moderatorsExpanded}
            {$t('site.sidebar.comunInfo.collapse')}
          {:else}
            {$t('site.sidebar.comunInfo.expandMore', { count: hiddenModeratorsCount })}
          {/if}
        </button>
      {/if}
    </section>
  {/if}

  {#if topPosts.length}
    <section class="rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
      <div class="text-base font-semibold text-slate-900 dark:text-zinc-100">{$t('site.sidebar.comunInfo.topPosts')}</div>
      <div class="mt-4 flex flex-col divide-y divide-slate-200 dark:divide-zinc-800">
        {#each topPosts as post}
          <a
            href={topPostPath(post)}
            class="group block py-3 first:pt-0 last:pb-0"
          >
            <div class="min-w-0">
              <div class="line-clamp-2 text-sm font-semibold leading-snug text-slate-900 transition group-hover:text-blue-600 dark:text-zinc-100 dark:group-hover:text-blue-400">
                {post.title}
              </div>
              <div class="mt-1 truncate text-xs text-slate-500 dark:text-zinc-400">
                {authorTitle(post)}
                {#if formatPostDate(post.created_at)}
                  · {formatPostDate(post.created_at)}
                {/if}
              </div>
              <div class="mt-2 flex items-center gap-3 text-xs font-medium text-slate-600 dark:text-zinc-400">
                <span class="inline-flex items-center gap-1">
                  <Icon src={ChatBubbleLeftRight} size="14" class="text-sky-500" />
                  {formatTopAuthorNumber(post.comments_count ?? 0)}
                </span>
                <span class="inline-flex items-center gap-1">
                  <Icon src={Trophy} size="14" class="text-amber-500" />
                  {formatTopAuthorNumber(post.rating ?? 0)}
                </span>
              </div>
            </div>
          </a>
        {/each}
      </div>
    </section>
  {/if}
</div>
