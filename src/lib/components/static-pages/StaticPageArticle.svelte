<script>
  import PostBody from '$lib/components/lemmy/post/PostBody.svelte'

  export let heading
  export let pageContent
</script>

<article class="rounded-xl border border-slate-200 border-b-slate-300 bg-white p-4 dark:border-zinc-800 dark:border-t-zinc-700 dark:bg-zinc-900 sm:p-6">
  <div class="post static-page-post relative max-w-full min-w-0 w-full">
    <h2 class="mb-5 border-b border-slate-100 pb-4 text-2xl font-medium text-black dark:border-zinc-800 dark:text-white">
      {heading}
    </h2>
    <div class="text-base leading-relaxed">
      <PostBody body={pageContent} showFullBody={true} />
    </div>
  </div>
</article>
