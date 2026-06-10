<script lang="ts">
  import type { BackendComun } from '$lib/api/backend'
  import { createEventDispatcher } from 'svelte'

  export let comun: BackendComun
  export let subscribed = false
  export let subscriptionsLoading = false

  const dispatch = createEventDispatcher<{ toggle: void }>()

  const hashString = (value?: string | null) => {
    const source = (value ?? '').trim() || 'comuna'
    let hash = 0
    for (let i = 0; i < source.length; i += 1) {
      hash = (hash * 31 + source.charCodeAt(i)) % 360
    }
    return Math.abs(hash)
  }

  const comunPlaceholderStyle = (name?: string | null) => `--comun-h:${hashString(name)}`

  const comunInitial = (name?: string | null) =>
    (name ?? '').trim().slice(0, 1).toUpperCase() || 'C'
</script>

<div
  class="group rounded-2xl border border-slate-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/85 p-4 sm:p-5 hover:border-blue-300 dark:hover:border-blue-700 hover:shadow-sm transition-all min-w-0"
>
  <div class="flex items-start gap-4 min-w-0">
    <div class="flex shrink-0 flex-col items-center gap-2">
      <a
        href={`/comuns/${comun.slug}`}
        class="h-14 w-14 rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 bg-slate-100 dark:bg-zinc-800"
        aria-label={`Открыть сообщество ${comun.name}`}
      >
        {#if comun.logo_url}
          <img src={comun.logo_url} alt={comun.name} class="h-full w-full object-cover" />
        {:else}
          <div
            class="comun-logo-fallback h-full w-full grid place-items-center text-xl font-bold"
            style={comunPlaceholderStyle(comun.name)}
          >
            {comunInitial(comun.name)}
          </div>
        {/if}
      </a>
      <button
        type="button"
        class={`grid h-9 w-9 place-items-center rounded-full border transition ${
          subscribed
            ? 'border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-300'
            : 'border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-900/70 dark:bg-blue-950/40 dark:text-blue-300'
        } ${subscriptionsLoading ? 'opacity-60 cursor-wait' : ''}`}
        title={subscriptionsLoading ? 'Загружаем подписки...' : subscribed ? 'Вы подписаны' : 'Подписаться'}
        aria-label={subscribed ? `Отписаться от ${comun.name}` : `Подписаться на ${comun.name}`}
        aria-pressed={subscribed}
        disabled={subscriptionsLoading}
        on:click|preventDefault|stopPropagation={() => dispatch('toggle')}
      >
        {#if subscribed}
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M4.5 10.4 8.1 14 15.7 6" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        {:else}
          <svg class="h-4 w-4" viewBox="0 0 20 20" fill="none" aria-hidden="true">
            <path d="M10 4v12M4 10h12" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" />
          </svg>
        {/if}
      </button>
    </div>
    <a href={`/comuns/${comun.slug}`} class="min-w-0 flex-1">
      <div class="flex items-center gap-2 min-w-0">
        <div class="text-base font-semibold text-slate-900 dark:text-zinc-100 truncate">
          {comun.name}
        </div>
      </div>
      {#if comun.product_description}
        <div class="mt-1 text-sm text-slate-600 dark:text-zinc-400 line-clamp-3">
          {comun.product_description}
        </div>
      {/if}
    </a>
  </div>
</div>

<style>
  .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 60% 92%);
    color: hsl(var(--comun-h, 220) 70% 34%);
  }

  :global(.dark) .comun-logo-fallback {
    background: hsl(var(--comun-h, 220) 35% 20%);
    color: hsl(var(--comun-h, 220) 78% 72%);
  }
</style>
