const EDITOR_MODEL_BASE64_RE = /^[A-Za-z0-9+/_-]*={0,2}$/

const isEditorModelShape = (value: unknown): value is { blocks: unknown[]; additional?: unknown } =>
  Boolean(value && typeof value === 'object' && Array.isArray((value as { blocks?: unknown[] }).blocks))

export function parseSerializedEditorModel(rawValue: string): any | null {
  const raw = typeof rawValue === 'string' ? rawValue.trim() : ''
  if (!raw) return null

  if (raw.startsWith('<') && raw.endsWith('>')) {
    return null
  }

  if (raw.startsWith('{') && raw.endsWith('}')) {
    try {
      const parsed = JSON.parse(raw)
      return isEditorModelShape(parsed) ? parsed : null
    } catch {
      return null
    }
  }

  if (!EDITOR_MODEL_BASE64_RE.test(raw) || raw.length < 16) {
    return null
  }

  try {
    const jsonString = decodeURIComponent(escape(atob(raw)))
    const parsed = JSON.parse(jsonString)
    return isEditorModelShape(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function looksLikeSerializedEditorModel(rawValue: string): boolean {
  const raw = typeof rawValue === 'string' ? rawValue.trim() : ''
  if (!raw) return false
  if (raw.startsWith('{') && raw.endsWith('}')) return true
  return raw.startsWith('eyJ') && EDITOR_MODEL_BASE64_RE.test(raw) && raw.length >= 24
}
