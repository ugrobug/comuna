<script lang="ts">
  import { browser } from '$app/environment'
  import { createEventDispatcher } from 'svelte'
  import { Button } from 'mono-svelte'
  import { Check, Icon, XMark } from 'svelte-hero-icons'
  import type { GlossaryAutoLinkMatch } from '$lib/glossaryAutoLink'

  export let open = false
  export let matches: GlossaryAutoLinkMatch[] = []

  const dispatch = createEventDispatcher<{
    applyAll: void
    applySelected: { ids: string[] }
    cancel: void
  }>()

  let acceptedIds: string[] = []
  let pendingMatches: GlossaryAutoLinkMatch[] = []
  let lastMatchKey = ''
  let activeDefinitionId = ''

  const portal = (node: HTMLElement) => {
    if (!browser) return
    document.body.appendChild(node)
    return {
      destroy() {
        node.remove()
      },
    }
  }

  $: if (open) {
    const nextMatchKey = matches.map((match) => match.id).join('|')
    if (nextMatchKey !== lastMatchKey) {
      acceptedIds = []
      pendingMatches = matches
      lastMatchKey = nextMatchKey
      activeDefinitionId = ''
    }
  }

  $: if (!open && lastMatchKey) {
    acceptedIds = []
    pendingMatches = []
    lastMatchKey = ''
    activeDefinitionId = ''
  }

  const finishIfResolved = (nextAcceptedIds: string[], nextPendingMatches: GlossaryAutoLinkMatch[]) => {
    if (!nextPendingMatches.length) {
      dispatch('applySelected', { ids: nextAcceptedIds })
    }
  }

  const acceptMatch = (id: string) => {
    const nextAcceptedIds = acceptedIds.includes(id) ? acceptedIds : [...acceptedIds, id]
    const nextPendingMatches = pendingMatches.filter((match) => match.id !== id)
    acceptedIds = nextAcceptedIds
    pendingMatches = nextPendingMatches
    if (activeDefinitionId === id) {
      activeDefinitionId = ''
    }
    finishIfResolved(nextAcceptedIds, nextPendingMatches)
  }

  const rejectMatch = (id: string) => {
    const nextPendingMatches = pendingMatches.filter((match) => match.id !== id)
    pendingMatches = nextPendingMatches
    if (activeDefinitionId === id) {
      activeDefinitionId = ''
    }
    finishIfResolved(acceptedIds, nextPendingMatches)
  }

  const acceptAllRemaining = () => {
    const nextAcceptedIds = Array.from(
      new Set([...acceptedIds, ...pendingMatches.map((match) => match.id)])
    )
    dispatch('applySelected', { ids: nextAcceptedIds })
  }

  const toggleDefinition = (id: string) => {
    activeDefinitionId = activeDefinitionId === id ? '' : id
  }

  const handleTermKeydown = (event: KeyboardEvent, id: string) => {
    if (event.key !== 'Enter' && event.key !== ' ') return
    event.preventDefault()
    toggleDefinition(id)
  }

  const splitMatchContext = (match: GlossaryAutoLinkMatch) => {
    const context = match.context || match.matchedText
    const matched = match.matchedText || match.term
    const index = context.toLocaleLowerCase('ru-RU').indexOf(matched.toLocaleLowerCase('ru-RU'))
    if (index === -1) {
      return {
        before: context,
        highlight: matched,
        after: '',
      }
    }
    return {
      before: context.slice(0, index),
      highlight: context.slice(index, index + matched.length),
      after: context.slice(index + matched.length),
    }
  }

  const cancelOnBackdropClick = (event: MouseEvent) => {
    if (event.target === event.currentTarget) {
      dispatch('cancel')
    }
  }
</script>

{#if open}
  <div
    use:portal
    class="fixed inset-0 z-[10000] flex h-screen w-screen items-center justify-center bg-slate-950/65 px-4 py-6 backdrop-blur-[1px] sm:py-8"
    role="presentation"
    on:click={cancelOnBackdropClick}
  >
    <div
      class="flex max-h-[min(760px,calc(100vh-2rem))] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl dark:border-zinc-800 dark:bg-zinc-950"
      role="dialog"
      aria-modal="true"
      aria-labelledby="glossary-auto-link-title"
      tabindex="-1"
      on:keydown={(event) => {
        if (event.key === 'Escape') dispatch('cancel')
      }}
    >
      <div class="border-b border-slate-200 px-5 py-4 dark:border-zinc-800">
        <h2 id="glossary-auto-link-title" class="text-lg font-semibold text-slate-950 dark:text-zinc-50">
          В тексте есть термины
        </h2>
        <p class="mt-1 text-sm text-slate-500 dark:text-zinc-400">
          Выбрав слово термином - при наведении пользователю будет показано его значение
        </p>
      </div>

      <div class="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        <div class="flex flex-col gap-3">
          {#each pendingMatches as match (match.id)}
            {@const context = splitMatchContext(match)}
            <div
              class="flex items-start gap-3 rounded-xl border border-sky-200 bg-sky-50/50 p-3 transition-colors dark:border-emerald-900/60 dark:bg-emerald-950/10"
            >
              <div class="min-w-0 flex-1">
                <p class="glossary-context text-sm leading-relaxed text-slate-700 dark:text-zinc-300">
                  {context.before}<span
                    class={`post-glossary-term ${activeDefinitionId === match.id ? 'post-glossary-term--active' : ''}`}
                    role="button"
                    tabindex="0"
                    data-glossary-term={match.term}
                    data-glossary-slug={match.slug}
                    data-glossary-definition={match.definition}
                    title={match.definition}
                    aria-label={`Показать значение термина "${match.matchedText}"`}
                    on:click|stopPropagation={() => toggleDefinition(match.id)}
                    on:keydown={(event) => handleTermKeydown(event, match.id)}
                  >{context.highlight}</span>{context.after}
                </p>
                <p class="mt-2 text-sm leading-relaxed text-slate-500 dark:text-zinc-400">
                  {match.definition}
                </p>
              </div>
              <div class="flex shrink-0 items-center gap-2">
                <button
                  type="button"
                  class="grid h-9 w-9 place-items-center rounded-full border border-emerald-500 bg-emerald-500 text-white shadow-sm transition-colors hover:bg-emerald-600"
                  aria-label={`Отметить "${match.matchedText}" термином`}
                  on:click={() => acceptMatch(match.id)}
                >
                  <Icon src={Check} size="18" mini />
                </button>
                <button
                  type="button"
                  class="grid h-9 w-9 place-items-center rounded-full border border-slate-200 bg-white text-slate-500 transition-colors hover:border-rose-300 hover:text-rose-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400"
                  aria-label={`Не отмечать "${match.matchedText}" термином`}
                  on:click={() => rejectMatch(match.id)}
                >
                  <Icon src={XMark} size="18" mini />
                </button>
              </div>
            </div>
          {/each}
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 px-5 py-4 dark:border-zinc-800">
        <div class="text-sm text-slate-500 dark:text-zinc-400">
          Принято {acceptedIds.length}, осталось {pendingMatches.length}
        </div>
        <div class="flex flex-wrap gap-2">
          <Button color="ghost" on:click={() => dispatch('cancel')}>Отмена</Button>
          <Button color="primary" disabled={!pendingMatches.length} on:click={acceptAllRemaining}>
            Согласовать все
          </Button>
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .glossary-context :global(.post-glossary-term) {
    position: relative;
    border-bottom: 1px dashed rgb(14 165 233 / 0.7);
    background: rgb(14 165 233 / 0.08);
    color: rgb(15 118 110);
    cursor: help;
    transition: background-color 0.18s ease, color 0.18s ease;
  }

  .glossary-context :global(.post-glossary-term:hover) {
    background: rgb(14 165 233 / 0.16);
  }

  .glossary-context :global(.post-glossary-term::after) {
    content: attr(data-glossary-definition);
    position: absolute;
    left: 50%;
    top: calc(100% + 0.45rem);
    z-index: 30;
    width: min(20rem, 70vw);
    transform: translateX(-50%) translateY(-4px);
    border-radius: 12px;
    background: rgba(15, 23, 42, 0.96);
    box-shadow: 0 18px 40px rgba(15, 23, 42, 0.22);
    color: white;
    padding: 0.65rem 0.8rem;
    font-size: 0.82rem;
    line-height: 1.45;
    opacity: 0;
    pointer-events: none;
    white-space: normal;
    transition: opacity 0.18s ease, transform 0.18s ease;
  }

  .glossary-context :global(.post-glossary-term:hover::after),
  .glossary-context :global(.post-glossary-term:focus-visible::after),
  .glossary-context :global(.post-glossary-term.post-glossary-term--active::after) {
    opacity: 1;
    transform: translateX(-50%);
  }

  :global(.dark) .glossary-context :global(.post-glossary-term) {
    border-bottom-color: rgb(74 222 128 / 0.65);
    background: rgb(34 197 94 / 0.14);
    color: rgb(187 247 208);
  }

  :global(.dark) .glossary-context :global(.post-glossary-term:hover) {
    background: rgb(34 197 94 / 0.22);
  }
</style>
