<script lang="ts">
  import { createEventDispatcher } from 'svelte'
  import type { PostTemplateCode } from '$lib/postTemplates'

  export type TemplateTypeOption = {
    value: PostTemplateCode
    label: string
    description?: string
  }

  export let options: TemplateTypeOption[] = []
  export let selectedValues: PostTemplateCode[] = []
  export let disabled = false
  export let placeholder = 'Выберите шаблоны'
  export let searchPlaceholder = 'Поиск шаблона...'
  export let helperText = ''
  export let allowEmpty = false
  export let actionLabel = ''
  export let actionDisabled = false
  export let customItems: Array<{ id: string; label: string }> = []
  export let customItemsTitle = 'Пользовательские шаблоны'

  const dispatch = createEventDispatcher<{
    change: PostTemplateCode[]
    action: void
    customitemclick: string
  }>()

  let query = ''

  const normalizeValue = (value: string) => value.trim().toLowerCase()

  $: selectedSet = new Set(selectedValues)
  $: normalizedQuery = normalizeValue(query)
  $: filteredOptions = options.filter((option) => {
    if (!normalizedQuery) return true
    return [option.label, option.value, option.description ?? ''].some((value) =>
      normalizeValue(value).includes(normalizedQuery)
    )
  })
  $: selectedOptions = options.filter((option) => selectedSet.has(option.value))
  $: summaryLabel = selectedOptions.length
    ? selectedOptions.map((option) => option.label).join(', ')
    : placeholder

  const toggleValue = (value: PostTemplateCode) => {
    const nextSelected = new Set(selectedValues)
    if (nextSelected.has(value)) {
      if (!allowEmpty && nextSelected.size === 1) return
      nextSelected.delete(value)
    } else {
      nextSelected.add(value)
    }
    const nextValues = options
      .map((option) => option.value)
      .filter((optionValue) => nextSelected.has(optionValue))
    dispatch('change', nextValues)
  }

  const triggerAction = () => {
    if (disabled || actionDisabled || !actionLabel) return
    dispatch('action')
  }

  const triggerCustomItemClick = (id: string) => {
    if (disabled) return
    dispatch('customitemclick', id)
  }
</script>

<div class="flex flex-col gap-2">
  <details class="template-type-dropdown group" data-disabled={disabled ? 'true' : 'false'}>
    <summary
      class="template-type-dropdown__summary"
      aria-disabled={disabled}
      tabindex={disabled ? -1 : 0}
    >
      <span class:template-type-dropdown__summary--placeholder={!selectedOptions.length}>
        {summaryLabel}
      </span>
      <span class="template-type-dropdown__chevron">⌄</span>
    </summary>
    <div class="template-type-dropdown__panel">
      <input
        bind:value={query}
        type="text"
        class="template-type-dropdown__search"
        placeholder={searchPlaceholder}
        disabled={disabled}
      />
      <div class="template-type-dropdown__options">
        {#if filteredOptions.length}
          {#each filteredOptions as option}
            <label class="template-type-dropdown__option">
              <input
                type="checkbox"
                checked={selectedSet.has(option.value)}
                disabled={
                  disabled ||
                  (!allowEmpty && selectedSet.has(option.value) && selectedSet.size === 1)
                }
                on:change={() => toggleValue(option.value)}
              />
              <span class="template-type-dropdown__option-copy">
                <span class="template-type-dropdown__option-label">{option.label}</span>
                {#if option.description}
                  <span class="template-type-dropdown__option-description">
                    {option.description}
                  </span>
                {/if}
              </span>
            </label>
          {/each}
        {:else}
          <div class="template-type-dropdown__empty">Шаблоны не найдены</div>
        {/if}
      </div>

      {#if customItems.length}
        <div class="template-type-dropdown__section">
          <div class="template-type-dropdown__section-title">{customItemsTitle}</div>
          <div class="template-type-dropdown__custom-items">
            {#each customItems as item}
              <button
                type="button"
                class="template-type-dropdown__custom-item"
                disabled={disabled}
                on:click={() => triggerCustomItemClick(item.id)}
              >
                <span>{item.label}</span>
                <span class="template-type-dropdown__custom-item-arrow">→</span>
              </button>
            {/each}
          </div>
        </div>
      {/if}

      {#if actionLabel}
        <div class="template-type-dropdown__section">
          <button
            type="button"
            class="template-type-dropdown__action"
            disabled={disabled || actionDisabled}
            on:click={triggerAction}
          >
            {actionLabel}
          </button>
        </div>
      {/if}
    </div>
  </details>

  {#if selectedOptions.length}
    <div class="template-type-dropdown__chips">
      {#each selectedOptions as option}
        <span class="template-type-dropdown__chip">{option.label}</span>
      {/each}
    </div>
  {/if}

  {#if helperText}
    <div class="text-xs text-slate-500 dark:text-zinc-400">{helperText}</div>
  {/if}
</div>

<style>
  .template-type-dropdown {
    position: relative;
  }

  .template-type-dropdown[data-disabled='true'] {
    pointer-events: none;
    opacity: 0.65;
  }

  .template-type-dropdown__summary {
    list-style: none;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
    width: 100%;
    min-height: 3rem;
    padding: 0.75rem 0.9rem;
    border: 1px solid rgb(203 213 225);
    border-radius: 0.9rem;
    background: rgb(255 255 255 / 0.96);
    color: rgb(15 23 42);
    cursor: pointer;
  }

  .template-type-dropdown__summary::-webkit-details-marker {
    display: none;
  }

  :global(.dark) .template-type-dropdown__summary {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27 / 0.88);
    color: rgb(244 244 245);
  }

  .template-type-dropdown__summary--placeholder {
    color: rgb(100 116 139);
  }

  :global(.dark) .template-type-dropdown__summary--placeholder {
    color: rgb(161 161 170);
  }

  .template-type-dropdown[open] .template-type-dropdown__summary {
    border-color: rgb(59 130 246);
    box-shadow: 0 0 0 3px rgb(59 130 246 / 0.12);
  }

  .template-type-dropdown__chevron {
    flex: none;
    color: rgb(100 116 139);
    transition: transform 0.18s ease;
  }

  .template-type-dropdown[open] .template-type-dropdown__chevron {
    transform: rotate(180deg);
  }

  .template-type-dropdown__panel {
    position: absolute;
    top: calc(100% + 0.5rem);
    left: 0;
    right: 0;
    z-index: 30;
    padding: 0.8rem;
    border: 1px solid rgb(226 232 240);
    border-radius: 1rem;
    background: rgb(255 255 255);
    box-shadow: 0 24px 60px rgb(15 23 42 / 0.14);
  }

  :global(.dark) .template-type-dropdown__panel {
    border-color: rgb(63 63 70);
    background: rgb(24 24 27);
    box-shadow: 0 24px 60px rgb(0 0 0 / 0.32);
  }

  .template-type-dropdown__search {
    width: 100%;
    min-height: 2.75rem;
    padding: 0.65rem 0.85rem;
    border: 1px solid rgb(203 213 225);
    border-radius: 0.8rem;
    background: rgb(248 250 252);
  }

  :global(.dark) .template-type-dropdown__search {
    border-color: rgb(63 63 70);
    background: rgb(39 39 42);
    color: rgb(244 244 245);
  }

  .template-type-dropdown__options {
    display: grid;
    gap: 0.55rem;
    max-height: 16rem;
    margin-top: 0.8rem;
    overflow: auto;
  }

  .template-type-dropdown__option {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.75rem 0.85rem;
    border: 1px solid rgb(226 232 240);
    border-radius: 0.8rem;
    background: rgb(248 250 252 / 0.9);
    color: rgb(15 23 42);
    cursor: pointer;
  }

  .template-type-dropdown__option input {
    margin-top: 0.15rem;
    flex: none;
  }

  .template-type-dropdown__option-copy {
    display: flex;
    min-width: 0;
    flex-direction: column;
    gap: 0.2rem;
  }

  .template-type-dropdown__option-label {
    font-weight: 600;
  }

  .template-type-dropdown__option-description {
    color: rgb(100 116 139);
    font-size: 0.82rem;
    line-height: 1.3;
  }

  :global(.dark) .template-type-dropdown__option-description {
    color: rgb(161 161 170);
  }

  :global(.dark) .template-type-dropdown__option {
    border-color: rgb(63 63 70);
    background: rgb(39 39 42 / 0.9);
    color: rgb(244 244 245);
  }

  .template-type-dropdown__empty {
    padding: 0.35rem 0.1rem;
    color: rgb(100 116 139);
    font-size: 0.95rem;
  }

  :global(.dark) .template-type-dropdown__empty {
    color: rgb(161 161 170);
  }

  .template-type-dropdown__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .template-type-dropdown__chip {
    display: inline-flex;
    align-items: center;
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    background: rgb(241 245 249);
    color: rgb(51 65 85);
    font-size: 0.85rem;
  }

  :global(.dark) .template-type-dropdown__chip {
    background: rgb(39 39 42);
    color: rgb(228 228 231);
  }

  .template-type-dropdown__section {
    margin-top: 0.85rem;
    padding-top: 0.85rem;
    border-top: 1px solid rgb(226 232 240);
  }

  :global(.dark) .template-type-dropdown__section {
    border-top-color: rgb(63 63 70);
  }

  .template-type-dropdown__section-title {
    margin-bottom: 0.55rem;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: rgb(100 116 139);
  }

  :global(.dark) .template-type-dropdown__section-title {
    color: rgb(161 161 170);
  }

  .template-type-dropdown__custom-items {
    display: grid;
    gap: 0.45rem;
  }

  .template-type-dropdown__custom-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    width: 100%;
    padding: 0.75rem 0.85rem;
    border: 1px solid rgb(226 232 240);
    border-radius: 0.8rem;
    background: rgb(255 255 255);
    color: rgb(15 23 42);
    text-align: left;
  }

  :global(.dark) .template-type-dropdown__custom-item {
    border-color: rgb(63 63 70);
    background: rgb(39 39 42 / 0.75);
    color: rgb(244 244 245);
  }

  .template-type-dropdown__custom-item-arrow {
    color: rgb(148 163 184);
  }

  .template-type-dropdown__action {
    width: 100%;
    min-height: 2.75rem;
    padding: 0.75rem 0.95rem;
    border: 1px dashed rgb(148 163 184);
    border-radius: 0.8rem;
    background: rgb(248 250 252);
    color: rgb(15 23 42);
    font-weight: 600;
  }

  :global(.dark) .template-type-dropdown__action {
    border-color: rgb(113 113 122);
    background: rgb(39 39 42 / 0.72);
    color: rgb(244 244 245);
  }
</style>
