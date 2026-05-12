import { writable } from 'svelte/store'

export type TemplateEditorFieldType = 'text' | 'file' | 'select' | 'checkbox'

export type TemplateEditorDragPaletteItem =
  | { kind: 'block'; blockType: string; dragId?: string }
  | { kind: 'field'; fieldType: TemplateEditorFieldType; dragId?: string }

export type TemplateEditorDropZone = 'header' | 'available' | 'footer'

export type TemplateEditorDropRequest = {
  zone: TemplateEditorDropZone
  item: TemplateEditorDragPaletteItem
}

export const TEMPLATE_EDITOR_DROP_EVENT = 'comuna-template-editor-drop'

export const templateEditorDraggedItem = writable<TemplateEditorDragPaletteItem | null>(null)
export const templateEditorActiveDropZone = writable<TemplateEditorDropZone | null>(null)
export const templateEditorDropRequest = writable<TemplateEditorDropRequest | null>(null)
