<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import Post from '$lib/components/lemmy/post/Post.svelte'
  import { backendPostToPostView, buildBackendPostPath } from '$lib/api/backend'
  import { env } from '$env/dynamic/public'
  import { page } from '$app/stores'

  export let data

  $: siteTitle = env.PUBLIC_SITE_TITLE || 'Comuna'
  $: rubricName = data.rubric?.name ?? 'Рубрика'
  $: title = `${rubricName} — ${siteTitle}`
  $: description =
    data.rubric?.description ||
    `Посты и подборки по теме «${rubricName}» на ${siteTitle}.`
  $: canonicalUrl = new URL(
    $page.url.pathname,
    (env.PUBLIC_SITE_URL || $page.url.origin).replace(/\/+$/, '') + '/'
  ).toString()
</script>

<div class="flex flex-col gap-6 max-w-3xl">
  <section class="overflow-hidden rounded-2xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800">
    <div
      class="h-40 sm:h-52 w-full bg-slate-100 dark:bg-zinc-800"
      style={data.rubric?.cover_image_url ? `background-image: url('${data.rubric.cover_image_url}'); background-size: cover; background-position: center;` : ''}
    ></div>
    <div class="px-6 pb-6 pt-4 relative">
      <div class="-mt-10 mb-4 flex items-center justify-between">
        <div class="flex items-center gap-4">
          <div class="h-20 w-20 rounded-full border-4 border-white dark:border-zinc-900 overflow-hidden bg-slate-100 dark:bg-zinc-800">
            {#if data.rubric?.icon_url}
              <img src={data.rubric.icon_url} alt={data.rubric?.name} class="h-full w-full object-cover" />
            {:else}
              <div class="h-full w-full flex items-center justify-center text-xl font-bold text-slate-400 dark:text-zinc-500">
                {data.rubric?.name?.[0] ?? 'R'}
              </div>
            {/if}
          </div>
          <div class="flex flex-col gap-1">
            <h1 class="text-2xl font-bold">{data.rubric?.name ?? 'Рубрика'}</h1>
            {#if data.rubric?.slug}
              <div class="text-slate-500 dark:text-zinc-400">@{data.rubric.slug}</div>
            {/if}
          </div>
        </div>
        {#if data.rubric?.subscribe_url}
          <a
            class="hidden sm:inline-flex items-center justify-center rounded-full bg-blue-600 text-white px-6 py-2 text-sm font-semibold hover:bg-blue-700"
            href={data.rubric.subscribe_url}
            target="_blank"
            rel="noreferrer"
          >
            Подписаться
          </a>
        {/if}
      </div>

      {#if data.rubric?.description}
        <p class="text-base leading-relaxed text-slate-700 dark:text-zinc-300">
          {data.rubric.description}
        </p>
      {/if}

      <div class="mt-4 text-base font-semibold text-slate-900 dark:text-zinc-100">
        Посты
      </div>
    </div>
  </section>

  {#if data.posts?.length}
    <div class="flex flex-col gap-6">
      {#each data.posts as backendPost (backendPost.id)}
        {@const postView = backendPostToPostView(backendPost)}
        <Post
          post={postView}
          view="cozy"
          actions={true}
          showReadMore={false}
          showFullBody={false}
          linkOverride={buildBackendPostPath(backendPost)}
          userUrlOverride={backendPost.author?.username ? `/${backendPost.author.username}` : undefined}
          communityUrlOverride={`/rubrics/${data.rubric?.slug ?? backendPost.rubric_slug}/posts`}
          subscribeUrl={backendPost.channel_url ?? backendPost.author?.channel_url}
          subscribeLabel="Подписаться"
        />
      {/each}
    </div>
  {:else}
    <div class="text-base text-slate-500">В этой рубрике пока нет публикаций.</div>
  {/if}
</div>

<svelte:head>
  <title>{title}</title>
  <meta name="description" content={description} />
  <meta property="og:title" content={title} />
  <meta property="og:description" content={description} />
  <meta property="og:type" content="website" />
  <meta property="og:url" content={canonicalUrl} />
  {#if data.rubric?.cover_image_url}
    <meta property="og:image" content={data.rubric.cover_image_url} />
    <meta name="twitter:card" content="summary_large_image" />
    <meta name="twitter:image" content={data.rubric.cover_image_url} />
  {/if}
  <link rel="canonical" href={canonicalUrl} />
</svelte:head>
