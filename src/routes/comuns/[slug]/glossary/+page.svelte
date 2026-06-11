<script lang="ts">
  import { tick } from 'svelte'
  import Header from '$lib/components/ui/layout/pages/Header.svelte'
  import { buildComunUrl, type BackendComun, type BackendComunGlossaryTerm } from '$lib/api/backend'
  import { Button, toast } from 'mono-svelte'
  import { siteToken, siteUser } from '$lib/siteAuth'

  export let data

  type GlossaryDraftTerm = BackendComunGlossaryTerm & { localId: string }

  let comun: BackendComun | null = data?.comun ?? null
  let searchQuery = ''
  let glossarySaving = false
  let glossaryError = ''
  let draftTerms: GlossaryDraftTerm[] = []
  let glossarySettingsOpen = false
  let glossarySettingsSection: HTMLElement | null = null
  let glossaryAutoLinkDraft = Boolean(comun?.glossary_auto_link_enabled)

  const createGlossaryLocalId = () =>
    `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`

  const normalizeGlossaryTerms = (
    terms: Array<BackendComunGlossaryTerm | GlossaryDraftTerm> | null | undefined
  ): GlossaryDraftTerm[] =>
    (terms ?? []).map((term, index) => ({
      id: Number(term?.id ?? 0) || 0,
      localId: (term as GlossaryDraftTerm)?.localId || createGlossaryLocalId(),
      term: String(term?.term ?? '').trim(),
      slug: String(term?.slug ?? '').trim(),
      definition: String(term?.definition ?? '').trim(),
      sort_order: Number(term?.sort_order ?? index) || index,
    }))

  draftTerms = normalizeGlossaryTerms(comun?.glossary_terms)

  const authHeaders = () => {
    if (!$siteToken) throw new Error('Нужна авторизация')
    return {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${$siteToken}`,
    }
  }

  $: currentUserId = Number($siteUser?.id ?? 0)
  $: canManageGlossary = Boolean(
    $siteToken &&
      currentUserId > 0 &&
      (Number(comun?.creator?.id ?? 0) === currentUserId ||
        (comun?.moderators ?? []).some(
          (moderator) => Number(moderator?.id ?? 0) === currentUserId
        ) ||
        comun?.can_moderate)
  )
  $: normalizedSearchQuery = searchQuery.trim().toLowerCase()
  $: filteredGlossaryTerms = draftTerms.filter((term) => {
    if (!normalizedSearchQuery) return true
    return [term.term, term.definition].some((value) =>
      String(value ?? '').toLowerCase().includes(normalizedSearchQuery)
    )
  })
  $: draftComparable = JSON.stringify(
    draftTerms.map((term) => ({
      id: Number(term.id) || 0,
      term: term.term.trim(),
      definition: term.definition.trim(),
    }))
  )
  $: sourceComparable = JSON.stringify(
    normalizeGlossaryTerms(comun?.glossary_terms).map((term) => ({
      id: Number(term.id) || 0,
      term: term.term.trim(),
      definition: term.definition.trim(),
    }))
  )
  $: glossaryAutoLinkHasChanges =
    glossaryAutoLinkDraft !== Boolean(comun?.glossary_auto_link_enabled)
  $: glossaryHasChanges = draftComparable !== sourceComparable || glossaryAutoLinkHasChanges

  const openGlossarySettings = async () => {
    glossarySettingsOpen = true
    await tick()
    glossarySettingsSection?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const addDraftGlossaryTerm = () => {
    draftTerms = [
      ...draftTerms,
      {
        id: 0,
        localId: createGlossaryLocalId(),
        term: '',
        slug: '',
        definition: '',
        sort_order: draftTerms.length,
      },
    ]
  }

  const updateDraftGlossaryTerm = (
    localId: string,
    field: 'term' | 'definition',
    value: string
  ) => {
    draftTerms = draftTerms.map((term, index) =>
      term.localId === localId
        ? { ...term, [field]: value, sort_order: index }
        : { ...term, sort_order: index }
    )
  }

  const removeDraftGlossaryTerm = (localId: string) => {
    draftTerms = draftTerms
      .filter((term) => term.localId !== localId)
      .map((term, index) => ({ ...term, sort_order: index }))
  }

  const onGlossaryTermInput = (localId: string, event: Event) => {
    const target = event.currentTarget as HTMLInputElement | null
    updateDraftGlossaryTerm(localId, 'term', target?.value ?? '')
  }

  const onGlossaryDefinitionInput = (localId: string, event: Event) => {
    const target = event.currentTarget as HTMLTextAreaElement | null
    updateDraftGlossaryTerm(localId, 'definition', target?.value ?? '')
  }

  const saveGlossary = async () => {
    if (!comun?.slug || !canManageGlossary || glossarySaving) return
    glossarySaving = true
    glossaryError = ''
    try {
      const response = await fetch(buildComunUrl(comun.slug), {
        method: 'PATCH',
        headers: authHeaders(),
        body: JSON.stringify({
          glossary_auto_link_enabled: glossaryAutoLinkDraft,
          glossary_terms: draftTerms.map((term, index) => ({
            id: Number(term.id) || undefined,
            term: term.term.trim(),
            definition: term.definition.trim(),
            sort_order: index,
          })),
        }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok) {
        throw new Error(payload?.error || 'Не удалось сохранить глоссарий')
      }
      comun = payload?.comun ?? comun
      draftTerms = normalizeGlossaryTerms(comun?.glossary_terms)
      glossaryAutoLinkDraft = Boolean(comun?.glossary_auto_link_enabled)
      toast({ content: 'Глоссарий сохранен', type: 'success' })
    } catch (error) {
      glossaryError = error instanceof Error ? error.message : 'Не удалось сохранить глоссарий'
      toast({ content: glossaryError, type: 'error' })
    } finally {
      glossarySaving = false
    }
  }
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
    <div class="flex flex-wrap items-center gap-2">
      {#if canManageGlossary}
        <Button size="sm" on:click={addDraftGlossaryTerm} disabled={glossarySaving}>
          Добавить термин
        </Button>
      {/if}
      <a
        href={comun?.slug ? `/comuns/${encodeURIComponent(comun.slug)}` : '/comuns'}
        class="inline-flex items-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-medium text-slate-900 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-800/60"
      >
        Назад к сообществу
      </a>
      {#if canManageGlossary}
        <button
          type="button"
          on:click={openGlossarySettings}
          class="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-900 transition hover:bg-slate-50 dark:border-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-800/60"
          aria-label="Настройки глоссария"
          title="Настройки глоссария"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            class="h-5 w-5"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.04.04a2.05 2.05 0 0 1-2.9 2.9l-.04-.04A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21a2.05 2.05 0 0 1-4.1 0v-.06A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.04.04a2.05 2.05 0 0 1-2.9-2.9l.04-.04A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3a2.05 2.05 0 0 1 0-4.1h.06A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.04-.04a2.05 2.05 0 0 1 2.9-2.9l.04.04A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3a2.05 2.05 0 0 1 4.1 0v.06A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.04-.04a2.05 2.05 0 0 1 2.9 2.9l-.04.04A1.7 1.7 0 0 0 19.4 9c.4.2.75.4 1 .6.3.3.4.7.4 1.1V11a2.05 2.05 0 0 1 0 4.1h-.06a1.7 1.7 0 0 0-1.34.9Z" />
          </svg>
        </button>
      {/if}
    </div>
  </div>

  {#if glossaryError}
    <div class="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900/50 dark:bg-rose-950/20 dark:text-rose-300">
      {glossaryError}
    </div>
  {/if}

  <section class="rounded-2xl border border-slate-200 bg-white/95 p-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-900/85">
    <div class="flex flex-col gap-4">
      {#if canManageGlossary && glossarySettingsOpen}
        <section
          id="glossary-settings"
          bind:this={glossarySettingsSection}
          class="rounded-2xl border border-slate-200 bg-slate-50/70 p-4 dark:border-zinc-800 dark:bg-zinc-900/60"
        >
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div class="max-w-3xl">
              <div class="text-sm font-semibold text-slate-900 dark:text-zinc-100">
                Настройки глоссария
              </div>
              <p class="mt-1 text-sm text-slate-600 dark:text-zinc-400">
                Управляйте тем, как термины глоссария предлагаются авторам при публикации постов в этом сообществе.
              </p>
            </div>
            <Button on:click={saveGlossary} disabled={glossarySaving || !glossaryHasChanges}>
              {glossarySaving ? 'Сохраняем...' : 'Сохранить настройки'}
            </Button>
          </div>

          <label class="mt-4 flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 bg-white/75 p-3 dark:border-zinc-800 dark:bg-zinc-950/30">
            <input
              type="checkbox"
              class="mt-1"
              checked={glossaryAutoLinkDraft}
              disabled={glossarySaving}
              on:change={() => {
                glossaryAutoLinkDraft = !glossaryAutoLinkDraft
              }}
            />
            <span class="min-w-0">
              <span class="block font-semibold text-slate-900 dark:text-zinc-100">
                Автоматически искать термины в тексте
              </span>
              <span class="mt-1 block text-sm text-slate-600 dark:text-zinc-400">
                При сохранении поста автор увидит найденные термины, их расшифровки и сможет согласовать разметку.
              </span>
            </span>
          </label>
        </section>
      {/if}

      <div class="flex flex-wrap items-center justify-between gap-3">
        <input
          bind:value={searchQuery}
          type="text"
          placeholder="Поиск по термину или расшифровке..."
          class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500 sm:max-w-md"
        />
        {#if canManageGlossary && glossaryHasChanges}
          <Button on:click={saveGlossary} disabled={glossarySaving}>
            {glossarySaving ? 'Сохраняем...' : 'Сохранить глоссарий'}
          </Button>
        {/if}
      </div>

      {#if filteredGlossaryTerms.length}
        <div class="grid gap-3">
          {#each filteredGlossaryTerms as term (term.localId)}
            <article
              id={term.slug ? `term-${term.slug}` : undefined}
              class="rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-4 dark:border-zinc-800 dark:bg-zinc-900/60"
            >
              {#if canManageGlossary}
                <div class="flex items-start justify-between gap-3">
                  <div class="flex-1 grid gap-3">
                    <input
                      value={term.term}
                      on:input={(event) => onGlossaryTermInput(term.localId, event)}
                      placeholder="Термин"
                      class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-base font-semibold text-slate-900 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-zinc-500"
                    />
                    <textarea
                      rows="4"
                      on:input={(event) => onGlossaryDefinitionInput(term.localId, event)}
                      class="rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm leading-relaxed text-slate-700 outline-none focus:border-slate-400 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:focus:border-zinc-500"
                      placeholder="Расшифровка термина"
                    >{term.definition}</textarea>
                  </div>
                  <button
                    type="button"
                    class="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600 dark:border-zinc-700 dark:text-zinc-400 dark:hover:border-rose-900/60 dark:hover:bg-rose-950/30 dark:hover:text-rose-300"
                    title="Удалить термин"
                    aria-label="Удалить термин"
                    on:click={() => removeDraftGlossaryTerm(term.localId)}
                  >
                    <svg viewBox="0 0 24 24" class="h-4 w-4" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                      <path d="M3 6h18"></path>
                      <path d="M8 6V4.8c0-.9.7-1.6 1.6-1.6h4.8c.9 0 1.6.7 1.6 1.6V6"></path>
                      <path d="M18 6v12.2c0 .9-.7 1.6-1.6 1.6H7.6c-.9 0-1.6-.7-1.6-1.6V6"></path>
                      <path d="M10 10.5v5"></path>
                      <path d="M14 10.5v5"></path>
                    </svg>
                  </button>
                </div>
              {:else}
                <div class="text-lg font-semibold text-slate-900 dark:text-zinc-100">
                  {term.term}
                </div>
                <div class="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
                  {term.definition}
                </div>
              {/if}
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
