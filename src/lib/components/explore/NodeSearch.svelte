<script lang="ts">
  import type { ExploreNode } from '$lib/explore/types'

  export let id: string
  export let label: string
  export let nodes: ExploreNode[] = []
  export let selected: number | null = null
  export let exclude: number | null = null
  export let disabled = false
  let query = '', open = false, highlighted = 0
  let input: HTMLInputElement
  $: chosen = nodes.find(node => node.id === selected)
  $: matches = nodes.filter(node => node.id !== exclude && node.title.toLocaleLowerCase('ru').includes(query.trim().toLocaleLowerCase('ru')))
  $: results = matches.slice(0, 30)
  $: if (highlighted >= results.length) highlighted = Math.max(0, results.length - 1)

  function choose(node: ExploreNode) {
    selected = node.id; query = ''; open = false
    input.focus()
  }
  function search(event: Event) {
    selected = null; query = (event.target as HTMLInputElement).value
    open = true; highlighted = 0
  }
  function keydown(event: KeyboardEvent) {
    if (event.key === 'Escape') { open = false; return }
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      const wasOpen = open
      open = true
      highlighted = wasOpen ? Math.max(0, Math.min(results.length - 1, highlighted + (event.key === 'ArrowDown' ? 1 : -1))) : 0
      requestAnimationFrame(() => document.getElementById(`${id}-option-${results[highlighted]?.id}`)?.scrollIntoView({block:'nearest'}))
    } else if (event.key === 'Enter' && open) {
      event.preventDefault()
      if (results[highlighted]) choose(results[highlighted])
    }
  }
</script>

<div class="node-search" on:focusout={(event) => { if (!event.currentTarget.contains(event.relatedTarget as Node)) open = false }}>
  <label for={id}>{label}</label>
  <div class="input-wrap">
    <input bind:this={input} {id} type="text" role="combobox" autocomplete="off" {disabled}
      aria-expanded={open} aria-controls={`${id}-results`} aria-autocomplete="list"
      aria-activedescendant={open && results[highlighted] ? `${id}-option-${results[highlighted].id}` : undefined}
      placeholder="Найти элемент или сообщество" value={chosen?.title ?? query}
      on:focus={() => { if (!chosen) open = true }} on:input={search} on:keydown={keydown} />
    {#if chosen || query}<button type="button" class="clear" aria-label={`Очистить: ${label}`} {disabled} on:click={() => { selected = null; query = ''; open = true; highlighted = 0; input.focus() }}>×</button>{/if}
  </div>
  {#if chosen}<p class="selected-kind">{chosen.kind === 'element' ? 'Элемент' : 'Сообщество'}{!chosen.is_active ? ' · скрыт' : ''}</p>{/if}
  {#if open && !disabled}
    <div class="suggestions">
      <ul id={`${id}-results`} role="listbox" aria-label={label}>
        {#each results as node, index (node.id)}
          <li id={`${id}-option-${node.id}`} role="option" aria-selected={highlighted === index} class:highlighted={highlighted === index}
            on:pointerdown|preventDefault={() => choose(node)}>
            <span>{node.title}</span><small>{node.kind === 'element' ? 'Элемент' : 'Сообщество'} · #{node.id}{!node.is_active ? ' · скрыт' : ''}</small>
          </li>
        {/each}
      </ul>
      {#if !results.length}<p role="status">Ничего не найдено. Проверьте название или добавьте узел в граф.</p>
      {:else if matches.length > results.length}<p>Найдено {matches.length}. Уточните название, чтобы сузить поиск.</p>{/if}
    </div>
  {/if}
</div>

<style>
  .node-search{position:relative;flex:1;min-width:0}label{display:block;margin-bottom:8px;font-size:12px}.input-wrap{position:relative}input{width:100%;box-sizing:border-box;border:1px solid #d9dfeb;border-radius:9px;padding:10px 34px 10px 12px;font-size:13px;background:transparent;color:inherit}input:focus-visible{outline:2px solid #8174ce;outline-offset:2px}.clear{position:absolute;right:5px;top:5px;padding:3px 7px;font-size:20px;line-height:1;color:#8b91a4;cursor:pointer}.selected-kind{font-size:10px;color:#8691a3;margin-top:5px}.suggestions{position:absolute;left:0;right:0;top:68px;z-index:10;border:1px solid #d9dfeb;border-radius:10px;background:white;box-shadow:0 12px 30px #30375122;overflow:hidden}ul{max-height:260px;overflow:auto;padding:4px;margin:0;list-style:none}li{padding:10px;border-radius:7px;cursor:pointer}li:hover,.highlighted{background:#f2effa;color:#7060b2}li span,li small{display:block}li span{font-size:13px;overflow-wrap:anywhere}li small{font-size:10px;color:#8691a3;margin-top:4px}.suggestions p{padding:10px 14px;font-size:11px;color:#8691a3}input:disabled,button:disabled{opacity:.5}:global(.dark) .suggestions{background:#242631;border-color:#414454}:global(.dark) li:hover,:global(.dark) .highlighted{background:#3a334f;color:#c6b8f2}
</style>
