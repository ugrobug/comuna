import { writable } from 'svelte/store'

export type TemplateEditorDragPaletteItem =
  | { kind: 'block'; blockType: string; dragId?: string }
  | { kind: 'field'; fieldType: 'text' | 'select' | 'checkbox'; dragId?: string }

export type TemplateEditorDropZone = 'header' | 'available' | 'footer'

export type TemplateEditorDropRequest = {
  zone: TemplateEditorDropZone
  item: TemplateEditorDragPaletteItem
}

export const templateEditorDraggedItem = writable<TemplateEditorDragPaletteItem | null>(null)
export const templateEditorActiveDropZone = writable<TemplateEditorDropZone | null>(null)
export const templateEditorDropRequest = writable<TemplateEditorDropRequest | null>(null)
