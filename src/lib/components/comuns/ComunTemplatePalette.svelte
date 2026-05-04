<script lang="ts">
  import { get } from 'svelte/store'
  import {
    TEMPLATE_EDITOR_DROP_EVENT,
    templateEditorActiveDropZone,
    templateEditorDraggedItem,
    templateEditorDropRequest,
    type TemplateEditorDragPaletteItem,
    type TemplateEditorDropZone,
  } from '$lib/components/comuns/templateEditorDnd'

  export let fieldOptions: Array<{ value: string; label: string }> = []
  export let blockOptions: Array<{ value: string; label: string }> = []

  const DRAG_TYPE = 'application/x-comuna-template-palette'
  const DROP_ZONE_SELECTOR = '[data-template-drop-zone]'

  let activeDragItem: TemplateEditorDragPaletteItem | null = null
  let dragPreviewLabel = ''
  let dragX = 0
  let dragY = 0

  const createDragId = () =>
    globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`

  const normalizeDropZone = (zone?: string): TemplateEditorDropZone | null =>
    zone === 'header' || zone === 'available' || zone === 'footer' ? zone : null

  const readZoneFromElement = (element: Element | null | undefined): TemplateEditorDropZone | null => {
    const dropZoneElement = element?.closest?.(DROP_ZONE_SELECTOR) as HTMLElement | null
    return normalizeDropZone(dropZoneElement?.dataset?.templateDropZone)
  }

  const readDropZoneFromPoint = (x: number, y: number): TemplateEditorDropZone | null => {
    for (const element of document.elementsFromPoint(x, y)) {
      const zone = readZoneFromElement(element)
      if (zone) return zone
    }
    for (const element of document.querySelectorAll<HTMLElement>(DROP_ZONE_SELECTOR)) {
      const rect = element.getBoundingClientRect()
      if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
        return normalizeDropZone(element.dataset.templateDropZone)
      }
    }
    return null
  }

  const sendDropRequest = (
    zone: TemplateEditorDropZone,
    item: TemplateEditorDragPaletteItem
  ) => {
    templateEditorDropRequest.set({ zone, item })
    window.dispatchEvent(
      new CustomEvent(TEMPLATE_EDITOR_DROP_EVENT, {
        detail: { zone, item },
      })
    )
  }

  const clearPointerDrag = () => {
    activeDragItem = null
    dragPreviewLabel = ''
    templateEditorDraggedItem.set(null)
    templateEditorActiveDropZone.set(null)
    window.removeEventListener('pointermove', handlePointerMove)
    window.removeEventListener('pointerup', handlePointerUp)
    window.removeEventListener('pointercancel', handlePointerCancel)
  }

  const handlePointerMove = (event: PointerEvent) => {
    if (!activeDragItem) return
    dragX = event.clientX
    dragY = event.clientY
    templateEditorActiveDropZone.set(readDropZoneFromPoint(event.clientX, event.clientY))
  }

  const handlePointerUp = (event: PointerEvent) => {
    const item = activeDragItem
    const zone = readDropZoneFromPoint(event.clientX, event.clientY) ?? get(templateEditorActiveDropZone)
    if (item && zone) {
      sendDropRequest(zone, item)
    }
    clearPointerDrag()
  }

  const handlePointerCancel = () => {
    clearPointerDrag()
  }

  const writeDragPayload = (
    event: DragEvent,
    payload: TemplateEditorDragPaletteItem
  ) => {
    const dragPayload = { ...payload, dragId: createDragId() }
    const serialized = JSON.stringify(dragPayload)
    templateEditorDraggedItem.set(dragPayload)
    event.dataTransfer?.setData(DRAG_TYPE, serialized)
    event.dataTransfer?.setData('text/plain', serialized)
    if (event.dataTransfer) {
      event.dataTransfer.effectAllowed = 'copy'
    }
  }

  const startPointerDrag = (
    event: PointerEvent,
    payload: TemplateEditorDragPaletteItem,
    label: string
  ) => {
    if (event.button !== 0) return
    event.preventDefault()
    const dragPayload = { ...payload, dragId: createDragId() }
    activeDragItem = dragPayload
    dragPreviewLabel = label
    dragX = event.clientX
    dragY = event.clientY
    templateEditorDraggedItem.set(dragPayload)
    templateEditorActiveDropZone.set(readDropZoneFromPoint(event.clientX, event.clientY))
    window.addEventListener('pointermove', handlePointerMove)
    window.addEventListener('pointerup', handlePointerUp)
    window.addEventListener('pointercancel', handlePointerCancel)
  }

  const clearDragPayload = () => {
    const item = get(templateEditorDraggedItem)
    const zone = get(templateEditorActiveDropZone)
    if (item && zone) {
      sendDropRequest(zone, item)
    }
    window.setTimeout(() => {
      templateEditorDraggedItem.set(null)
      templateEditorActiveDropZone.set(null)
    }, 0)
  }
</script>

<div class="flex flex-col gap-4">
  <section class="rounded-[28px] border border-slate-200 bg-white px-5 py-5 shadow-sm dark:border-zinc-800 dark:bg-zinc-950/70">
    <div class="text-xs uppercase tracking-[0.2em] text-slate-500 dark:text-zinc-400">Доступные поля</div>
    <div class="mt-2 text-sm text-slate-600 dark:text-zinc-300">
      Перетаскивайте поля в `Header`, `Текстовый блок` или `Footer`.
    </div>
    <div class="mt-4 flex flex-col gap-2">
      {#each fieldOptions as fieldOption}
        <button
          type="button"
          draggable="true"
          class="flex w-full touch-none select-none items-center rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-medium text-slate-800 transition hover:border-slate-300 hover:bg-white active:cursor-grabbing dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-zinc-100 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
          class:cursor-grab={!activeDragItem}
          class:cursor-grabbing={Boolean(activeDragItem)}
          on:pointerdown={(event) =>
            startPointerDrag(event, { kind: 'field', fieldType: fieldOption.value }, fieldOption.label)}
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
          class="flex w-full touch-none select-none items-center rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm font-medium text-slate-800 transition hover:border-slate-300 hover:bg-white active:cursor-grabbing dark:border-zinc-800 dark:bg-zinc-900/70 dark:text-zinc-100 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
          class:cursor-grab={!activeDragItem}
          class:cursor-grabbing={Boolean(activeDragItem)}
          on:pointerdown={(event) =>
            startPointerDrag(event, { kind: 'block', blockType: option.value }, option.label)}
          on:dragstart={(event) => writeDragPayload(event, { kind: 'block', blockType: option.value })}
          on:dragend={clearDragPayload}
        >
          <span class="min-w-0 truncate">{option.label}</span>
        </button>
      {/each}
    </div>
  </section>
</div>

{#if activeDragItem}
  <div
    class="pointer-events-none fixed z-[9999] rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-900 shadow-2xl dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
    style={`left: ${dragX}px; top: ${dragY}px; transform: translate(-50%, -50%);`}
  >
    {dragPreviewLabel}
  </div>
{/if}
