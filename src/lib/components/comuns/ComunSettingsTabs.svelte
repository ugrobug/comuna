<script lang="ts">
  import { createEventDispatcher } from 'svelte'

  type ComunSettingsTab = {
    value: string
    label: string
  }

  export let tabs: ComunSettingsTab[] = []
  export let value = ''
  export let ariaLabel = 'Разделы настроек сообщества'
  export let panelPrefix = ''

  const dispatch = createEventDispatcher<{ change: string }>()

  const selectTab = (nextValue: string) => {
    if (!nextValue || nextValue === value) return
    dispatch('change', nextValue)
  }
  const onKeydown = (event: KeyboardEvent, index: number) => {
    const offsets: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: tabs.length - 1 - index }
    if (!(event.key in offsets) || !tabs.length) return
    event.preventDefault()
    const nextIndex = (index + offsets[event.key] + tabs.length) % tabs.length
    const button = event.currentTarget as HTMLButtonElement
    const buttons = button.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')
    buttons?.[nextIndex]?.focus()
    selectTab(tabs[nextIndex].value)
  }
</script>

<div class="comun-settings-tabs" role="tablist" aria-label={ariaLabel}>
  {#each tabs as tab, index}
    <button
      type="button"
      role="tab"
      id={panelPrefix ? `${panelPrefix}-tab-${tab.value}` : undefined}
      aria-controls={panelPrefix ? `${panelPrefix}-panel-${tab.value}` : undefined}
      class="comun-settings-tab"
      class:is-active={value === tab.value}
      aria-selected={value === tab.value}
      tabindex={value === tab.value ? 0 : -1}
      on:click={() => selectTab(tab.value)}
      on:keydown={(event) => onKeydown(event, index)}
    >
      {tab.label}
    </button>
  {/each}
</div>

<style>
  .comun-settings-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 1.25rem;
  }

  .comun-settings-tab {
    border-radius: 9999px;
    padding: 0.5rem 0.75rem;
    font-size: 0.875rem;
    line-height: 1.25rem;
    font-weight: 500;
    transition:
      background-color 0.2s ease,
      color 0.2s ease;
    background: rgb(241 245 249);
    color: rgb(51 65 85);
  }

  .comun-settings-tab:hover {
    background: rgb(226 232 240);
  }

  .comun-settings-tab.is-active {
    background: rgb(15 23 42);
    color: white;
  }

  :global(.dark) .comun-settings-tab {
    background: rgb(39 39 42);
    color: rgb(228 228 231);
  }

  :global(.dark) .comun-settings-tab:hover {
    background: rgb(63 63 70);
  }

  :global(.dark) .comun-settings-tab.is-active {
    background: white;
    color: rgb(24 24 27);
  }
</style>
