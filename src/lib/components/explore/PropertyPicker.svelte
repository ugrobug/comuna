<script lang="ts">
  import type { ExploreProperty } from '$lib/explore/types'
  export let properties: ExploreProperty[] = []
  export let selected: number[] = []
  export let disabled = false
  export let emptyLabel = 'Все'
  function toggle(id: number) {
    selected = selected.includes(id) ? selected.filter(value => value !== id) : [...selected, id]
  }
</script>

<div class="property-pickers">
  {#each properties as property (property.id)}
    <details>
      <summary>{property.name}<span>{property.options.filter(option => selected.includes(option.id)).length || emptyLabel} ▾</span></summary>
      <div class="options">
        {#each property.options as option (option.id)}
          <label><input type="checkbox" checked={selected.includes(option.id)} {disabled} on:change={() => toggle(option.id)} />{option.label}</label>
        {/each}
      </div>
    </details>
  {/each}
</div>

<style>
  .property-pickers{display:grid;gap:8px}details{border:1px solid #dce2eb;border-radius:12px;background:var(--explore-surface,#fff);color:var(--explore-ink,#26324b)}summary{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:12px;font-size:13px;cursor:pointer;list-style:none}summary::-webkit-details-marker{display:none}summary span{white-space:nowrap;color:#667696;font-size:11px}.options{padding:0 12px 12px;display:grid;gap:10px}label{display:flex;align-items:center;gap:9px;font-size:13px;cursor:pointer}input{accent-color:#6558c8;width:15px;height:15px}
</style>
