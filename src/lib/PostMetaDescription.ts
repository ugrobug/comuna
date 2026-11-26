import { decodeHTMLStrict } from 'entities'
import { truncateUnicodeText } from './seoJsonLd'
import { looksLikeSerializedEditorModel, parseSerializedEditorModel } from './serializedEditorModel'

export class PostMetaDescription {
  static fromContent(content: string): string {
    const raw = content.trim()
    const editor = parseSerializedEditorModel(raw)
    if (!editor) {
      return looksLikeSerializedEditorModel(raw) ? '' : this.plainText(raw)
    }

    for (const candidate of [editor.additional?.metaDescription, editor.additional?.previewDescription]) {
      const text = this.plainText(candidate)
      if (text) return text
    }
    for (const block of editor.blocks) {
      const type = String(block?.type || '').toLowerCase()
      if (type === 'paragraph' || type === 'header') {
        const text = this.plainText(block.data?.text)
        if (text) return text
      }
    }
    return ''
  }

  private static plainText(value: unknown): string {
    if (typeof value !== 'string') return ''
    const text = decodeHTMLStrict(value.replace(/<[^>]*>/g, ' ')).replace(/\s+/g, ' ').trim()
    return truncateUnicodeText(text, 200)
  }
}
