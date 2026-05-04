<script lang="ts">
  import { templateEditorDraggedItem, type TemplateEditorDragPaletteItem } from '$lib/components/comuns/templateEditorDnd'

  export let fieldOptions: Array<{ value: string; label: string }> = []
  export let blockOptions: Array<{ value: string; label: string }> = []

  const DRAG_TYPE = 'application/x-comuna-template-palette'

  const writeDragPayload = (
    event: DragEvent,
    payload: TemplateEditorDragPaletteItem
  ) => {
    const serialized = JSON.stringify(payload)
    templateEditorDraggedItem.set(payload)
    event.dataTransfer?.setData(DRAG_TYPE, serialized)
    event.dataTransfer?.setData('text/plain', serialized)
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'copy'
    }
  }

  const clearDragPayload = () => {
    window.setTimeout(() => {
      templateEditorDraggedItem.set(null)
    }, 0)
  }
</script>

<div class="flex flex-col gap-4">
  <section class="rounded-[28px] border border-slate-200 bg-white px-5 py-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950/70">
    <div class="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-zinc-400">Доступные поля</div>
    <div class="mt-2 text-sm text-slate-600 dark:text-zinc-300">
      Перетаскивайте поля в `Header` или `Footer`.
    </div>
    <div class="mt-4 flex flex-col gap-2">
      {#each fieldOptions as fieldOption}
        <button
          type="button"
          draggable="true"
          class="flex w-full cursor-grab items-center rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-medium text-slate-800 transition hover:border-slate-300 hover:bg-white active:cursor-grabbing dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-zinc-100 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
          on:dragstart={(event) => writeDragPayload(event, { kind: 'field', fieldType: fieldOption.value })}
          on:dragend={clearDragPayload}
        >
          <span class="min-w-0 truncate">{fieldOption.label}</span>
        </button>
      {/each}
    </div>
  </section>

  <section class="rounded-[28px] border border-slate-200 bg-white px-5 py-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950/70">
    <div class="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-zinc-400">Все блоки</div>
    <div class="mt-2 text-sm text-slate-600 dark:text-zinc-300">
      Перетаскивайте блоки в `Header`, `Текстовый блок` или `Footer`.
    </div>
    <div class="mt-4 flex flex-col gap-2">
      {#each blockOptions as option}
        <button
          type="button"
          draggable="true"
          class="flex w-full cursor-grab items-center rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-medium text-slate-800 transition hover:border-slate-300 hover:bg-white active:cursor-grabbing dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-zinc-100 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
          on:dragstart={(event) => writeDragPayload(event, { kind: 'block', blockType: option.value })}
          on:dragend={clearDragPayload}
        >
          <span class="min-w-0 truncate">{option.label}</span>
        </button>
      {/each}
    </div>
  </section>
</div>
