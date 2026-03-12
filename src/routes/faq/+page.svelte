<script lang="ts">
  import { env } from '$env/dynamic/public'
  import PostBody from '$lib/components/lemmy/post/PostBody.svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import type { BackendPost } from '$lib/api/backend'
  import { page } from '$app/stores'
  import { ChevronDown, Icon, MagnifyingGlass } from 'svelte-hero-icons'

  type FaqRubric = {
    name?: string
    slug?: string
    description?: string | null
  }

  type SearchableFaqPost = BackendPost & {
    searchText: string
  }

  export let data: {
    rubric?: FaqRubric | null
    posts?: BackendPost[]
  }

  const normalizeSearch = (value: string) =>
    value
      .toLowerCase()
      .replace(/ё/g, 'е')
      .replace(/\s+/g, ' ')
      .trim()

  const stripHtml = (value: string) =>
    value
      .replace(/<[^>]+>/g, ' ')
      .replace(/&nbsp;/g, ' ')
      .replace(/&amp;/g, '&')
      .replace(/&quot;/g, '"')
      .replace(/&#39;/g, "'")
      .replace(/\s+/g, ' ')
      .trim()

  const decodeBase64Json = (value: string) => {
    const normalized = value.replace(/-/g, '+').replace(/_/g, '/')
    const padding = normalized.length % 4 === 0 ? '' : '='.repeat(4 - (normalized.length % 4))
    const padded = `${normalized}${padding}`

    if (typeof atob === 'function') {
      return decodeURIComponent(escape(atob(padded)))
    }

    const bufferCtor = (globalThis as { Buffer?: typeof Buffer }).Buffer
    if (bufferCtor) {
      return bufferCtor.from(padded, 'base64').toString('utf-8')
    }

    throw new Error('Base64 decoder is unavailable')
  }

  const parseEditorPayload = (value: string) => {
    const raw = String(value ?? '').trim()
    if (!raw) return null

    try {
      return JSON.parse(raw)
    } catch {
      try {
        return JSON.parse(decodeBase64Json(raw))
      } catch {
        return null
      }
    }
  }

  const collectText = (value: unknown): string => {
    if (typeof value === 'string') {
      return stripHtml(value)
    }
    if (Array.isArray(value)) {
      return value.map((item) => collectText(item)).filter(Boolean).join(' ')
    }
    if (value && typeof value === 'object') {
      return Object.values(value)
        .map((item) => collectText(item))
        .filter(Boolean)
        .join(' ')
    }
    return ''
  }

  const buildSearchText = (post: BackendPost) => {
    const parsedContent = parseEditorPayload(post.content)
    const contentText =
      parsedContent && typeof parsedContent === 'object' && Array.isArray((parsedContent as any).blocks)
        ? collectText((parsedContent as any).blocks)
        : stripHtml(post.content ?? '')

    return normalizeSearch(`${post.title ?? ''} ${contentText}`)
  }

  let searchQuery = ''
  let openPostId: number | null = null

  $: rubricName = data.rubric?.name ?? 'FAQ'
  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: title = `${rubricName} — ${siteTitle}`
  $: description =
    data.rubric?.description ||
    'Ответы на частые вопросы и инструкции по работе с сайтом.'
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()

  $: searchablePosts = (data.posts ?? []).map((post) => ({
    ...post,
    searchText: buildSearchText(post),
  })) as SearchableFaqPost[]
  $: normalizedQuery = normalizeSearch(searchQuery)
  $: filteredPosts = searchablePosts.filter(
    (post) => !normalizedQuery || post.searchText.includes(normalizedQuery)
  )
  $: if (openPostId && !filteredPosts.some((post) => post.id === openPostId)) {
    openPostId = null
  }

  const togglePost = (postId: number) => {
    openPostId = openPostId === postId ? null : postId
  }
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <Header pageHeader>
    <div class="flex w-full items-start justify-between gap-3">
      <div class="flex flex-col gap-2">
        <h1 class="text-2xl font-bold">{rubricName}</h1>
        <p class="text-sm leading-6 text-slate-600 dark:text-zinc-400">
          {description}
        </p>
      </div>
    </div>
  </Header>

  <section class="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
    <label class="mb-2 block text-sm font-medium text-slate-700 dark:text-zinc-200" for="faq-search">
      Поиск по FAQ
    </label>
    <div class="relative">
      <Icon
        src={MagnifyingGlass}
        size="18"
        class="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500"
      />
      <input
        id="faq-search"
        type="search"
        bind:value={searchQuery}
        placeholder="Начните вводить вопрос или ключевое слово"
        class="w-full rounded-xl border border-slate-200 bg-slate-50 py-3 pl-11 pr-4 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:bg-white dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:bg-zinc-900"
      />
    </div>
    <p class="mt-3 text-sm text-slate-500 dark:text-zinc-400">
      {#if normalizedQuery}
        Найдено: {filteredPosts.length}
      {:else}
        Всего вопросов: {searchablePosts.length}
      {/if}
    </p>
  </section>

  {#if filteredPosts.length}
    <section class="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
      {#each filteredPosts as post, index (post.id)}
        <article class:post-border={index > 0}>
          <button
            type="button"
            class="flex w-full items-center gap-3 px-5 py-4 text-left transition hover:bg-slate-50 dark:hover:bg-zinc-800/70"
            aria-expanded={openPostId === post.id}
            aria-controls={`faq-post-${post.id}`}
            on:click={() => togglePost(post.id)}
          >
            <span class="flex-1 text-base font-semibold text-slate-900 dark:text-zinc-100">
              {post.title}
            </span>
            <div
              class="shrink-0 text-slate-400 transition-transform dark:text-zinc-500"
              class:rotate-180={openPostId === post.id}
            >
              <Icon src={ChevronDown} size="18" />
            </div>
          </button>

          {#if openPostId === post.id}
            <div
              id={`faq-post-${post.id}`}
              class="border-t border-slate-100 px-5 pb-5 pt-4 dark:border-zinc-800"
            >
              <PostBody body={post.content} showFullBody={true} />
            </div>
          {/if}
        </article>
      {/each}
    </section>
  {:else}
    <section class="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-sm text-slate-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
      По вашему запросу ничего не найдено.
    </section>
  {/if}
</div>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>

<style>
  article.post-border {
    border-top: 1px solid rgb(226 232 240 / 1);
  }

  :global(.dark) article.post-border {
    border-top-color: rgb(39 39 42 / 1);
  }
</style>
