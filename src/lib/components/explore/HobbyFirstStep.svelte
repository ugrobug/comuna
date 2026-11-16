<script lang="ts">
  import type { ExploreNode } from '$lib/explore/types'
  import type { HobbySteps } from '$lib/explore/HobbySteps'
  export let node: ExploreNode
  export let steps: HobbySteps
  $: checked = steps.isDone(node)
</script>

{#if node.try_description || node.try_step}
  <section aria-label="Как попробовать">
    <h4>Как попробовать</h4>
    {#if node.try_description}<p>{node.try_description}</p>{/if}
    {#if node.try_step}
      <label><input type="checkbox" bind:checked on:change={e => steps.set(node, e.currentTarget.checked)} />{node.try_step}</label>
    {/if}
  </section>
{/if}

<style>
  section{margin-top:16px;border-top:1px solid #8174ce44;padding-top:12px;font-size:14px;line-height:1.5;overflow-wrap:anywhere}
  h4{font-weight:650}p{margin-top:8px;white-space:pre-line}
  label{display:flex;align-items:baseline;gap:10px;padding:10px 0;cursor:pointer}
  input{flex:none;accent-color:#6250a5}
</style>
