import { writable } from 'svelte/store'

export type TemplateEditorDragPaletteItem =
  | { kind: 'block'; blockType: string }
  | { kind: 'field'; fieldType: 'text' | 'select' | 'checkbox' }

export const templateEditorDraggedItem = writable<TemplateEditorDragPaletteItem | null>(null)
