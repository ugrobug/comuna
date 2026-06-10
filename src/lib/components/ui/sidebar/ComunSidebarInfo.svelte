<script lang="ts">
  import {
    buildComunGlossaryPath,
    buildComunKnowledgeBasePath,
    buildComunRoadmapPath,
    type BackendComun,
  } from '$lib/api/backend'

  export let comun: BackendComun | null = null

  type SidebarMember = {
    id?: number | null
    username?: string | null
    display_name?: string | null
    is_deleted?: boolean
    isCreator?: boolean
  }

  const displayName = (user?: SidebarMember | null) => {
    const name = (user?.display_name ?? '').trim()
    if (name) return name
    const username = (user?.username ?? '').trim()
    return username ? `@${username}` : 'Пользователь'
  }

  const userInitial = (user?: SidebarMember | null) =>
    ((user?.display_name ?? user?.username ?? '?').trim().slice(0, 1) || '?').toUpperCase()

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
</script>

<div class="flex flex-col gap-4">
  {#if websiteUrl}
    <a
      href={websiteUrl}
      target="_blank"
      rel="nofollow noopener noreferrer"
      class="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-100 dark:hover:bg-zinc-800"
    >
      Сайт сообщества
    </a>
  {/if}

  {#if comun?.rules_text}
    <section class="rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
      <details>
        <summary class="cursor-pointer list-none text-base font-semibold text-slate-900 dark:text-zinc-100">
          <span class="flex items-center justify-between gap-3">
            <span>Правила сообщества</span>
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
      Глоссарий
    </a>
  {/if}

  {#if comun?.roadmap_enabled}
    <a
      href={roadmapPath}
      class="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-100 dark:hover:bg-zinc-800"
    >
      Дорожная карта
    </a>
  {/if}

  {#if comun?.knowledge_base_enabled}
    <a
      href={knowledgeBasePath}
      class="inline-flex items-center justify-center rounded-2xl border border-slate-200 bg-white/95 px-4 py-3 text-sm font-semibold text-slate-900 shadow-sm transition hover:bg-slate-50 dark:border-zinc-800 dark:bg-zinc-900/85 dark:text-zinc-100 dark:hover:bg-zinc-800"
    >
      База знаний
    </a>
  {/if}

  {#if moderatorList.length}
    <section class="rounded-2xl border border-slate-200 bg-white/95 p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
      <div class="text-base font-semibold text-slate-900 dark:text-zinc-100">Модераторы</div>
      <div class="mt-4 flex flex-col gap-3">
        {#each moderatorList as moderator}
          <div class="flex items-center gap-3">
            <div class="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-slate-100 text-sm font-semibold text-slate-700 dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
              {userInitial(moderator)}
            </div>
            <div class="min-w-0 flex-1">
              {#if moderator.id && !moderator.is_deleted}
                <a
                  href={`/id${moderator.id}`}
                  class="block truncate text-sm font-medium text-slate-900 hover:underline dark:text-zinc-100"
                  title={moderator.username ? `Профиль @${moderator.username}` : 'Профиль пользователя'}
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
                    Создатель
                  </span>
                {/if}
              </div>
            </div>
          </div>
        {/each}
      </div>
    </section>
  {/if}
</div>
