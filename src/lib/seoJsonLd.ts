export const toWellFormedUnicode = (value: string): string => {
  let result = ''
  for (let index = 0; index < value.length; index += 1) {
    const current = value.charCodeAt(index)
    if (current >= 0xd800 && current <= 0xdbff) {
      const next = value.charCodeAt(index + 1)
      if (next >= 0xdc00 && next <= 0xdfff) {
        result += value[index] + value[index + 1]
        index += 1
      } else {
        result += '\ufffd'
      }
      continue
    }
    if (current >= 0xdc00 && current <= 0xdfff) {
      result += '\ufffd'
      continue
    }
    result += value[index]
  }
  return result
}

export const truncateUnicodeText = (value: string, maxLength: number): string => {
  const wellFormed = toWellFormedUnicode(value)
  const codePoints = Array.from(wellFormed)
  if (codePoints.length <= maxLength) return wellFormed
  return `${codePoints.slice(0, Math.max(maxLength, 0)).join('').trimEnd()}…`
}

export const stringifyJsonLd = (value: unknown): string =>
  JSON.stringify(value, (_key, item) =>
    typeof item === 'string' ? toWellFormedUnicode(item) : item
  )
    .replace(/</g, '\\u003c')
    .replace(/>/g, '\\u003e')
    .replace(/&/g, '\\u0026')
