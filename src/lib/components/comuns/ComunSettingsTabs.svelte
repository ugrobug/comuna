<script lang="ts">
  import { createEventDispatcher } from 'svelte'

  type ComunSettingsTab = {
    value: string
    label: string
  }

  export let tabs: ComunSettingsTab[] = []
  export let value = ''

  const dispatch = createEventDispatcher<{ change: string }>()

  const selectTab = (nextValue: string) => {
    if (!nextValue || nextValue === value) return
    dispatch('change', nextValue)
  }
</script>

<div class="comun-settings-tabs" role="tablist" aria-label="Разделы настроек сообщества">
  {#each tabs as tab}
    <button
      type="button"
      role="tab"
      class="comun-settings-tab"
      class:is-active={value === tab.value}
      aria-selected={value === tab.value}
      tabindex={value === tab.value ? 0 : -1}
      on:click={() => selectTab(tab.value)}
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
