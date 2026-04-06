<script lang="ts">
  import Header from '$lib/components/ui/layout/pages/Header.svelte'

  export let data

  let searchQuery = ''

  $: comun = data?.comun ?? null
  $: glossaryTerms = comun?.glossary_terms ?? []
  $: normalizedSearchQuery = searchQuery.trim().toLowerCase()
  $: filteredGlossaryTerms = glossaryTerms.filter((term) => {
    if (!normalizedSearchQuery) return true
    return [term.term, term.definition].some((value) =>
      String(value ?? '').toLowerCase().includes(normalizedSearchQuery)
    )
  })
</script>

<div class="flex w-full flex-col gap-6">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <div class="min-w-0">
      <div class="text-xs uppercase tracking-wide text-slate-500 dark:text-zinc-400">
        Сообщество
      </div>
      <Header noMargin>Глоссарий</Header>
      {#if comun?.name}
        <div class="truncate text-sm text-slate-600 dark:text-zinc-400">{comun.name}</div>
      {/if}
    </div>
    <a
      href={comun?.slug ? `/comuns/${encodeURIComponent(comun.slug)}` : '/comuns'}
      class="inline-flex items-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-800/60"
    >
      Назад к сообществу
    </a>
  </div>

  <section class="rounded-2xl border border-slate-200 bg-white/95 p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
    <div class="flex flex-col gap-4">
      <input
        bind:value={searchQuery}
        type="text"
        placeholder="Поиск по термину или расшифровке..."
        class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
      />

      {#if filteredGlossaryTerms.length}
        <div class="grid gap-3">
          {#each filteredGlossaryTerms as term (term.id)}
            <article
              id={term.slug ? `term-${term.slug}` : undefined}
              class="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/60"
            >
              <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">
                {term.term}
              </div>
              <div class="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
                {term.definition}
              </div>
            </article>
          {/each}
        </div>
      {:else}
        <div class="rounded-xl border border-slate-200 px-4 py-4 text-sm text-slate-500 dark:border-zinc-800 dark:text-zinc-400">
          {normalizedSearchQuery ? 'Ничего не найдено' : 'Термины пока не добавлены'}
        </div>
      {/if}
    </div>
  </section>
</div>

<svelte:head>
  <title>{comun?.name ? `Глоссарий ${comun.name}` : 'Глоссарий сообщества'}</title>
</svelte:head>
